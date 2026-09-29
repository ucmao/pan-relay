import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.clients.base_client import BasePanClient

logger = logging.getLogger(__name__)

# ============================================================================
# 迅雷 Android 移动端签名体系与算法
# ============================================================================
_CLIENT_ID = "Xp6vsxz_7IYVw2BB"
_CLIENT_SECRET = "Xp6vsy4tN9toTVdMSpomVdXpRmES"
_CLIENT_VERSION = "8.31.0.9726"
_PACKAGE_NAME = "com.xunlei.downloadprovider"
_USER_AGENT = (
    "ANDROID-com.xunlei.downloadprovider/8.31.0.9726 netWorkType/5G appid/40 "
    "deviceName/Xiaomi_M2004j7ac deviceModel/M2004J7AC OSVersion/12 "
    "protocolVersion/301 platformVersion/10 sdkVersion/512000 Oauth2Client/0.9 "
    "(Linux 4_14_186-perf-gddfs8vbb238b) (JAVA 0)"
)

# 10 轮固定的 MD5 盐值算法
_ALGORITHMS = [
    "9uJNVj/wLmdwKrJaVj/omlQ",
    "Oz64Lp0GigmChHMf/6TNfxx7O9PyopcczMsnf",
    "Eb+L7Ce+Ej48u",
    "jKY0",
    "ASr0zCl6v8W4aidjPK5KHd1Lq3t+vBFf41dqv5+fnOd",
    "wQlozdg6r1qxh0eRmt3QgNXOvSZO6q/GXK",
    "gmirk+ciAvIgA/cxUUCema47jr/YToixTT+Q6O",
    "5IiCoM9B1/788ntB",
    "P07JH0h6qoM6TSUAK2aL9T5s2QBVeY9JWvalf",
    "+oK0AN",
]

# 全局缓存，避免频繁刷新 Token 触发风控
# 结构: {refresh_token: {"access_token": str, "user_id": str, "expires_at": float}}
_XUNLEI_ACCESS_TOKEN_CACHE: Dict[str, Dict[str, Any]] = {}
# 结构: {(device_id, action): {"captcha_token": str, "expires_at": float}}
_XUNLEI_CAPTCHA_TOKEN_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}


def _derive_device_id(refresh_token: str) -> str:
    """根据 refresh_token 派生稳定独立的 32 位设备标识"""
    return hashlib.md5(f"{refresh_token}xlrefresh".encode("utf-8")).hexdigest()


def _calc_captcha_sign(client_id: str, client_version: str, package_name: str, device_id: str, ts: str) -> str:
    """基于 Android 客户端逆向盐值算法动态计算验证码签名"""
    s = f"{client_id}{client_version}{package_name}{device_id}{ts}"
    for salt in _ALGORITHMS:
        s = hashlib.md5((s + salt).encode("utf-8")).hexdigest()
    return f"1.{s}"


