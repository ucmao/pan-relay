import json
import logging
from typing import Any, Dict, List, Optional

from src.db.system_configs import get_config_value, set_config_value
from src.utils.netdisk_utils import FRONTEND_DISPLAY_NETDISK_OPTIONS

logger = logging.getLogger(__name__)

FRONTEND_DISPLAY_NETDISKS_KEY = "frontend_display_netdisks"
FRONTEND_LINK_MODE_KEY = "frontend_link_mode"
PUBLIC_SEARCH_API_KEY = "public_search_api"
FRONTEND_LINK_MODE_OPTIONS = {"copy", "view"}


def _default_frontend_display_config() -> Dict[str, List[str]]:
    return {"enabled_netdisks": FRONTEND_DISPLAY_NETDISK_OPTIONS.copy()}


def get_frontend_display_netdisk_config() -> Dict[str, List[str]]:
    raw_value = get_config_value(FRONTEND_DISPLAY_NETDISKS_KEY)
    default_config = _default_frontend_display_config()

    if not raw_value:
        return default_config

    try:
        parsed = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        logger.warning("前端网盘显示配置格式无效，已回退到默认值")
        return default_config

    enabled_netdisks = parsed.get("enabled_netdisks", [])
    if not isinstance(enabled_netdisks, list):
        return default_config

    valid_enabled = [name for name in enabled_netdisks if name in FRONTEND_DISPLAY_NETDISK_OPTIONS]
    if not valid_enabled:
        return default_config

    return {"enabled_netdisks": valid_enabled}


def save_frontend_display_netdisk_config(enabled_netdisks: List[str]) -> bool:
    if not isinstance(enabled_netdisks, list):
        return False

    valid_enabled = []
    for name in enabled_netdisks:
        if name in FRONTEND_DISPLAY_NETDISK_OPTIONS and name not in valid_enabled:
            valid_enabled.append(name)

    if not valid_enabled:
        return False

    return set_config_value(
        FRONTEND_DISPLAY_NETDISKS_KEY,
        {"enabled_netdisks": valid_enabled},
    )


def get_allowed_frontend_netdisks() -> set:
    return set(get_frontend_display_netdisk_config()["enabled_netdisks"])


def get_frontend_link_mode() -> str:
    raw_value = get_config_value(FRONTEND_LINK_MODE_KEY)
    if not raw_value:
        return "copy"

    try:
        parsed = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        logger.warning("前端出链模式配置格式无效，已回退到默认值")
        return "copy"

    mode = parsed.get("mode", "copy")
    return mode if mode in FRONTEND_LINK_MODE_OPTIONS else "copy"


def save_frontend_link_mode(mode: str) -> bool:
    if mode not in FRONTEND_LINK_MODE_OPTIONS:
        return False

    return set_config_value(
        FRONTEND_LINK_MODE_KEY,
        {"mode": mode},
    )


def get_public_search_api_config() -> Dict[str, bool]:
    raw_value = get_config_value(PUBLIC_SEARCH_API_KEY)
    if not raw_value:
        return {"enabled": True}

    try:
        parsed = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        logger.warning("公开聚合接口配置格式无效，已回退到默认值")
        return {"enabled": True}

    return {"enabled": bool(parsed.get("enabled", True))}


def is_public_search_api_enabled() -> bool:
    return get_public_search_api_config()["enabled"]


def save_public_search_api_config(enabled: bool) -> bool:
    return set_config_value(
        PUBLIC_SEARCH_API_KEY,
        {"enabled": bool(enabled)},
    )


TG_SEARCH_CONFIG_KEY = "telegram_search_config"
PLUGIN_SETTINGS_KEY = "plugin_settings"


def get_tg_search_config() -> Dict[str, Any]:
    """
    获取 Telegram 频道搜索配置，优先从数据库获取，否则回退至环境变量默认值。
    """
    from src.configs.app_config import (
        TG_SEARCH_ENABLED,
        TG_CHANNELS,
        TG_PROXY,
        TG_SEARCH_TIMEOUT,
        TG_SEARCH_MAX_WORKERS,
    )

    default_config = {
        "enabled": TG_SEARCH_ENABLED,
        "channels": TG_CHANNELS.copy() if isinstance(TG_CHANNELS, list) else ["tgsearchers7", "tgsearchers3", "tgsearchers6"],
        "proxy": TG_PROXY or "",
        "timeout": TG_SEARCH_TIMEOUT or 10,
        "max_workers": TG_SEARCH_MAX_WORKERS or 4,
    }

    raw_value = get_config_value(TG_SEARCH_CONFIG_KEY)
    if not raw_value:
        return default_config

    try:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            return default_config

        channels = [
            str(c).strip().lstrip("@").strip("/")
            for c in parsed.get("channels", default_config["channels"])
            if str(c).strip()
        ]
        return {
            "enabled": bool(parsed.get("enabled", default_config["enabled"])),
            "channels": channels,
            "proxy": str(parsed.get("proxy", default_config["proxy"])).strip(),
            "timeout": max(int(parsed.get("timeout", default_config["timeout"])), 1),
            "max_workers": max(int(parsed.get("max_workers", default_config["max_workers"])), 1),
        }
    except Exception as e:
        logger.warning(f"TG 搜索配置格式无效，已回退到默认值: {e}")
        return default_config


