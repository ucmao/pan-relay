import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from src.services.storage_cleanup_service import cleanup_all_storage
from src.services.system_config_service import get_storage_cleanup_config
from src.services.temp_share_service import cleanup_expired_temp_shares

logger = logging.getLogger(__name__)

_scheduler = None


def reload_storage_cleanup_job():
    """重新载入存储清理定时任务"""
    global _scheduler
    if not _scheduler:
        return
    try:
        config = get_storage_cleanup_config()
        hours = max(1, config.get("auto_cleanup_interval_hours", 12))
        _scheduler.add_job(
            cleanup_all_storage,
            trigger="interval",
            hours=hours,
            id="cleanup_all_storage",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(f"已更新存储定时清理任务: 每 {hours} 小时执行一次")
    except Exception as exc:
        logger.error(f"重载存储清理定时任务异常: {exc}")


def start_scheduler():
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    if os.environ.get("WERKZEUG_RUN_MAIN") == "false":
        return None

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        cleanup_expired_temp_shares,
        trigger="interval",
        minutes=30,
        id="cleanup_expired_temp_shares",
        max_instances=1,
        replace_existing=True,
    )

    config = get_storage_cleanup_config()
    hours = max(1, config.get("auto_cleanup_interval_hours", 12))
    scheduler.add_job(
        cleanup_all_storage,
        trigger="interval",
        hours=hours,
        id="cleanup_all_storage",
        max_instances=1,
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"定时任务已启动: 每30分钟清理过期动态分享, 每{hours}小时执行一次存储优化清理")
    _scheduler = scheduler
    return _scheduler
