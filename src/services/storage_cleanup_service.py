import logging
import time
from typing import Any, Dict

from src.db.resources import (
    count_expired_resources,
    delete_resource_by_id,
    list_expired_resources,
)
from src.pan_operator import del_share
from src.services.system_config_service import get_storage_cleanup_config
from src.services.temp_share_service import cleanup_expired_temp_shares

logger = logging.getLogger(__name__)


def cleanup_expired_resources(retention_days: int = 15, limit: int = 100) -> int:
    """
    清理创建时间超过 retention_days 天的转存资源（物理删除网盘文件并清理数据库记录）
    """
    expired_items = list_expired_resources(days=retention_days, limit=limit)
    if not expired_items:
        return 0

    cleaned_count = 0
    logger.info(
        f"开始执行过期转存资源清理，扫描到 {len(expired_items)} 条待清理记录 (保留期: {retention_days}天)..."
    )

    for item in expired_items:
        share_url = item.get("share_link")
        file_id = item.get("file_id")
        resource_id = item.get("id")

        try:
            # 1. 执行网盘物理删除
            del_success = del_share({"share_url": share_url, "file_id": file_id})
            # 无论网盘物理删除是否成功，都删除过期数据库记录，避免堆积
            delete_resource_by_id(resource_id)
            # 联动将 temp_share 记录标记为已删除
            from src.db.temp_shares import mark_temp_share_deleted_by_url_or_file
            mark_temp_share_deleted_by_url_or_file(url=share_url, file_id=file_id)
            cleaned_count += 1
            logger.info(
                f"成功清理过期资源: ID={resource_id}, 名称='{item.get('name')}', 网盘物理删除={del_success}"
            )
        except Exception as exc:
            logger.error(f"清理过期资源异常 (ID={resource_id}): {exc}")

    logger.info(f"过期转存资源清理完成，共清理 {cleaned_count} 条记录")
    return cleaned_count


def cleanup_all_storage() -> Dict[str, Any]:
    """
    统一存储清理入口：按配置自动清理过期临时分享与过期转存资源
    """
    config = get_storage_cleanup_config()
    if not config.get("enabled", True):
        logger.info("存储自动清理策略已禁用，跳过本次执行。")
        return {
            "status": "disabled",
            "temp_shares_cleaned": 0,
            "resources_cleaned": 0,
            "executed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    temp_cleaned = 0
    res_cleaned = 0
    limit = config.get("limit_per_run", 100)

    # 1. 清理过期动态临时分享 (默认 6 小时)
    if config.get("clean_temp_shares", True):
        try:
            temp_cleaned = cleanup_expired_temp_shares(limit=limit)
        except Exception as exc:
            logger.error(f"清理临时分享异常: {exc}")

    # 2. 清理超过保留期的转存资源 (默认 15 天)
    if config.get("clean_old_resources", True):
        retention_days = config.get("retention_days", 15)
        try:
            res_cleaned = cleanup_expired_resources(retention_days=retention_days, limit=limit)
        except Exception as exc:
            logger.error(f"清理过期转存资源异常: {exc}")

    # 3. 释放 SQLite 碎片与磁盘空间
    try:
        from src.db.connection import vacuum_db
        vacuum_db()
    except Exception as exc:
        logger.error(f"清理自动压缩数据库异常: {exc}")

    result = {
        "status": "success",
        "temp_shares_cleaned": temp_cleaned,
        "resources_cleaned": res_cleaned,
        "executed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    logger.info(f"统一存储清理任务执行完毕: {result}")
    return result


def get_storage_stats() -> Dict[str, Any]:
    """获取当前存储概览统计信息"""
    config = get_storage_cleanup_config()
    retention_days = config.get("retention_days", 15)
    expired_res_count = count_expired_resources(days=retention_days)

    return {
        "config": config,
        "expired_resources_count": expired_res_count,
    }
