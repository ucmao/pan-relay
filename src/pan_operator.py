import json
import logging
import time
from typing import Any, Dict, List

from src.clients import (
    AliyunPanClient,
    BaiduPanClient,
    QuarkPanClient,
    UcPanClient,
    XunleiPanClient,
)
from src.db.resources import insert_resource, delete_by_share_link, update_share_link
from src.db.credentials import get_cookie_by_cloud_name
from src.utils.netdisk_utils import match_netdisk_link

logger = logging.getLogger(__name__)

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
            if client_class == Baidu:
                target = [parsed_file_id] if isinstance(parsed_file_id, str) else parsed_file_id
            elif client_class in (AliyunDrive, UcDrive, XunleiDrive):
                target = parsed_file_id if isinstance(parsed_file_id, list) else [parsed_file_id]
            else:
                target = parsed_file_id
            status = client.del_file(target)
            return status

    except Exception as e:
        logger.exception(f"[{client_class.__name__}] 接口调用异常: {e}")
        return (None, None, None) if operation == 'store' else False

# --- 业务接口：创建分享 ---

def create_share(share_data):
    """
    创建/转存分享链接
    """
    try:
        share_url = share_data.get('share_url')
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

        # 4. 执行转存
        new_file_id, file_name, new_share_url = _handle_netdisk_operation(
            client_class=conf["class"],
            client_credential=client_credential,
            share_url=share_url,
            operation='store'
        )

        if not new_share_url:
            return share_data if not has_id else None

        # 5. 数据库同步
        if has_id:
            # 场景 A: 已有记录更新链接
            update_share_link(share_id, new_share_url, new_file_id)
            return None
        else:
            # 场景 B: 搜索发现新资源，入库并返回新对象
            if any(key in share_data for key in ['name', 'cloud_name']):
                new_record = {
                    'file_id': new_file_id,
                    'name': share_data.get('name', file_name or title),
                    'share_link': new_share_url,
                    'cloud_name': netdisk_type,
                    'type': share_data.get('resource_type'),
                    'remarks': share_data.get('remark')
                }
                new_record['file_id'] = _normalize_file_id(new_record['file_id'])
                insert_resource(new_record)
                return new_record
            return {"share_url": new_share_url, "file_id": _normalize_file_id(new_file_id)}

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

        if not share_url:
            return False

        # 1. 获取凭证
        netdisk_type = match_netdisk_link(share_url)
        client_credential = get_and_validate_credential(netdisk_type)
        if not client_credential:
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
            return False
        status = _handle_netdisk_operation(
            client_class=client_class,
            client_credential=client_credential,
            share_url=share_url,
            operation='delete',
            file_id=file_id
        )

        # 3. 逻辑删除（数据库记录清理）
        if status:
            delete_by_share_link(share_url)
            logger.info(f"成功清理 {netdisk_type} 资源及其数据库记录")
            return True
        
        return False

    except Exception as e:
        logger.exception(f"del_share 运行异常: {e}")
        return False
