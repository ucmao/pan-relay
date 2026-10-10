import json
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple, Type

from src.clients import (
    AliyunPanClient,
    BaiduPanClient,
    CaiyunPanClient,
    GuangyaPanClient,
    QuarkPanClient,
    UcPanClient,
    WukongPanClient,
    XunleiPanClient,
)
from src.db.accounts import (
    get_account_by_id,
    get_accounts_by_cloud,
    record_account_keepalive,
    record_account_transfer,
    update_account,
    update_account_credential,
    update_account_space,
    update_account_status,
)
from src.db.credentials import get_cookie_by_cloud_name

logger = logging.getLogger(__name__)

# 云盘名称与客户端映射关系
CLOUD_CLIENT_MAP: Dict[str, Type] = {
    "夸克网盘": QuarkPanClient,
    "百度网盘": BaiduPanClient,
    "阿里云盘": AliyunPanClient,
    "UC网盘": UcPanClient,
    "迅雷网盘": XunleiPanClient,
    "光鸭云盘": GuangyaPanClient,
    "悟空网盘": WukongPanClient,
    "移动云盘": CaiyunPanClient,
}


def _parse_xunlei_credential_dict(raw_credential: str, extra_data: Optional[str] = None) -> Dict[str, str]:
    """解析迅雷网盘凭据"""
    result = {
        "refresh_token": "",
        "captcha_sign": "",
        "user_id": "",
        "client_id": "",
        "device_id": "",
    }
    # 优先检查 extra_data
    if extra_data:
        try:
            extra = json.loads(extra_data) if isinstance(extra_data, str) else extra_data
            if isinstance(extra, dict):
                for k in result.keys():
                    if extra.get(k):
                        result[k] = str(extra[k]).strip()
        except Exception:
            pass

    # 其次检查 credential 字段
    if raw_credential:
        try:
            parsed = json.loads(raw_credential)
            if isinstance(parsed, dict):
                for k in result.keys():
                    if parsed.get(k) and not result[k]:
                        result[k] = str(parsed[k]).strip()
        except Exception:
            if not result["refresh_token"]:
                result["refresh_token"] = raw_credential.strip()

    return result