def save_tg_search_config(data: Dict[str, Any]) -> bool:
    """
    保存 Telegram 频道搜索配置至数据库。
    """
    if not isinstance(data, dict):
        return False

    enabled = bool(data.get("enabled", True))
    raw_channels = data.get("channels", [])
    if isinstance(raw_channels, str):
        channels = [
            c.strip().lstrip("@").strip("/")
            for c in raw_channels.replace("\n", ",").split(",")
            if c.strip()
        ]
    elif isinstance(raw_channels, list):
        channels = [
            str(c).strip().lstrip("@").strip("/")
            for c in raw_channels
            if str(c).strip()
        ]
    else:
        channels = []

    proxy = str(data.get("proxy", "")).strip()
    try:
        timeout = max(int(data.get("timeout", 10)), 1)
    except (TypeError, ValueError):
        timeout = 10

    try:
        max_workers = max(int(data.get("max_workers", 4)), 1)
    except (TypeError, ValueError):
        max_workers = 4

    payload = {
        "enabled": enabled,
        "channels": channels,
        "proxy": proxy,
        "timeout": timeout,
        "max_workers": max_workers,
    }

    return set_config_value(TG_SEARCH_CONFIG_KEY, payload)


def get_plugin_settings() -> Dict[str, Dict[str, Any]]:
    """
    获取所有插件的持久化配置状态。
    """
    raw_value = get_config_value(PLUGIN_SETTINGS_KEY)
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as e:
        logger.warning(f"读取插件持久化配置失败: {e}")
        return {}


def save_plugin_status(plugin_name: str, is_enabled: bool) -> bool:
    """
    保存指定插件的启用/禁用状态至数据库。
    """
    settings = get_plugin_settings()
    if plugin_name not in settings:
        settings[plugin_name] = {}
    settings[plugin_name]["is_enabled"] = bool(is_enabled)
    return set_config_value(PLUGIN_SETTINGS_KEY, settings)


def init_default_search_sources():
    """
    首次初始化时自动将默认全量搜索源（API、TG频道、插件）写入数据库。
    若数据库已有配置，则保留数据库现有设置，不覆盖用户的修改或自动禁用状态。
    """
    from src.configs.app_config import (
        TG_CHANNELS,
        TG_PROXY,
        TG_SEARCH_TIMEOUT,
        TG_SEARCH_MAX_WORKERS,
        BASE_DIR,
    )

    # 1. 首次初始化 TG 频道配置至 system_config
    current_tg = get_config_value(TG_SEARCH_CONFIG_KEY)
    if not current_tg:
        save_tg_search_config({
            "enabled": True,
            "channels": TG_CHANNELS,
            "proxy": TG_PROXY,
            "timeout": TG_SEARCH_TIMEOUT,
            "max_workers": TG_SEARCH_MAX_WORKERS,
        })
        logger.info(f"数据库未初始化，已自动写入全量 {len(TG_CHANNELS)} 个默认 TG 频道。")

    # 2. 首次初始化 API 接口至 api_config（若表为空）
    try:
        from src.db.connection import db_cursor
        with db_cursor() as cursor:
            if cursor:
                cursor.execute("SELECT count(*) FROM api_config;")
                row = cursor.fetchone()
                if row and (row[0] if isinstance(row, tuple) else row.get("count(*)", 0)) == 0:
                    cursor.execute("UPDATE api_config SET is_enabled = 1;")
                    logger.info("已完成全量 API 接口默认开启写入。")
    except Exception as e:
        logger.warning(f"初始化 API 接口状态失败: {e}")

    # 3. 首次初始化插件状态至 plugin_settings
    current_plugins = get_config_value(PLUGIN_SETTINGS_KEY)
    if not current_plugins:
        try:
            plugins_dir = os.path.join(BASE_DIR, "src", "plugins")
            plugin_names = []
            if os.path.exists(plugins_dir):
                for fn in os.listdir(plugins_dir):
                    if fn.endswith("_plugin.py") and fn != "base_plugin.py":
                        plugin_names.append(fn[:-10])

            settings = {}
            for p_name in plugin_names:
                settings[p_name] = {"is_enabled": True}
            set_config_value(PLUGIN_SETTINGS_KEY, settings)
            logger.info(f"已完成全量 {len(plugin_names)} 个插件默认开启配置写入。")
        except Exception as e:
            logger.warning(f"初始化插件配置失败: {e}")


