import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from src.services.temp_share_service import cleanup_expired_temp_shares

logger = logging.getLogger(__name__)

_scheduler = None


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
    scheduler.start()
    logger.info("定时清理任务已启动: 每30分钟清理一次过期动态分享")
    _scheduler = scheduler
    return _scheduler
