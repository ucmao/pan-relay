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
    "博彩", "赌博", "百家乐", "新葡京",
    "色情", "黄片", "成人视频",
    "卡密", "代刷", "接码", "撞库",
    "外挂", "辅助透视", "透视挂",
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


SEARCH_SCHEDULER_CONFIG_KEY = "search_scheduler_settings"
PLUGIN_SETTINGS_KEY = "plugin_settings"


def get_search_scheduler_config() -> Dict[str, Any]:
    """获取三类检索源的调度参数。"""
    from src.configs.app_config import (
        API_SEARCH_MAX_WORKERS,
        API_SEARCH_TIMEOUT,
        PLUGIN_SEARCH_MAX_WORKERS,
        PLUGIN_SEARCH_TIMEOUT,
        TG_SEARCH_ENABLED,
        TG_PROXY,
        TG_SEARCH_TIMEOUT,
        TG_SEARCH_MAX_WORKERS,
    )

    default_config = {
        "api": {"timeout": API_SEARCH_TIMEOUT, "max_workers": API_SEARCH_MAX_WORKERS},
        "tg": {"enabled": TG_SEARCH_ENABLED, "proxy": TG_PROXY or "", "timeout": TG_SEARCH_TIMEOUT, "max_workers": TG_SEARCH_MAX_WORKERS},
        "plugin": {"timeout": PLUGIN_SEARCH_TIMEOUT, "max_workers": PLUGIN_SEARCH_MAX_WORKERS},
    }
    raw_value = get_config_value(SEARCH_SCHEDULER_CONFIG_KEY)
    if not raw_value:
        return default_config
    try:
        parsed = json.loads(raw_value)
        return {
            "api": {"timeout": max(int(parsed["api"].get("timeout", default_config["api"]["timeout"])), 1), "max_workers": max(int(parsed["api"].get("max_workers", default_config["api"]["max_workers"])), 1)},
            "tg": {"enabled": bool(parsed["tg"].get("enabled", default_config["tg"]["enabled"])), "proxy": str(parsed["tg"].get("proxy", default_config["tg"]["proxy"])).strip(), "timeout": max(int(parsed["tg"].get("timeout", default_config["tg"]["timeout"])), 1), "max_workers": max(int(parsed["tg"].get("max_workers", default_config["tg"]["max_workers"])), 1)},
            "plugin": {"timeout": max(int(parsed["plugin"].get("timeout", default_config["plugin"]["timeout"])), 1), "max_workers": max(int(parsed["plugin"].get("max_workers", default_config["plugin"]["max_workers"])), 1)},
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        logger.warning("搜索调度设置格式无效，已回退到默认值: %s", error)
        return default_config


def save_search_scheduler_config(data: Dict[str, Any]) -> bool:
    """保存三类检索源的调度参数。"""
    if not isinstance(data, dict):
        return False
    return set_config_value(SEARCH_SCHEDULER_CONFIG_KEY, data)


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
        TG_PROXY,
        TG_SEARCH_TIMEOUT,
        TG_SEARCH_MAX_WORKERS,
    )
    from src.configs.preset_loader import (
        load_preset_api_configs,
        load_preset_tg_channels,
        load_preset_plugin_settings,
    )

    # 1. 首次初始化 TG 全局设置与频道表
    current_scheduler = get_config_value(SEARCH_SCHEDULER_CONFIG_KEY)
    if not current_scheduler:
        save_search_scheduler_config(get_search_scheduler_config())
        try:
            from src.db.telegram_channels import seed_channels
            preset_channels = load_preset_tg_channels()
            seeded_count = seed_channels(preset_channels)
            if seeded_count:
                logger.info("已从 tg_channels_preset.json 写入 %d 个默认 TG 频道。", seeded_count)
        except Exception as error:
            logger.warning("初始化 TG 频道失败: %s", error)

    # 2. 首次初始化 API 接口至 api_config（若表为空时从 api_configs_preset.json 导入）
    try:
        from src.db.connection import db_cursor
        with db_cursor() as cursor:
            if cursor:
                cursor.execute("SELECT count(*) FROM api_config;")
                row = cursor.fetchone()
                count = row[0] if isinstance(row, tuple) else row.get("count(*)", 0)
                if count == 0:
                    preset_apis = load_preset_api_configs()
                    for item in preset_apis:
                        cursor.execute(
                            "INSERT OR IGNORE INTO api_config (name, url, method, request, response, status, response_time_ms, is_enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                item.get("name"),
                                item.get("url"),
                                item.get("method", "get"),
                                item.get("request", ""),
                                item.get("response", ""),
                                item.get("status", "unknown"),
                                int(item.get("response_time_ms", 0)),
                                1 if item.get("is_enabled") else 0,
                            ),
                        )
                    logger.info("已从 api_configs_preset.json 成功导入 %d 个默认 API 接口。", len(preset_apis))
    except Exception as e:
        logger.warning(f"初始化 API 接口状态失败: {e}")

    # 3. 首次初始化插件状态至 plugin_settings
    current_plugins = get_config_value(PLUGIN_SETTINGS_KEY)
    if not current_plugins:
        try:
            default_plugin_settings = load_preset_plugin_settings()
            settings = {
                name: {"is_enabled": bool(is_enabled)}
                for name, is_enabled in default_plugin_settings.items()
            }
            set_config_value(PLUGIN_SETTINGS_KEY, settings)
            enabled_count = sum(1 for item in settings.values() if item["is_enabled"])
            logger.info("已写入 %d 个插件默认状态，其中 %d 个启用。", len(settings), enabled_count)
        except Exception as e:
            logger.warning(f"初始化插件配置失败: {e}")
