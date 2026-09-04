import json
import logging
from typing import Any, Dict, List

from src.db.system_configs import get_config_value, set_config_value
from src.utils.netdisk_utils import FRONTEND_DISPLAY_NETDISK_OPTIONS

logger = logging.getLogger(__name__)

FRONTEND_DISPLAY_NETDISKS_KEY = "frontend_display_netdisks"
FRONTEND_LINK_MODE_KEY = "frontend_link_mode"
PUBLIC_SEARCH_API_KEY = "public_search_api"
ALLOW_EXCEL_DOWNLOAD_KEY = "allow_excel_download"
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


def get_allow_excel_download_config() -> Dict[str, bool]:
    raw_value = get_config_value(ALLOW_EXCEL_DOWNLOAD_KEY)
    if not raw_value:
        return {"enabled": True}

    try:
        parsed = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Excel 下载按钮配置格式无效，已回退到默认值")
        return {"enabled": True}

    return {"enabled": bool(parsed.get("enabled", True))}


def is_excel_download_enabled() -> bool:
    return get_allow_excel_download_config()["enabled"]


def save_allow_excel_download_config(enabled: bool) -> bool:
    return set_config_value(
        ALLOW_EXCEL_DOWNLOAD_KEY,
        {"enabled": bool(enabled)},
    )


SENSITIVE_WORDS_CONFIG_KEY = "sensitive_words_config"
DEFAULT_SENSITIVE_WORDS = [
    "外挂", "辅助透视", "破解工具", "博彩", "赌博", "色情", "卡密", "代刷"
]


def get_sensitive_words_config() -> Dict[str, Any]:
    """获取敏感词过滤全局设置与词库"""
    default_config = {
        "enabled": True,
        "input_enabled": True,
        "output_enabled": True,
        "words": DEFAULT_SENSITIVE_WORDS.copy(),
    }
    raw_value = get_config_value(SENSITIVE_WORDS_CONFIG_KEY)
    if not raw_value:
        return default_config
    try:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            return default_config
        words = parsed.get("words", default_config["words"])
        if isinstance(words, str):
            words = [w.strip() for w in words.replace("\r\n", "\n").split("\n") if w.strip()]
        elif not isinstance(words, list):
            words = default_config["words"]
        return {
            "enabled": bool(parsed.get("enabled", True)),
            "input_enabled": bool(parsed.get("input_enabled", True)),
            "output_enabled": bool(parsed.get("output_enabled", True)),
            "words": [str(w).strip().lower() for w in words if str(w).strip()],
        }
    except Exception as e:
        logger.warning(f"读取敏感词配置失败，回退默认配置: {e}")
        return default_config


def save_sensitive_words_config(config_data: Dict[str, Any]) -> bool:
    """保存敏感词过滤配置并触发算法缓存重载"""
    if not isinstance(config_data, dict):
        return False
    current = get_sensitive_words_config()
    enabled = bool(config_data.get("enabled", current["enabled"]))
    input_enabled = bool(config_data.get("input_enabled", current["input_enabled"]))
    output_enabled = bool(config_data.get("output_enabled", current["output_enabled"]))
    words_raw = config_data.get("words", current["words"])
    if isinstance(words_raw, str):
        words = [w.strip().lower() for w in words_raw.replace("\r\n", "\n").split("\n") if w.strip()]
    elif isinstance(words_raw, list):
        words = [str(w).strip().lower() for w in words_raw if str(w).strip()]
    else:
        words = current["words"]

    unique_words = list(dict.fromkeys(words))
    payload = {
        "enabled": enabled,
        "input_enabled": input_enabled,
        "output_enabled": output_enabled,
        "words": unique_words,
    }
    success = set_config_value(SENSITIVE_WORDS_CONFIG_KEY, payload)
    if success:
        try:
            from src.services.sensitive_word_service import reload_sensitive_words_cache
            reload_sensitive_words_cache()
        except Exception as e:
            logger.warning(f"重载敏感词缓存失败: {e}")
    return success


TG_SEARCH_CONFIG_KEY = "telegram_search_settings"
PLUGIN_SETTINGS_KEY = "plugin_settings"


