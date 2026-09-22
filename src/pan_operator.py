import json
import logging
import threading
import time
from typing import Any, Dict, List

from src.clients import (
    AliyunPanClient,
    BaiduPanClient,
    QuarkPanClient,
    UcPanClient,
    XunleiPanClient,
)
from src.db.resources import (
    insert_resource,
    delete_by_share_link,
    delete_by_file_id,
    update_share_link,
    get_resource_by_share_link,
)
from src.db.credentials import get_cookie_by_cloud_name
from src.services.link_checker import check_link, STATE_BAD, STATE_LOCKED
from src.utils.netdisk_utils import match_netdisk_link, extract_password_from_url

logger = logging.getLogger(__name__)

# 并发转存防击穿互斥锁表与临时转存结果缓存 (URL -> Result Record)
_TRANSFER_LOCKS: Dict[str, threading.Lock] = {}
_TRANSFER_LOCKS_MUTEX = threading.Lock()
_TRANSFERRED_URL_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_transfer_lock(url: str) -> threading.Lock:
    clean_url = str(url or "").strip()
    with _TRANSFER_LOCKS_MUTEX:
        if clean_url not in _TRANSFER_LOCKS:
            _TRANSFER_LOCKS[clean_url] = threading.Lock()
        return _TRANSFER_LOCKS[clean_url]

# --- 工具函数：凭证校验 ---

def _parse_xunlei_credential(raw_credential: str) -> Dict[str, str]:
    try:
        parsed = json.loads(raw_credential)
        if isinstance(parsed, dict):
            return {
                "refresh_token": str(parsed.get("refresh_token", "")).strip(),
                "captcha_sign": str(parsed.get("captcha_sign", "")).strip(),
                "user_id": str(parsed.get("user_id", "")).strip(),
            }
    except json.JSONDecodeError:
        return {}
    return {}


def get_and_validate_credential(netdisk_type: str) -> Any:
    """
    统一获取并校验云盘凭证。
    凭证可能是 Cookie，也可能是 refresh_token。
    """
    credential = get_cookie_by_cloud_name(netdisk_type)
    
    if not credential:
        logger.error(f"[{netdisk_type}] 操作失败：数据库中未配置凭证。")
        return ""

    if netdisk_type == "迅雷网盘":
        parsed_credential = _parse_xunlei_credential(credential)
        required_fields = ("refresh_token", "captcha_sign", "user_id")
        if not all(parsed_credential.get(field) for field in required_fields):
            logger.error(f"[{netdisk_type}] 操作失败：凭证缺少 refresh_token/captcha_sign/user_id。")
            return {}
        return parsed_credential
    
    min_length_map = {
        "夸克网盘": 50,
        "百度网盘": 50,
        "UC网盘": 50,
        "阿里云盘": 20,
    }
    min_length = min_length_map.get(netdisk_type, 20)

    if len(credential) < min_length:
        logger.error(f"[{netdisk_type}] 操作失败：凭证长度不足({len(credential)})，可能已失效。")
        return ""
        
    return credential


def _normalize_file_id(file_id: Any) -> Any:
    if isinstance(file_id, list):
        return json.dumps(file_id, ensure_ascii=False)
    return file_id


def _parse_file_id(file_id: Any) -> Any:
    if isinstance(file_id, list):
        return file_id
    if not isinstance(file_id, str):
        return file_id

    file_id = file_id.strip()
    if not file_id:
        return file_id

    if file_id.startswith("["):
        try:
            parsed = json.loads(file_id)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return file_id
    return file_id

# --- 核心逻辑：通用网盘操作处理器 ---

def _handle_netdisk_operation(client_class, client_credential, share_url, to_pdir_path: str = '/', 
                              operation: str = 'store', file_id: str = None):
    """
    通用网盘操作处理器（转存或删除）。
    """
    client = client_class(client_credential)
    try:
        if operation == 'store':
            # 执行转存流程
            new_file_id, file_name, new_share_url = client.store(share_url, to_pdir_path)

            if not new_file_id or not new_share_url:
                logger.error(f"[{client_class.__name__}] 转存或分享接口返回空数据")
                return None, None, None

            logger.info(f"[{client_class.__name__}] 处理成功: {file_name}")
            time.sleep(0.5)  # 避免频率过快
            return new_file_id, file_name, new_share_url

        elif operation == 'delete':
            if not file_id:
                logger.error(f"[{client_class.__name__}] 删除操作缺失 file_id")
                return False

            parsed_file_id = _parse_file_id(file_id)
            # 百度删除通常需要路径列表，阿里/UC 需要列表，夸克通常是单个 ID
            if client_class == BaiduPanClient:
                target = [parsed_file_id] if isinstance(parsed_file_id, str) else parsed_file_id
            elif client_class in (AliyunPanClient, UcPanClient, XunleiPanClient):
                target = parsed_file_id if isinstance(parsed_file_id, list) else [parsed_file_id]
            else:
                target = parsed_file_id
            status = client.del_file(target)
            return status

    except Exception as e:
        logger.exception(f"[{client_class.__name__}] 接口调用异常: {e}")
        return (None, None, None) if operation == 'store' else False

