import logging
from typing import Dict

from src.db.resources import delete_by_file_id, delete_by_share_link
from src.db.temp_shares import (
    create_temp_share_record,
    get_active_temp_share,
    list_expired_temp_shares,
    mark_temp_share_deleted,
    touch_temp_share,
)
from src.pan_operator import create_share, del_share, get_and_validate_credential
from src.utils.netdisk_utils import match_netdisk_link

logger = logging.getLogger(__name__)

TEMP_SHARE_EXPIRE_HOURS = 6
SUPPORTED_DYNAMIC_NETDISKS = {
    "百度网盘": "baidu",
    "夸克网盘": "quark",
    "阿里云盘": "aliyun",
    "UC网盘": "uc",
    "迅雷网盘": "xunlei",
}


def resolve_view_url(title: str, original_url: str, netdisk_name: str = "") -> Dict[str, str]:
    resolved_netdisk_name = netdisk_name or match_netdisk_link(original_url)
    fallback = {
        "url": original_url,
        "mode": "original",
        "netdisk_name": resolved_netdisk_name,
    }

    save_to_key = SUPPORTED_DYNAMIC_NETDISKS.get(resolved_netdisk_name)
    if not save_to_key:
        return fallback

    active_record = get_active_temp_share(original_url, resolved_netdisk_name)
    if active_record:
        touch_temp_share(active_record["id"])
        return {
            "url": active_record["temp_share_url"],
            "mode": "temp_share",
            "netdisk_name": resolved_netdisk_name,
        }

    if not get_and_validate_credential(resolved_netdisk_name):
        return fallback

    share_result = create_share(
        {
            "share_url": original_url,
            "title": title,
            "name": title,
            "cloud_name": resolved_netdisk_name,
            "remark": f"转存自: {original_url}",
            "save_to_netdisk": {save_to_key: True},
        }
    )

    if not share_result:
        return fallback

    new_share_url = share_result.get("share_url") or share_result.get("share_link")
    file_id = share_result.get("file_id")
    if not new_share_url or not file_id:
        return fallback

    create_temp_share_record(
        original_url=original_url,
        title=title,
        cloud_name=resolved_netdisk_name,
        temp_share_url=new_share_url,
        file_id=file_id,
        expires_in_hours=TEMP_SHARE_EXPIRE_HOURS,
    )

    return {
        "url": new_share_url,
        "mode": "temp_share",
        "netdisk_name": resolved_netdisk_name,
    }


def cleanup_expired_temp_shares(limit: int = 50) -> int:
    expired_records = list_expired_temp_shares(limit=limit)
    cleaned_count = 0

    for record in expired_records:
        temp_url = record.get("temp_share_url")
        file_id = record.get("file_id")
        try:
            del_share(
                {
                    "share_url": temp_url,
                    "file_id": file_id,
                    "cloud_name": record.get("cloud_name"),
                }
            )
        except Exception as exc:
            logger.warning(f"删除物理网盘分享失败 (id={record['id']}): {exc}")

        # 无论物理删除返回何种结果，均同步清理本地数据库过期记录（temp_share 与 resources）
        mark_temp_share_deleted(record["id"])
        if temp_url:
            delete_by_share_link(temp_url)
        if file_id:
            delete_by_file_id(file_id)
        cleaned_count += 1

    if cleaned_count:
        logger.info(f"本次清理过期临时分享及关联资源数量: {cleaned_count}")
    return cleaned_count