class XunleiPanClient(BasePanClient):
    """迅雷网盘客户端 (基于 Android 移动端签名体系)"""

    client_id = _CLIENT_ID
    client_secret = _CLIENT_SECRET
    client_version = _CLIENT_VERSION
    package_name = _PACKAGE_NAME
    user_agent = _USER_AGENT

    def __init__(self, credential: Dict[str, str]) -> None:
        self.refresh_token = (credential.get("refresh_token") or "").strip()
        self.user_id = str(credential.get("user_id") or "").strip()
        self.client_id = credential.get("client_id") or _CLIENT_ID
        self.client_secret = credential.get("client_secret") or _CLIENT_SECRET
        self.device_id = credential.get("device_id") or (_derive_device_id(self.refresh_token) if self.refresh_token else "c24ecadc44c643637d127fb847dbe36d")
        if self.client_id == "YBJdb1UyFQJwh_nS":
            self.client_version = "5.80.5"
            self.package_name = "com.xunlei.macthunder"
            self.user_agent = "Thunder/5.80.5 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
                "x-client-id": self.client_id,
                "x-device-id": self.device_id,
            }
        )
        self.access_token = ""

    def store(
        self, share_url: str, to_dir: str = ""
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """执行完整转存换链流程：解析分享 -> 转存 -> 轮询等待任务完成 -> 创建专属分享"""
        share_id, pwd = self._parse_share_url(share_url)
        if not share_id:
            logger.error("迅雷网盘链接解析失败: %s", share_url)
            return None, None, None

        access_token = self._get_access_token()
        if not access_token:
            logger.error("迅雷网盘获取 access_token 失败，无法继续转存")
            return None, None, None

        # 1. 获取分享详情 (GET /drive/v1/share)
        detail = self._request_pan(
            "GET",
            "https://api-pan.xunlei.com/drive/v1/share",
            params={
                "share_id": share_id,
                "pass_code": pwd,
                "limit": 100,
                "pass_code_token": "",
                "page_token": "",
                "thumbnail_size": "SIZE_SMALL",
            },
            action="GET:/drive/v1/share",
        )
        if not detail or detail.get("error_code"):
            err_msg = (detail or {}).get("error_description") or (detail or {}).get("error_code") or "未知错误"
            logger.error("迅雷网盘获取分享信息失败: %s (share_id=%s)", err_msg, share_id)
            return None, None, None

        share_status = detail.get("share_status")
        if share_status and share_status != "OK":
            if share_status == "SENSITIVE_RESOURCE":
                logger.error("迅雷网盘分享内容涉及侵权或敏感违规，已被官方屏蔽: share_id=%s", share_id)
            else:
                status_text = detail.get("share_status_text") or share_status
                logger.error("迅雷网盘分享状态异常: %s (share_id=%s)", status_text, share_id)
            return None, None, None

        from src.services.ad_filter_service import is_ad_filename

        raw_files = detail.get("files", [])
        files = [item for item in raw_files if not is_ad_filename(item.get("name", ""))]
        if not files:
            logger.warning("迅雷网盘分享内容全为广告，已终止转存与分享: share_id=%s", share_id)
            return None, None, None

        file_ids = [item["id"] for item in files if item.get("id")]
        pass_code_token = detail.get("pass_code_token", "")
        if not file_ids or not pass_code_token:
            logger.error("迅雷网盘分享详情缺少必要字段: file_ids=%s, pass_code_token=%s", file_ids, bool(pass_code_token))
            return None, None, None

        # 2. 提交转存请求 (POST /drive/v1/share/restore)
        target_dir = "" if to_dir in ("/", "\\", "", "0", "root", None) else to_dir
        restore_result = self._request_pan(
            "POST",
            "https://api-pan.xunlei.com/drive/v1/share/restore",
            payload={
                "parent_id": target_dir,
                "share_id": share_id,
                "pass_code_token": pass_code_token,
                "ancestor_ids": [],
                "specify_parent_id": True,
                "file_ids": file_ids,
            },
            action="POST:/drive/v1/share/restore",
        )
        if not restore_result or restore_result.get("error_code"):
            err_msg = (restore_result or {}).get("error_description") or (restore_result or {}).get("error_code") or "转存接口异常"
            logger.error("迅雷网盘转存失败: %s", err_msg)
            return None, None, None

        task_id = restore_result.get("restore_task_id")
        if not task_id:
            logger.error("迅雷网盘转存接口未返回 restore_task_id")
            return None, None, None

        # 3. 轮询等待转存异步任务完成
        task_result = self._wait_task(task_id)
        if not task_result or task_result.get("progress") != 100:
            err_msg = (task_result or {}).get("message") or "转存任务未完成或超时"
            logger.error("迅雷网盘转存任务失败: %s", err_msg)
            return None, None, None

        # 4. 解析转存后的新文件 ID (支持多种响应格式兼容解析)
        trace_file_ids: List[str] = []
        params_obj = task_result.get("params") or {}
        raw_trace = params_obj.get("trace_file_ids") or ""
        if raw_trace:
            try:
                parsed = json.loads(raw_trace) if isinstance(raw_trace, str) else raw_trace
                if isinstance(parsed, dict):
                    trace_file_ids = [str(v) for v in parsed.values() if v]
                elif isinstance(parsed, list):
                    trace_file_ids = [str(v) for v in parsed if v]
            except Exception:
                trace_file_ids = []

        if not trace_file_ids and isinstance(params_obj.get("file_ids"), list):
            trace_file_ids = [str(v) for v in params_obj["file_ids"] if v]

        if not trace_file_ids and task_result.get("file_id"):
            trace_file_ids = [str(task_result["file_id"])]

        if not trace_file_ids:
            logger.error("迅雷网盘未解析出转存后的文件 ID (task params: %s)", params_obj)
            return None, None, None

        # 尝试植入个人自定义引流广告 (若已配置并启用)
        for fid in trace_file_ids:
            try:
                self.add_ad(fid)
            except Exception:
                pass

        cleaned_file_ids = self._clean_ad_files_and_folders(trace_file_ids)
        if not cleaned_file_ids:
            cleaned_file_ids = trace_file_ids

        # 5. 创建站长专属新分享链接 (POST /drive/v1/share)
        share_title = detail.get("title") or detail.get("share_name") or (files[0].get("name") if files else "云盘资源分享")
        share_result = self._request_pan(
            "POST",
            "https://api-pan.xunlei.com/drive/v1/share",
            payload={
                "file_ids": cleaned_file_ids,
                "share_to": "copy",
                "params": {
                    "subscribe_push": "false",
                    "WithPassCodeInLink": "true",
                },
                "title": share_title,
                "restore_limit": "-1",
                "expiration_days": "-1",
            },
            action="POST:/drive/v1/share",
        )
        if not share_result or share_result.get("error_code") or not share_result.get("share_url"):
            err_msg = (share_result or {}).get("error_description") or (share_result or {}).get("error_code") or "创建分享失败"
            logger.error("迅雷网盘创建分享失败: %s", err_msg)
            return None, None, None

        final_url = share_result["share_url"]
        if share_result.get("pass_code"):
            final_url = f"{final_url}?pwd={share_result['pass_code']}"

        first_fid = cleaned_file_ids[0] if len(cleaned_file_ids) == 1 else ",".join(cleaned_file_ids)
        return first_fid, share_title, final_url

    def del_file(self, file_ids: Any) -> bool:
        """从个人网盘中删除转存的临时文件 (实现 BasePanClient 抽象接口)"""
        if not file_ids:
            logger.warning("迅雷网盘删除操作未提供 file_ids")
            return False

        if isinstance(file_ids, list):
            normalized_ids = [str(x).strip() for x in file_ids if str(x).strip()]
        elif isinstance(file_ids, str):
            normalized_ids = [item.strip() for item in file_ids.split(",") if item.strip()]
        else:
            normalized_ids = [str(file_ids).strip()]

        if not normalized_ids:
            return False

        success_count = 0
        for fid in normalized_ids:
            result = self._request_pan(
                "DELETE",
                f"https://api-pan.xunlei.com/drive/v1/files/{fid}",
                action=f"DELETE:/drive/v1/files/{fid}",
            )
            if result is not None and not result.get("error_code"):
                success_count += 1
            else:
                err_msg = (result or {}).get("error_description") or (result or {}).get("error_code") or "未知原因"
                logger.warning("迅雷网盘删除文件失败 (%s): %s", fid, err_msg)
        return success_count > 0

    def _clean_ad_files_and_folders(self, file_ids: List[str]) -> List[str]:
        """扫描迅雷网盘转存后的文件，智能清理广告/引流文件"""
        from src.services.ad_filter_service import is_ad_filename

        valid_ids: List[str] = []
        ad_ids: List[str] = []

        for fid in file_ids:
            try:
                info = self._request_pan("GET", f"https://api-pan.xunlei.com/drive/v1/files/{fid}", action=f"GET:/drive/v1/files/{fid}")
                name = (info or {}).get("name") or ""
                if name and is_ad_filename(name):
                    logger.info("迅雷网盘转存项命中广告关键词，标记清理: %s (fid=%s)", name, fid)
                    ad_ids.append(fid)
                else:
                    valid_ids.append(fid)
            except Exception as exc:
                logger.warning("迅雷网盘检测文件信息异常 (fid=%s): %s", fid, exc)
                valid_ids.append(fid)

        if ad_ids:
            try:
                self.del_file(ad_ids)
                logger.info("迅雷网盘已清理广告文件 %d 项: %s", len(ad_ids), ad_ids)
            except Exception as exc:
                logger.error("迅雷网盘清理广告文件失败: %s", exc)

        return valid_ids

    def get_or_create_dir(self, dir_name: str, parent_id: str = "") -> str:
        """获取或创建迅雷网盘目标目录"""
        if not dir_name or dir_name.strip() in ("", "/", "0"):
            return ""
        clean_name = dir_name.strip().strip("/")
        normalized_parent = "" if parent_id in ("0", "/", "root", None) else parent_id
        try:
            # 1. 查找是否存在同名目录
            list_res = self._request_pan(
                "GET",
                "https://api-pan.xunlei.com/drive/v1/files",
                params={"parent_id": normalized_parent, "limit": 100},
                action="GET:/drive/v1/files",
            )
            files = (list_res or {}).get("files", [])
            for f in files:
                if f.get("name") == clean_name and f.get("kind") == "drive#folder":
                    return str(f.get("id"))

            # 2. 不存在则创建
            create_res = self._request_pan(
                "POST",
                "https://api-pan.xunlei.com/drive/v1/files",
                payload={
                    "kind": "drive#folder",
                    "name": clean_name,
                    "parent_id": normalized_parent,
                },
                action="POST:/drive/v1/files",
            )
            new_id = (create_res or {}).get("file", {}).get("id") or (create_res or {}).get("id")
            if new_id:
                return str(new_id)
        except Exception as exc:
            logger.error("迅雷网盘获取或创建目录异常: %s", exc)

        return normalized_parent

    def _get_access_token(self) -> str:
        """使用 refresh_token 换取 access_token 并支持自动轮换持久化"""
        global _XUNLEI_ACCESS_TOKEN_CACHE

        now = time.time()
        cached = _XUNLEI_ACCESS_TOKEN_CACHE.get(self.refresh_token)
        if cached and cached.get("access_token") and now < cached.get("expires_at", 0) - 60:
            self.access_token = cached["access_token"]
            if cached.get("user_id"):
                self.user_id = cached["user_id"]
            return self.access_token

        try:
            payload = {
                "client_id": self.client_id,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            }
            if self.client_id == _CLIENT_ID and self.client_secret:
                payload["client_secret"] = self.client_secret

            response = requests.post(
                "https://xluser-ssl.xunlei.com/v1/auth/token",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": self.user_agent,
                    "x-client-id": self.client_id,
                    "x-device-id": self.device_id,
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("迅雷网盘获取 access_token 请求异常: %s", exc)
            return ""

        if not data:
            logger.error("迅雷网盘获取 access_token 返回空响应")
            return ""

        token_data = data.get("data") if isinstance(data.get("data"), dict) else data
        access_token = token_data.get("access_token", "")
        if not access_token:
            err_msg = data.get("error_description") or data.get("msg") or data.get("code") or "未知认证错误"
            logger.error("迅雷网盘 refresh_token 认证失败: %s", err_msg)
            return ""

        self.access_token = access_token
        self.user_id = str(token_data.get("user_id") or token_data.get("sub") or self.user_id or "")
        expires_in = int(token_data.get("expires_in", 7200))
        new_refresh_token = token_data.get("refresh_token")

        # 缓存 Access Token
        _XUNLEI_ACCESS_TOKEN_CACHE[self.refresh_token] = {
            "access_token": self.access_token,
            "user_id": self.user_id,
            "expires_at": now + expires_in,
        }

        # 轮换机制：若返回新的 refresh_token，自动更新数据库凭证
        if new_refresh_token and new_refresh_token != self.refresh_token:
            logger.info("迅雷网盘返回新的 refresh_token，正在执行自动轮换持久化...")
            try:
                from src.db.credentials import update_xunlei_refresh_token
                update_xunlei_refresh_token(new_refresh_token)
                _XUNLEI_ACCESS_TOKEN_CACHE[new_refresh_token] = _XUNLEI_ACCESS_TOKEN_CACHE.pop(self.refresh_token)
                self.refresh_token = new_refresh_token
                if not self.device_id:
                    self.device_id = _derive_device_id(self.refresh_token)
            except Exception as exc:
                logger.warning("迅雷网盘持久化新 refresh_token 异常: %s", exc)

        return self.access_token

    def _get_captcha_token(self, action: str) -> str:
        """获取验证码令牌 (自动生成时间戳与多轮迭代签名)"""
        global _XUNLEI_CAPTCHA_TOKEN_CACHE

        now = time.time()
        cache_key = (self.device_id, action)
        cached = _XUNLEI_CAPTCHA_TOKEN_CACHE.get(cache_key)
        if cached and cached.get("captcha_token") and now < cached.get("expires_at", 0) - 10:
            return cached["captcha_token"]

        # 优先检测本地 Mac Thunder 生成的系统级高防令牌 (若存在且未过期)
        meta_fallback = None
        try:
            import os, sqlite3
            local_cap_db = os.path.expanduser(f"~/Library/Application Support/Thunder/Account/captcha/2rvk4e3gkdnl7u1kl0k/{self.client_id}/data.db")
            if os.path.exists(local_cap_db):
                conn = sqlite3.connect(local_cap_db)
                cur = conn.cursor()
                cur.execute("SELECT captcha_token_info, expires_at FROM captcha_token_info ORDER BY expires_at DESC LIMIT 1")
                row = cur.fetchone()
                conn.close()
                if row:
                    info_dict = json.loads(row[0])
                    exp_at = float(row[1] or 0)
                    token = info_dict.get("captcha_token")
                    if token and exp_at > now + 10:
                        _XUNLEI_CAPTCHA_TOKEN_CACHE[cache_key] = {
                            "captcha_token": token,
                            "expires_at": exp_at,
                        }
                        return token
                    meta_fallback = info_dict.get("meta")
        except Exception:
            pass

        if self.client_id == "YBJdb1UyFQJwh_nS":
            meta = meta_fallback or {
                "client_version": self.client_version,
                "package_name": self.package_name,
                "user_id": self.user_id,
                "timestamp": "1790587491.046402",
                "captcha_sign": "1.09b150b2b79b7beffd6ba99afcf2351e",
            }
        else:
            ts = str(int(now * 1000))
            sign = _calc_captcha_sign(self.client_id, self.client_version, self.package_name, self.device_id, ts)
            meta = {
                "client_version": self.client_version,
                "package_name": self.package_name,
                "user_id": self.user_id,
                "timestamp": ts,
                "captcha_sign": sign,
            }

        try:
            response = requests.post(
                "https://xluser-ssl.xunlei.com/v1/shield/captcha/init",
                json={
                    "action": action,
                    "captcha_token": "",
                    "client_id": self.client_id,
                    "device_id": self.device_id,
                    "redirect_uri": "xlaccsdk01://xunlei.com/callback?state=harbor",
                    "meta": meta,
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": self.user_agent,
                    "x-client-id": self.client_id,
                    "x-device-id": self.device_id,
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("迅雷网盘获取 captcha_token 异常: %s", exc)
            return ""

        captcha_token = data.get("captcha_token") or data.get("data", {}).get("captcha_token", "")
        expires_in = int(data.get("expires_in") or data.get("data", {}).get("expires_in", 300))
        if captcha_token:
            _XUNLEI_CAPTCHA_TOKEN_CACHE[cache_key] = {
                "captcha_token": captcha_token,
                "expires_at": now + expires_in,
            }

        return captcha_token

    def _wait_task(self, task_id: str, retries: int = 30) -> Optional[Dict[str, Any]]:
        """等待转存异步任务完成"""
        if not task_id:
            return None
        for _ in range(retries):
            result = self._request_pan(
                "GET",
                f"https://api-pan.xunlei.com/drive/v1/tasks/{task_id}",
                action="GET:/drive/v1/tasks",
            )
            if result and not result.get("error_code") and result.get("progress") == 100:
                return result
            time.sleep(1)
        return result if "result" in locals() else None

    def _request_pan(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        action: str = "GET:/drive/v1/share",
    ) -> Optional[Dict[str, Any]]:
        """统一发送网盘 API 请求"""
        access_token = self._get_access_token()
        captcha_token = self._get_captcha_token(action)
        if not access_token or not captcha_token:
            return None

        headers = dict(self.session.headers)
        headers["Authorization"] = f"Bearer {access_token}"
        headers["x-captcha-token"] = captcha_token

        try:
            response = self.session.request(
                method,
                url,
                json=payload if payload is not None else None,
                params=params,
                headers=headers,
                timeout=20,
            )
            data = response.json()
            if not response.ok:
                err_msg = data.get("error_description") or data.get("error") or response.text
                logger.error("迅雷网盘接口响应异常 (%s %s): %s", response.status_code, url, err_msg)
            return data
        except Exception as exc:
            logger.error("迅雷网盘接口调用网络异常 (%s): %s", url, exc)
            return None

    def get_user_and_space_info(self) -> Dict[str, Any]:
        """
        获取迅雷网盘用户信息与空间容量配额。
        """
        info = {
            "username": f"UID:{self.user_id}" if self.user_id else "",
            "total_space_bytes": 0,
            "used_space_bytes": 0,
            "vip_status": 0,
        }
        token = self._get_access_token()
        if not token:
            return info

        try:
            about_resp = self._request_pan("GET", "https://api-pan.xunlei.com/drive/v1/about", action="GET:/drive/v1/about")
            if about_resp:
                quota = about_resp.get("quota") or {}
                space = about_resp.get("space") or {}
                info["total_space_bytes"] = int(quota.get("limit") or space.get("total") or space.get("total_bytes") or 0)
                info["used_space_bytes"] = int(quota.get("usage") or space.get("used") or space.get("used_bytes") or 0)
                user = about_resp.get("user") or {}
                name = user.get("name") or user.get("nickname") or ""
                if name:
                    info["username"] = name
        except Exception as e:
            logger.warning(f"迅雷网盘获取空间信息异常: {e}")

        return info

    @staticmethod
    def _parse_share_url(url: str) -> Tuple[str, str]:
        share_match = re.search(r"/s/([^?#/]+)", url)
        pwd_match = re.search(r"pwd=([a-zA-Z0-9]+)", url)
        return (
            share_match.group(1) if share_match else "",
            pwd_match.group(1) if pwd_match else "",
        )
