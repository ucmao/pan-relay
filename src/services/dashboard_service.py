import logging
import os
import sys
from typing import Any, Dict

from src.configs.app_config import SQLITE_DB_PATH
from src.db.connection import db_cursor
from src.services.plugin_manager import plugin_manager
from src.routes.system_config_routes import _build_dynamic_transfer_statuses
from src.services.system_config_service import (
    get_allow_excel_download_config,
    get_frontend_link_mode,
    get_public_search_api_config,
)

logger = logging.getLogger(__name__)


def get_dashboard_summary() -> Dict[str, Any]:
    """
    获取后台工作台仪表盘所需的所有统计指标与系统快照数据
    """
    summary = {
        "resources": {
            "total_count": 0,
            "replaced_count": 0,
            "cloud_distribution": [],
            "recent_items": [],
        },
        "sources": {
            "api": {
                "total_count": 0,
                "enabled_count": 0,
                "healthy_count": 0,
                "unhealthy_count": 0,
                "avg_response_time_ms": 0,
            },
            "plugins": {
                "total_count": 0,
                "enabled_count": 0,
                "items": [],
            },
            "telegram": {
                "total_count": 0,
                "enabled_count": 0,
                "healthy_count": 0,
            },
            "overall_health_rate": 100,
        },
        "credentials": {
            "statuses": [],
            "summary": {
                "enabled_count": 0,
                "total_count": 5,
            },
        },
        "system": {
            "frontend_link_mode": "direct",
            "public_search_api_enabled": True,
            "allow_excel_download_enabled": True,
            "db_size_mb": 0.0,
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
        },
    }

    # 1. 资源库统计
    with db_cursor(as_dict=True) as cursor:
        if cursor:
            try:
                # 总数与替换数
                cursor.execute("SELECT COUNT(*) AS total FROM resources")
                row = cursor.fetchone()
                summary["resources"]["total_count"] = row["total"] if row else 0

                cursor.execute("SELECT COUNT(*) AS replaced FROM resources WHERE is_replaced = 1")
                row = cursor.fetchone()
                summary["resources"]["replaced_count"] = row["replaced"] if row else 0

                # 云盘分布
                cursor.execute(
                    "SELECT cloud_name, COUNT(*) AS count FROM resources GROUP BY cloud_name ORDER BY count DESC"
                )
                summary["resources"]["cloud_distribution"] = cursor.fetchall() or []

                # 最新资源 5 条
                cursor.execute(
                    "SELECT id, name, share_link, cloud_name, type, created_at FROM resources ORDER BY id DESC LIMIT 5"
                )
                recent = cursor.fetchall() or []
                for item in recent:
                    if item.get("created_at"):
                        item["created_at"] = str(item["created_at"])
                summary["resources"]["recent_items"] = recent

            except Exception as e:
                logger.error(f"仪表盘获取资源库数据失败: {e}")

    # 2. 检索源统计 (API 接口 + Telegram 频道)
    with db_cursor(as_dict=True) as cursor:
        if cursor:
            try:
                # API 检索源
                cursor.execute("SELECT COUNT(*) AS total FROM api_config")
                summary["sources"]["api"]["total_count"] = cursor.fetchone()["total"]

                cursor.execute("SELECT COUNT(*) AS enabled FROM api_config WHERE is_enabled = 1")
                summary["sources"]["api"]["enabled_count"] = cursor.fetchone()["enabled"]

                cursor.execute("SELECT COUNT(*) AS healthy FROM api_config WHERE status = 'healthy'")
                summary["sources"]["api"]["healthy_count"] = cursor.fetchone()["healthy"]

                cursor.execute("SELECT COUNT(*) AS unhealthy FROM api_config WHERE status = 'unhealthy'")
                summary["sources"]["api"]["unhealthy_count"] = cursor.fetchone()["unhealthy"]

                cursor.execute(
                    "SELECT AVG(response_time_ms) AS avg_ms FROM api_config WHERE is_enabled = 1 AND response_time_ms > 0"
                )
                avg_row = cursor.fetchone()
                summary["sources"]["api"]["avg_response_time_ms"] = (
                    round(avg_row["avg_ms"], 1) if avg_row and avg_row["avg_ms"] is not None else 0
                )

                # Telegram 频道
                cursor.execute("SELECT COUNT(*) AS total FROM telegram_channel")
                summary["sources"]["telegram"]["total_count"] = cursor.fetchone()["total"]

                cursor.execute("SELECT COUNT(*) AS enabled FROM telegram_channel WHERE is_enabled = 1")
                summary["sources"]["telegram"]["enabled_count"] = cursor.fetchone()["enabled"]

                cursor.execute("SELECT COUNT(*) AS healthy FROM telegram_channel WHERE health_status = 'success'")
                summary["sources"]["telegram"]["healthy_count"] = cursor.fetchone()["healthy"]

            except Exception as e:
                logger.error(f"仪表盘获取检索源数据失败: {e}")

    # 3. 插件统计
    all_plugins = plugin_manager.get_all_plugins()
    enabled_plugins = plugin_manager.get_enabled_plugins()
    summary["sources"]["plugins"]["total_count"] = len(all_plugins)
    summary["sources"]["plugins"]["enabled_count"] = len(enabled_plugins)
    summary["sources"]["plugins"]["items"] = [
        {
            "name": p.name,
            "display_name": p.display_name,
            "version": p.version,
            "is_enabled": p.is_enabled,
        }
        for p in all_plugins
    ]

    # 计算整体检索源健康率 (%)
    total_active_sources = (
        summary["sources"]["api"]["enabled_count"]
        + summary["sources"]["plugins"]["enabled_count"]
        + summary["sources"]["telegram"]["enabled_count"]
    )
    total_healthy_sources = (
        summary["sources"]["api"]["healthy_count"]
        + summary["sources"]["plugins"]["enabled_count"]
        + summary["sources"]["telegram"]["healthy_count"]
    )
    if total_active_sources > 0:
        summary["sources"]["overall_health_rate"] = round(
            (total_healthy_sources / total_active_sources) * 100, 1
        )
    else:
        summary["sources"]["overall_health_rate"] = 100.0

    # 4. 云盘凭证与自动转存状态
    try:
        cred_status = _build_dynamic_transfer_statuses()
        summary["credentials"]["statuses"] = cred_status.get("statuses", [])
        summary["credentials"]["summary"] = cred_status.get("summary", {"enabled_count": 0, "total_count": 5})
    except Exception as e:
        logger.error(f"仪表盘获取凭证状态失败: {e}")

    # 5. 系统开关与文件体积
    try:
        summary["system"]["frontend_link_mode"] = get_frontend_link_mode()
        summary["system"]["public_search_api_enabled"] = get_public_search_api_config().get("enabled", True)
        summary["system"]["allow_excel_download_enabled"] = get_allow_excel_download_config().get("enabled", True)

        if os.path.exists(SQLITE_DB_PATH):
            db_size_bytes = os.path.getsize(SQLITE_DB_PATH)
            summary["system"]["db_size_mb"] = round(db_size_bytes / (1024 * 1024), 2)
    except Exception as e:
        logger.error(f"仪表盘获取系统配置失败: {e}")

    return summary