class AccountPoolManager:
    """
    网盘多账号池管理与智能调度器。
    支持同网盘多账号优先级管理、容量过滤、加权轮询分流、故障自动转移以及定期保活。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AccountPoolManager, cls).__new__(cls)
                cls._instance._rr_indices = {}  # cloud_name -> int (用于同优先级账号轮询)
                cls._instance._rr_lock = threading.Lock()
            return cls._instance

    @classmethod
    def get_instance(cls) -> "AccountPoolManager":
        if cls._instance is None:
            cls._instance = AccountPoolManager()
        return cls._instance

    def create_client_for_account(self, account: Dict[str, Any]) -> Optional[Any]:
        """
        根据账号记录实例化对应的网盘客户端对象。
        """
        cloud_name = account.get("cloud_name")
        client_cls = CLOUD_CLIENT_MAP.get(cloud_name)
        if not client_cls:
            logger.error(f"不支持的网盘平台: {cloud_name}")
            return None

        credential = account.get("credential", "")
        extra_data = account.get("extra_data")

        try:
            if cloud_name == "迅雷网盘":
                cred_dict = _parse_xunlei_credential_dict(credential, extra_data)
                if not cred_dict.get("refresh_token"):
                    logger.error(f"迅雷账号(id={account.get('id')})缺少 refresh_token")
                    return None
                return client_cls(cred_dict)
            elif cloud_name == "阿里云盘":
                # 阿里接收 refresh_token 字符串
                rt = credential.strip()
                if extra_data:
                    try:
                        parsed = json.loads(extra_data)
                        if isinstance(parsed, dict) and parsed.get("refresh_token"):
                            rt = parsed["refresh_token"].strip()
                    except Exception:
                        pass
                return client_cls(rt)
            else:
                return client_cls(credential.strip())
        except Exception as exc:
            logger.error(f"实例化网盘客户端异常 (cloud={cloud_name}, account_id={account.get('id')}): {exc}")
            return None

    def get_client_by_account_id(self, account_id: int) -> Optional[Any]:
        """
        按 account_id 查询并实例化客户端（常用于按账号精准清理删除过期分享）。
        """
        account = get_account_by_id(account_id)
        if not account:
            return None
        return self.create_client_for_account(account)

    def get_candidate_accounts(
        self, cloud_name: str, min_left_space_bytes: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取指定平台所有符合条件（激活、有效、剩余空间足够）的可用候选账号列表。
        """
        accounts = get_accounts_by_cloud(cloud_name, only_active=True, only_valid=True)
        if not accounts:
            return []

        # 容量过滤：如果配置了最小剩余空间要求，过滤空间不足的账号
        if min_left_space_bytes > 0:
            filtered = [
                acc
                for acc in accounts
                if acc.get("left_space_bytes", 0) <= 0
                or acc.get("left_space_bytes", 0) >= min_left_space_bytes
            ]
            if filtered:
                return filtered

        return accounts

    def select_account_for_transfer(
        self, cloud_name: str, min_left_space_bytes: int = 0
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
        """
        调度选取一个最适合进行转存的账号并返回 (account, client)。
        调度策略：
        1. 过滤有效且空间充裕的账号池；
        2. 按 priority (优先级，越小越优先) 分组；
        3. 同一优先级内采用 Round-Robin (轮询) 平摊并发与风控压力。
        4. 若无多账号池配置，平滑回退至单凭据配置。
        """
        candidates = self.get_candidate_accounts(cloud_name, min_left_space_bytes)

        if candidates:
            # 找到最高优先级 (min priority)
            top_priority = min(acc.get("priority", 0) for acc in candidates)
            top_group = [acc for acc in candidates if acc.get("priority", 0) == top_priority]

            # 轮询选择
            with self._rr_lock:
                idx = self._rr_indices.get(cloud_name, 0)
                selected_account = top_group[idx % len(top_group)]
                self._rr_indices[cloud_name] = (idx + 1) % len(top_group)

            client = self.create_client_for_account(selected_account)
            if client:
                return selected_account, client

            # 如果当前选中的账号创建客户端失败，尝试备选账号
            for fallback_acc in candidates:
                if fallback_acc.get("id") == selected_account.get("id"):
                    continue
                client = self.create_client_for_account(fallback_acc)
                if client:
                    return fallback_acc, client

        # 平滑回退：若 cloud_accounts 中暂无任何可用账号，尝试读取旧凭证表
        fallback_cred = get_cookie_by_cloud_name(cloud_name)
        if fallback_cred:
            dummy_account = {
                "id": None,
                "cloud_name": cloud_name,
                "account_name": f"{cloud_name}-默认单凭据",
                "credential": fallback_cred,
                "extra_data": None,
                "is_active": 1,
                "is_valid": 1,
            }
            client = self.create_client_for_account(dummy_account)
            if client:
                return dummy_account, client

        return None, None

    def report_success(self, account_id: Optional[int], used_delta_bytes: int = 0):
        """
        上报一次转存成功，更新账号使用计数与容量。
        """
        if not account_id:
            return
        record_account_transfer(account_id)
        if used_delta_bytes > 0:
            account = get_account_by_id(account_id)
            if account and account.get("left_space_bytes", 0) > 0:
                new_used = account.get("used_space_bytes", 0) + used_delta_bytes
                update_account_space(
                    account_id,
                    total_space=account.get("total_space_bytes", 0),
                    used_space=new_used,
                )

    def report_failure(self, account_id: Optional[int], error_msg: str, is_fatal: bool = False):
        """
        上报账号操作异常。若为严重凭据失效或被封控，自动将 is_valid 标记为 0。
        """
        if not account_id:
            return
        logger.warning(f"账号池上报失败 (account_id={account_id}, fatal={is_fatal}): {error_msg}")
        if is_fatal:
            update_account_status(account_id, is_valid=False, invalid_reason=error_msg)
        else:
            update_account_status(account_id, is_valid=True, invalid_reason=f"最近偶发警告: {error_msg}")

    def inspect_and_refresh_account(self, account_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        主动自检账号有效性并自动更新空间配额与用户名。
        """
        account = get_account_by_id(account_id)
        if not account:
            return False, "账号不存在", {}

        client = self.create_client_for_account(account)
        if not client:
            update_account_status(account_id, is_valid=False, invalid_reason="初始化客户端失败，凭证格式错误")
            return False, "初始化客户端失败", {}

        cloud_name = account.get("cloud_name")
        info = {
            "username": account.get("username") or "",
            "total_space_bytes": account.get("total_space_bytes", 0),
            "used_space_bytes": account.get("used_space_bytes", 0),
            "left_space_bytes": account.get("left_space_bytes", 0),
            "vip_status": account.get("vip_status", 0),
        }

        try:
            # 1. 针对不同客户端的专项刷新与校验
            if cloud_name == "阿里云盘":
                if hasattr(client, "_refresh_access_token"):
                    client._refresh_access_token(force=True)
                    if client.refresh_token and client.refresh_token != account.get("credential"):
                        update_account_credential(account_id, client.refresh_token)

            elif cloud_name == "迅雷网盘":
                if hasattr(client, "_get_access_token"):
                    token = client._get_access_token()
                    if not token:
                        raise ValueError("迅雷 refresh_token 已过期或无效，请重新授权")
                    if client.refresh_token:
                        cred_raw = account.get("credential") or ""
                        if cred_raw.startswith("{"):
                            try:
                                d = json.loads(cred_raw)
                                if d.get("refresh_token") != client.refresh_token:
                                    d["refresh_token"] = client.refresh_token
                                    update_account_credential(account_id, json.dumps(d, ensure_ascii=False))
                            except Exception:
                                pass
                        elif cred_raw != client.refresh_token:
                            update_account_credential(account_id, client.refresh_token)

            elif cloud_name == "夸克网盘":
                if hasattr(client, "get_all_file"):
                    client.get_all_file()

            elif cloud_name == "百度网盘":
                if hasattr(client, "get_or_create_dir"):
                    client.get_or_create_dir("PanRelay_Health")

            elif cloud_name == "光鸭云盘":
                if hasattr(client, "_get_access_token"):
                    token = client._get_access_token()
                    if not token:
                        raise ValueError("光鸭云盘 Token 已过期或无效，请重新授权")

            elif hasattr(client, "get_or_create_dir"):
                client.get_or_create_dir("PanRelay_Health")

            # 2. 获取实时用户信息与空间容量配额
            if hasattr(client, "get_user_and_space_info"):
                live_info = client.get_user_and_space_info()
                if live_info:
                    if live_info.get("username"):
                        info["username"] = live_info["username"]
                    if live_info.get("total_space_bytes"):
                        info["total_space_bytes"] = int(live_info["total_space_bytes"])
                    if "used_space_bytes" in live_info:
                        info["used_space_bytes"] = int(live_info["used_space_bytes"])
                    if "vip_status" in live_info:
                        info["vip_status"] = int(live_info["vip_status"])
                    info["left_space_bytes"] = max(0, info["total_space_bytes"] - info["used_space_bytes"])

            # 3. 持久化同步信息至数据库
            update_data = {
                "username": info["username"],
                "total_space_bytes": info["total_space_bytes"],
                "used_space_bytes": info["used_space_bytes"],
                "left_space_bytes": info["left_space_bytes"],
                "vip_status": info["vip_status"],
                "is_valid": 1,
                "invalid_reason": "",
            }
            update_account(account_id, update_data)
            record_account_keepalive(account_id)
            if cloud_name in ("悟空网盘", "移动云盘", "迅雷网盘", "迅雷"):
                return True, "凭证有效，账号状态就绪（该平台暂不支持容量探测）", info
            return True, "凭证有效，空间配额与账号信息已同步", info

        except Exception as exc:
            err_str = str(exc)
            logger.error(f"自检网盘账号(id={account_id})失败: {err_str}")
            update_account_status(account_id, is_valid=False, invalid_reason=err_str)
            return False, f"测试失败: {err_str}", info

    def keepalive_all_accounts(self) -> Dict[str, Any]:
        """
        后台保活与续期任务：遍历所有启用的账号，执行检测、静默续期并同步空间状态。
        """
        from src.db.accounts import get_all_accounts
        all_active = [acc for acc in get_all_accounts() if acc.get("is_active")]

        refreshed = 0
        failed = 0

        for acc in all_active:
            try:
                success, msg, _ = self.inspect_and_refresh_account(acc["id"])
                if success:
                    refreshed += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.warning(f"账号保活异常 (id={acc['id']}): {exc}")
                failed += 1

        return {"total_checked": len(all_active), "refreshed": refreshed, "failed": failed}