def get_tg_search_config() -> Dict[str, Any]:
    """获取 Telegram 抓取引擎的全局设置。"""
    from src.configs.app_config import (
        TG_SEARCH_ENABLED,
        TG_PROXY,
        TG_SEARCH_TIMEOUT,
        TG_SEARCH_MAX_WORKERS,
    )

    default_config = {
        "enabled": TG_SEARCH_ENABLED,
        "proxy": TG_PROXY or "",
        "timeout": TG_SEARCH_TIMEOUT or 10,
        "max_workers": TG_SEARCH_MAX_WORKERS or 4,
    }

    raw_value = get_config_value(TG_SEARCH_CONFIG_KEY)
    if not raw_value:
        return default_config
    try:
        parsed = json.loads(raw_value)
        return {
            "enabled": bool(parsed.get("enabled", default_config["enabled"])),
            "proxy": str(parsed.get("proxy", default_config["proxy"])).strip(),
            "timeout": max(int(parsed.get("timeout", default_config["timeout"])), 1),
            "max_workers": max(int(parsed.get("max_workers", default_config["max_workers"])), 1),
        }
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        logger.warning("TG 搜索设置格式无效，已回退到默认值: %s", error)
        return default_config


def save_tg_search_config(data: Dict[str, Any]) -> bool:
    """保存 Telegram 抓取引擎的全局设置。"""
    if not isinstance(data, dict):
        return False

    current = get_tg_search_config()
    enabled = bool(data.get("enabled", current.get("enabled", True)))
    proxy = str(data.get("proxy", current.get("proxy", ""))).strip()
    try:
        timeout = max(int(data.get("timeout", current.get("timeout", 10))), 1)
    except (TypeError, ValueError):
        timeout = 10

    try:
        max_workers = max(int(data.get("max_workers", current.get("max_workers", 4))), 1)
    except (TypeError, ValueError):
        max_workers = 4

    payload = {
        "enabled": enabled,
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


def save_plugin_health(plugin_name: str, health_data: Dict[str, Any]) -> bool:
    """
    保存指定插件的客观健康度数据（status, latency_ms, count, message, checked_at）至数据库。
    """
    import time
    settings = get_plugin_settings()
    if plugin_name not in settings:
        settings[plugin_name] = {}
    settings[plugin_name]["health"] = {
        "status": health_data.get("status", "unknown"),
        "latency_ms": health_data.get("latency_ms", 0),
        "result_count": health_data.get("count", 0),
        "message": health_data.get("message", ""),
        "checked_at": health_data.get("checked_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
    }
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
        TG_DISABLED_CHANNELS,
        DEFAULT_PLUGIN_SETTINGS,
    )

    # 1. 首次初始化 TG 全局设置与频道表
    current_tg = get_config_value(TG_SEARCH_CONFIG_KEY)
    if not current_tg:
        save_tg_search_config({
            "enabled": True,
            "proxy": TG_PROXY,
            "timeout": TG_SEARCH_TIMEOUT,
            "max_workers": TG_SEARCH_MAX_WORKERS,
        })
        try:
            from src.db.telegram_channels import seed_channels
            seeded_count = seed_channels(TG_CHANNELS, TG_DISABLED_CHANNELS)
            if seeded_count:
                logger.info("已写入 %d 个默认 TG 频道。", seeded_count)
        except Exception as error:
            logger.warning("初始化 TG 频道失败: %s", error)

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

    # 3. 首次初始化插件状态至 plugin_settings，使用发布前健康检测生成的默认值。
    current_plugins = get_config_value(PLUGIN_SETTINGS_KEY)
    if not current_plugins:
        try:
            settings = {
                name: {"is_enabled": bool(is_enabled)}
                for name, is_enabled in DEFAULT_PLUGIN_SETTINGS.items()
            }
            set_config_value(PLUGIN_SETTINGS_KEY, settings)
            enabled_count = sum(1 for item in settings.values() if item["is_enabled"])
            logger.info("已写入 %d 个插件默认状态，其中 %d 个启用。", len(settings), enabled_count)
        except Exception as e:
            logger.warning(f"初始化插件配置失败: {e}")