def _resolve_target_dir(client_class, client_credential, target_dir_name: str) -> str:
    """
    根据配置的目录名称与网盘类型，解析出对应的目标路径/文件夹 ID。
    """
    if not target_dir_name or target_dir_name.strip() in ("", "/"):
        return "/" if client_class == BaiduPanClient else ("root" if client_class == AliyunPanClient else "0")

    clean_dir = target_dir_name.strip().strip("/")
    if client_class == BaiduPanClient:
        return f"/{clean_dir}"

    try:
        client = client_class(client_credential)
        if hasattr(client, "get_or_create_dir"):
            return client.get_or_create_dir(clean_dir)
    except Exception as exc:
        logger.error(f"[{client_class.__name__}] 解析目标转存目录失败: {exc}")

    return "root" if client_class == AliyunPanClient else "0"


# --- 业务接口：创建分享 ---

def create_share(share_data):
    """
    创建/转存分享链接（支持并发互斥锁防击穿）
    """
    try:
        share_url = (share_data.get('share_url') or '').strip()
        if not share_url:
            return share_data if 'id' not in share_data else None

        title = share_data.get('title', f"资源_{int(time.time())}")
        save_to_netdisk = share_data.get('save_to_netdisk', {})
        has_id = 'id' in share_data
        share_id = share_data.get('id')

        # 1. 匹配网盘类型
        netdisk_type = match_netdisk_link(share_url)
        config_map = {
            "夸克网盘": {"class": QuarkPanClient, "enabled": save_to_netdisk.get('quark', False)},
            "百度网盘": {"class": BaiduPanClient, "enabled": save_to_netdisk.get('baidu', False)},
            "阿里云盘": {"class": AliyunPanClient, "enabled": save_to_netdisk.get('aliyun', False)},
            "UC网盘": {"class": UcPanClient, "enabled": save_to_netdisk.get('uc', False)},
            "迅雷网盘": {"class": XunleiPanClient, "enabled": save_to_netdisk.get('xunlei', False)},
        }
        
        conf = config_map.get(netdisk_type)

        # 2. 判断是否需要转存
        if not conf or not conf["enabled"]:
            logger.info(f"无需转存操作，跳过。类型: {netdisk_type}")
            return share_data if not has_id else None

        # 3. 获取并校验凭证
        client_credential = get_and_validate_credential(netdisk_type)
        if not client_credential:
            return share_data if not has_id else None

        # 使用 URL 互斥锁防止高并发重复转存同一资源 (防击穿)
        lock = _get_transfer_lock(share_url)
        with lock:
            # Double-check: 若无 id 的搜索发现场景，先检查内存缓存或数据库是否已被其他并发线程转存成功
            if not has_id:
                if share_url in _TRANSFERRED_URL_CACHE:
                    cached = _TRANSFERRED_URL_CACHE[share_url]
                    target_link = cached.get("share_link") or cached.get("share_url")
                    if target_link:
                        existing = get_resource_by_share_link(target_link)
                        if existing and existing.get("file_id"):
                            logger.info(f"并发防击穿: 资源已由其他线程转存完成 (命中内存缓存: {share_url})")
                            return cached
                    _TRANSFERRED_URL_CACHE.pop(share_url, None)

                existing = get_resource_by_share_link(share_url)
                if existing and existing.get("file_id") and existing.get("share_link"):
                    logger.info(f"并发防击穿: 资源已由其他线程转存入库 ({share_url})")
                    _TRANSFERRED_URL_CACHE[share_url] = existing
                    return existing

            # 3.1 前置免登录测活检查 (避免死链无效提交给网盘造成风控或报错)
            check_res = check_link(share_url, password=share_data.get("password"), disk_type=netdisk_type)
            if check_res.get("state") == STATE_BAD:
                logger.warning(
                    f"[{netdisk_type}] 转存前检测到链接已失效/违规，终止转存: {check_res.get('summary')} ({share_url})"
                )
                return None
            if check_res.get("state") == STATE_LOCKED:
                pwd = share_data.get("password") or extract_password_from_url(share_url)
                if not pwd:
                    logger.warning(
                        f"[{netdisk_type}] 转存前检测到链接需要提取码但未提供密码，终止转存 ({share_url})"
                    )
                    return None

            # 4. 执行转存（读取系统配置的目标转存目录）
            from src.services.system_config_service import get_transfer_target_dir
            target_dir_name = get_transfer_target_dir()
            target_pdir = _resolve_target_dir(conf["class"], client_credential, target_dir_name)

            new_file_id, file_name, new_share_url = _handle_netdisk_operation(
                client_class=conf["class"],
                client_credential=client_credential,
                share_url=share_url,
                to_pdir_path=target_pdir,
                operation='store'
            )

            if not new_share_url:
                return share_data if not has_id else None

            # 5. 数据库同步与缓存更新
            if has_id:
                # 场景 A: 已有记录更新链接
                update_share_link(share_id, new_share_url, new_file_id)
                updated_record = {
                    'id': share_id,
                    'file_id': _normalize_file_id(new_file_id),
                    'name': share_data.get('name') or share_data.get('title') or file_name or title,
                    'share_link': new_share_url,
                    'share_url': new_share_url,
                    'cloud_name': share_data.get('cloud_name') or netdisk_type,
                    'is_replaced': 1,
                }
                _TRANSFERRED_URL_CACHE[share_url] = updated_record
                return updated_record
            else:
                # 场景 B: 转存新资源，统一持久化入库到 resources (我的资源管理)
                record_name = share_data.get('name') or share_data.get('title') or file_name or title or "未命名资源"
                record_cloud = share_data.get('cloud_name') or netdisk_type
                record_type = share_data.get('resource_type') or share_data.get('type') or ""
                record_remarks = share_data.get('remark') or share_data.get('remarks') or f"转存自: {share_url}"

                new_record = {
                    'file_id': _normalize_file_id(new_file_id),
                    'name': record_name,
                    'share_link': new_share_url,
                    'share_url': new_share_url,
                    'cloud_name': record_cloud,
                    'type': record_type,
                    'remarks': record_remarks,
                    'is_replaced': 1,
                    'health_status': 'ok',
                }
                new_id = insert_resource(new_record)
                if new_id:
                    new_record['id'] = new_id

                _TRANSFERRED_URL_CACHE[share_url] = new_record
                return new_record

    except Exception as e:
        logger.exception(f"create_share 运行异常: {e}")
        return share_data if 'id' not in share_data else None

# --- 业务接口：删除分享 ---

def del_share(share_data):
    """
    删除分享及其对应的网盘文件
    """
    try:
        share_url = share_data.get('share_url')
        file_id = share_data.get('file_id')

        if not share_url and not file_id:
            return False

        # 1. 获取凭证
        netdisk_type = match_netdisk_link(share_url or '') if share_url else ""
        if not netdisk_type and share_data.get("cloud_name"):
            netdisk_type = share_data.get("cloud_name")

        client_credential = get_and_validate_credential(netdisk_type) if netdisk_type else None
        if not client_credential:
            logger.warning(f"无法获取网盘凭证或未匹配到网盘类型: {netdisk_type} ({share_url})")
            # 即使无网盘凭证，也尝试清理本地数据库关联记录
            if share_url:
                delete_by_share_link(share_url)
            if file_id:
                delete_by_file_id(_normalize_file_id(file_id))
            return False

        # 2. 执行物理删除
        client_map = {
            "百度网盘": BaiduPanClient,
            "夸克网盘": QuarkPanClient,
            "阿里云盘": AliyunPanClient,
            "UC网盘": UcPanClient,
            "迅雷网盘": XunleiPanClient,
        }
        client_class = client_map.get(netdisk_type)
        if not client_class:
            logger.warning(f"未支持删除操作的网盘类型: {netdisk_type}")
            if share_url:
                delete_by_share_link(share_url)
            if file_id:
                delete_by_file_id(_normalize_file_id(file_id))
            return False

        status = _handle_netdisk_operation(
            client_class=client_class,
            client_credential=client_credential,
            share_url=share_url,
            operation='delete',
            file_id=file_id
        )

        # 3. 逻辑删除（数据库记录清理：按 share_url 与 file_id 清理 resources 表）
        if status:
            if share_url:
                delete_by_share_link(share_url)
            if file_id:
                delete_by_file_id(_normalize_file_id(file_id))
            with _TRANSFER_LOCKS_MUTEX:
                keys_to_del = [
                    k for k, v in _TRANSFERRED_URL_CACHE.items()
                    if k == share_url
                    or (isinstance(v, dict) and (v.get("share_link") == share_url or v.get("share_url") == share_url or (file_id and v.get("file_id") == file_id)))
                ]
                for k in keys_to_del:
                    _TRANSFERRED_URL_CACHE.pop(k, None)
            logger.info(f"成功清理 {netdisk_type} 资源及其数据库记录 (URL={share_url}, file_id={file_id})")
            return True
        
        return False

    except Exception as e:
        logger.exception(f"del_share 运行异常: {e}")
        return False
