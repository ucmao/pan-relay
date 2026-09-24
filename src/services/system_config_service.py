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
TRANSFER_TARGET_DIR_KEY = "transfer_target_dir"
DEFAULT_TRANSFER_TARGET_DIR = "Pan-Relay分享"
FRONTEND_LINK_MODE_OPTIONS = {"copy", "view"}
API_MODE_CONFIG_KEY = "api_mode_config"
SEARCH_API_SCOPE_KEY = "search_api_scope"
SEARCH_API_LIMIT_KEY = "search_api_limit"
SEARCH_API_SCOPE_LOCK_KEY = "search_api_scope_lock"
SEARCH_API_LIMIT_LOCK_KEY = "search_api_limit_lock"
TRANSFER_API_KEY_KEY = "transfer_api_key"
FRONTEND_LINK_CHECK_CONFIG_KEY = "frontend_link_check_config"




def get_transfer_target_dir() -> str:
    raw_value = get_config_value(TRANSFER_TARGET_DIR_KEY)
    if not raw_value:
        return DEFAULT_TRANSFER_TARGET_DIR

    try:
        parsed = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        logger.warning("转存目标目录配置格式无效，已回退到默认值")
        return DEFAULT_TRANSFER_TARGET_DIR

    target_dir = str(parsed.get("target_dir", DEFAULT_TRANSFER_TARGET_DIR)).strip()
    return target_dir


def save_transfer_target_dir(target_dir: str) -> bool:
    clean_dir = (target_dir or "").strip()
    return set_config_value(
        TRANSFER_TARGET_DIR_KEY,
        {"target_dir": clean_dir},
    )


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


def get_frontend_link_check_config() -> Dict[str, Any]:
    """获取前台测活配置"""
    from src.utils.netdisk_utils import LINK_CHECK_NETDISK_OPTIONS
    raw_value = get_config_value(FRONTEND_LINK_CHECK_CONFIG_KEY)
    default_config = {
        "enable_link_check": True,
        "enabled_check_pans": LINK_CHECK_NETDISK_OPTIONS.copy(),
    }
    if not raw_value:
        return default_config

    try:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            return default_config
        enabled_pans = parsed.get("enabled_check_pans")
        if not isinstance(enabled_pans, list):
            enabled_pans = LINK_CHECK_NETDISK_OPTIONS.copy()

        return {
            "enable_link_check": bool(parsed.get("enable_link_check", True)),
            "enabled_check_pans": enabled_pans,
        }
    except (TypeError, json.JSONDecodeError):
        logger.warning("前台测活配置格式无效，已回退到默认值")
        return default_config


def save_frontend_link_check_config(
    enable_link_check: bool = True,
    enabled_check_pans: Any = None,
) -> bool:
    """保存前台测活配置"""
    from src.utils.netdisk_utils import LINK_CHECK_NETDISK_OPTIONS
    if enabled_check_pans is None:
        enabled_check_pans = LINK_CHECK_NETDISK_OPTIONS.copy()

    valid_pans = [str(name) for name in enabled_check_pans if isinstance(name, str)]

    return set_config_value(
        FRONTEND_LINK_CHECK_CONFIG_KEY,
        {
            "enable_link_check": bool(enable_link_check),
            "enabled_check_pans": valid_pans,
        },
    )


def is_frontend_link_check_enabled() -> bool:
    return get_frontend_link_check_config()["enable_link_check"]


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


AD_FILTER_CONFIG_KEY = "ad_filter_config"
DEFAULT_AD_KEYWORDS = [
    "关注公众号", "防失联", "防走丢", "防封地址", "发布页",
    "福利群", "扫码进群", "交流群", "通知群", "一手资源群", "禁止倒卖", "严禁倒卖", "低价出售",
    "最新地址", "永久地址", "官方网站", "永久发布页", "解压密码", "更多资源请关注",
]


def get_ad_filter_config() -> Dict[str, Any]:
    """获取广告过滤与标题匹配模式配置与关键词库"""
    default_config = {
        "enabled": False,
        "keywords": DEFAULT_AD_KEYWORDS.copy(),
        "title_filter_mode": "loose",
    }
    raw_value = get_config_value(AD_FILTER_CONFIG_KEY)
    if not raw_value:
        return default_config
    try:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            return default_config
        keywords = parsed.get("keywords", default_config["keywords"])
        if isinstance(keywords, str):
            keywords = [w.strip() for w in keywords.replace("\r\n", "\n").split("\n") if w.strip()]
        elif not isinstance(keywords, list):
            keywords = default_config["keywords"]

        title_filter_mode = str(parsed.get("title_filter_mode", "loose")).strip().lower()
        if title_filter_mode not in ("loose", "off"):
            title_filter_mode = "loose"

        return {
            "enabled": bool(parsed.get("enabled", False)),
            "keywords": [str(w).strip().lower() for w in keywords if str(w).strip()],
            "title_filter_mode": title_filter_mode,
        }
    except Exception as e:
        logger.warning(f"读取广告过滤配置失败，回退默认配置: {e}")
        return default_config


def save_ad_filter_config(config_data: Dict[str, Any]) -> bool:
    """保存广告过滤与标题匹配模式配置与关键词库"""
    if not isinstance(config_data, dict):
        return False
    current = get_ad_filter_config()
    enabled = bool(config_data.get("enabled", current["enabled"]))
    keywords_raw = config_data.get("keywords", current["keywords"])
    if isinstance(keywords_raw, str):
        keywords = [w.strip().lower() for w in keywords_raw.replace("\r\n", "\n").split("\n") if w.strip()]
    elif isinstance(keywords_raw, list):
        keywords = [str(w).strip().lower() for w in keywords_raw if str(w).strip()]
    else:
        keywords = current["keywords"]

    title_filter_mode = str(config_data.get("title_filter_mode", current.get("title_filter_mode", "loose"))).strip().lower()
    if title_filter_mode not in ("loose", "off"):
        title_filter_mode = "loose"

    unique_keywords = list(dict.fromkeys(keywords))
    payload = {
        "enabled": enabled,
        "keywords": unique_keywords,
        "title_filter_mode": title_filter_mode,
    }
    return set_config_value(AD_FILTER_CONFIG_KEY, payload)


def get_title_filter_mode() -> str:
    """获取当前标题匹配过滤模式 ('loose' | 'off')"""
    config = get_ad_filter_config()
    mode = config.get("title_filter_mode", "loose")
    return mode if mode in ("loose", "off") else "loose"




CUSTOM_AD_INJECTION_CONFIG_KEY = "custom_ad_injection_config"
DEFAULT_AD_SHARE_URLS = {
    "quark": "",
    "uc": "",
    "baidu": "",
    "aliyun": "",
    "xunlei": "",
    "caiyun": "",
    "guangya": "",
    "wukong": "",
}
DEFAULT_CUSTOM_AD_INJECTION_CONFIG = {
    "enabled": False,
    "ad_share_url": "",
    "ad_share_urls": DEFAULT_AD_SHARE_URLS.copy(),
}


def get_custom_ad_injection_config() -> Dict[str, Any]:
    """获取自定义引流广告植入配置（支持多网盘独立配置）"""
    default_config = {
        "enabled": False,
        "ad_share_url": "",
        "ad_share_urls": DEFAULT_AD_SHARE_URLS.copy(),
    }
    raw_value = get_config_value(CUSTOM_AD_INJECTION_CONFIG_KEY)
    if not raw_value:
        return default_config
    try:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            return default_config
        
        ad_urls = DEFAULT_AD_SHARE_URLS.copy()
        raw_urls = parsed.get("ad_share_urls")
        if isinstance(raw_urls, dict):
            for k in ad_urls.keys():
                if k in raw_urls and isinstance(raw_urls[k], str):
                    ad_urls[k] = raw_urls[k].strip()
        
        legacy_url = str(parsed.get("ad_share_url", "")).strip()

        return {
            "enabled": bool(parsed.get("enabled", False)),
            "ad_share_url": legacy_url,
            "ad_share_urls": ad_urls,
        }
    except Exception as e:
        logger.warning(f"读取自定义广告植入配置失败，回退默认配置: {e}")
        return default_config


def save_custom_ad_injection_config(config_data: Dict[str, Any]) -> bool:
    """保存自定义引流广告植入配置（支持多网盘独立配置）"""
    if not isinstance(config_data, dict):
        return False
    current = get_custom_ad_injection_config()
    
    enabled = bool(config_data.get("enabled", current["enabled"]))
    legacy_url = str(config_data.get("ad_share_url", current.get("ad_share_url", ""))).strip()
    
    ad_urls = current.get("ad_share_urls", DEFAULT_AD_SHARE_URLS.copy()).copy()
    if "ad_share_urls" in config_data and isinstance(config_data["ad_share_urls"], dict):
        for k in DEFAULT_AD_SHARE_URLS.keys():
            if k in config_data["ad_share_urls"]:
                ad_urls[k] = str(config_data["ad_share_urls"][k] or "").strip()

    payload = {
        "enabled": enabled,
        "ad_share_url": legacy_url,
        "ad_share_urls": ad_urls,
    }
    return set_config_value(CUSTOM_AD_INJECTION_CONFIG_KEY, payload)


def get_ad_share_url_for_disk(disk_type: str) -> str:
    """
    根据网盘类型获取其专属引流分享链接；若未配置专属链接则尝试回退到通用引流链接。
    :param disk_type: 网盘标识或中文名（如 'quark', '夸克网盘', 'baidu', '百度网盘' 等）
    :return: 对应的引流分享链接，若未启用或未配置则返回空字符串
    """
    cfg = get_custom_ad_injection_config()
    if not cfg.get("enabled"):
        return ""
    
    key_map = {
        "quark": "quark", "夸克网盘": "quark", "夸克": "quark",
        "uc": "uc", "uc网盘": "uc", "uc云盘": "uc",
        "baidu": "baidu", "百度网盘": "baidu", "百度": "baidu",
        "aliyun": "aliyun", "阿里云盘": "aliyun", "阿里": "aliyun", "alipan": "aliyun",
        "xunlei": "xunlei", "迅雷网盘": "xunlei", "迅雷": "xunlei",
        "caiyun": "caiyun", "移动云盘": "caiyun", "和彩云": "caiyun", "mobile": "caiyun",
        "guangya": "guangya", "光鸭云盘": "guangya", "光雅网盘": "guangya", "光雅": "guangya",
        "wukong": "wukong", "悟空网盘": "wukong", "悟空": "wukong",
    }
    norm_key = key_map.get(str(disk_type).strip().lower(), "")
    ad_urls = cfg.get("ad_share_urls") or {}
    if norm_key and norm_key in ad_urls and ad_urls[norm_key]:
        return ad_urls[norm_key].strip()
    
    return cfg.get("ad_share_url", "").strip()



STORAGE_CLEANUP_CONFIG_KEY = "storage_cleanup_config"
DEFAULT_STORAGE_CLEANUP_CONFIG = {
    "enabled": True,
    "retention_unit": "days",
    "retention_value": 15,
    "retention_days": 15,
    "retention_minutes": 15 * 24 * 60,
    "cleanup_interval_unit": "hours",
    "cleanup_interval_value": 12,
    "auto_cleanup_interval_minutes": 12 * 60,
    "auto_cleanup_interval_hours": 12,
    "clean_temp_shares": True,
    "clean_old_resources": True,
    "limit_per_run": 100,
}


def get_storage_cleanup_config() -> Dict[str, Any]:
    """获取存储优化与自动清理配置"""
    default_config = DEFAULT_STORAGE_CLEANUP_CONFIG.copy()
    raw_value = get_config_value(STORAGE_CLEANUP_CONFIG_KEY)
    if not raw_value:
        return default_config
    try:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            return default_config

        # 1. 保留时长计算
        retention_unit = str(parsed.get("retention_unit", "")).strip().lower()
        if retention_unit not in ("minutes", "hours", "days"):
            retention_unit = "days"

        if "retention_value" in parsed:
            retention_value = int(parsed["retention_value"])
        elif "retention_days" in parsed:
            retention_value = int(parsed["retention_days"])
            retention_unit = "days"
        else:
            retention_value = default_config["retention_value"]

        if retention_unit == "minutes":
            retention_value = max(30, retention_value)
            retention_minutes = retention_value
        elif retention_unit == "hours":
            retention_value = max(1, retention_value)
            retention_minutes = retention_value * 60
        else:
            retention_value = max(1, retention_value)
            retention_minutes = retention_value * 1440

        retention_days = max(1, int(round(retention_minutes / 1440)))

        # 2. 扫描清理周期计算
        interval_unit = str(parsed.get("cleanup_interval_unit", "")).strip().lower()
        if interval_unit not in ("minutes", "hours", "days"):
            interval_unit = "hours"

        if "cleanup_interval_value" in parsed:
            interval_value = int(parsed["cleanup_interval_value"])
        elif "auto_cleanup_interval_hours" in parsed:
            interval_value = int(parsed["auto_cleanup_interval_hours"])
            interval_unit = "hours"
        else:
            interval_value = default_config["cleanup_interval_value"]

        if interval_unit == "minutes":
            interval_value = max(15, interval_value)
            interval_minutes = interval_value
        elif interval_unit == "hours":
            interval_value = max(1, interval_value)
            interval_minutes = interval_value * 60
        else:
            interval_value = max(1, interval_value)
            interval_minutes = interval_value * 1440

        interval_hours = max(1, int(round(interval_minutes / 60)))

        return {
            "enabled": bool(parsed.get("enabled", default_config["enabled"])),
            "retention_unit": retention_unit,
            "retention_value": retention_value,
            "retention_days": retention_days,
            "retention_minutes": retention_minutes,
            "cleanup_interval_unit": interval_unit,
            "cleanup_interval_value": interval_value,
            "auto_cleanup_interval_minutes": interval_minutes,
            "auto_cleanup_interval_hours": interval_hours,
            "clean_temp_shares": bool(parsed.get("clean_temp_shares", default_config["clean_temp_shares"])),
            "clean_old_resources": bool(
                parsed.get("clean_old_resources", default_config["clean_old_resources"])
            ),
            "limit_per_run": int(parsed.get("limit_per_run", default_config["limit_per_run"])),
        }
    except Exception as e:
        logger.warning(f"读取存储清理配置失败，回退默认配置: {e}")
        return default_config


def save_storage_cleanup_config(config_data: Dict[str, Any]) -> bool:
    """保存存储优化与自动清理配置"""
    if not isinstance(config_data, dict):
        return False
    current = get_storage_cleanup_config()

    # 1. 保留时长
    retention_unit = str(config_data.get("retention_unit", current["retention_unit"])).strip().lower()
    if retention_unit not in ("minutes", "hours", "days"):
        retention_unit = "days"

    if "retention_value" in config_data:
        raw_ret_val = int(config_data.get("retention_value", current["retention_value"]))
    elif "retention_days" in config_data:
        raw_ret_val = int(config_data.get("retention_days", current["retention_days"]))
        retention_unit = "days"
    else:
        raw_ret_val = current["retention_value"]

    if retention_unit == "minutes":
        retention_value = max(30, raw_ret_val)
        retention_minutes = retention_value
    elif retention_unit == "hours":
        retention_value = max(1, raw_ret_val)
        retention_minutes = retention_value * 60
    else:
        retention_value = max(1, raw_ret_val)
        retention_minutes = retention_value * 1440

    retention_days = max(1, int(round(retention_minutes / 1440)))

    # 2. 扫描周期
    interval_unit = str(
        config_data.get("cleanup_interval_unit", current.get("cleanup_interval_unit", "hours"))
    ).strip().lower()
    if interval_unit not in ("minutes", "hours", "days"):
        interval_unit = "hours"

    if "cleanup_interval_value" in config_data:
        raw_int_val = int(
            config_data.get("cleanup_interval_value", current.get("cleanup_interval_value", 12))
        )
    elif "auto_cleanup_interval_hours" in config_data:
        raw_int_val = int(
            config_data.get("auto_cleanup_interval_hours", current.get("auto_cleanup_interval_hours", 12))
        )
        interval_unit = "hours"
    else:
        raw_int_val = current.get("cleanup_interval_value", 12)

    if interval_unit == "minutes":
        interval_value = max(15, raw_int_val)
        interval_minutes = interval_value
    elif interval_unit == "hours":
        interval_value = max(1, raw_int_val)
        interval_minutes = interval_value * 60
    else:
        interval_value = max(1, raw_int_val)
        interval_minutes = interval_value * 1440

    interval_hours = max(1, int(round(interval_minutes / 60)))

    payload = {
        "enabled": bool(config_data.get("enabled", current["enabled"])),
        "retention_unit": retention_unit,
        "retention_value": retention_value,
        "retention_days": retention_days,
        "retention_minutes": retention_minutes,
        "cleanup_interval_unit": interval_unit,
        "cleanup_interval_value": interval_value,
        "auto_cleanup_interval_minutes": interval_minutes,
        "auto_cleanup_interval_hours": interval_hours,
        "clean_temp_shares": bool(
            config_data.get("clean_temp_shares", current["clean_temp_shares"])
        ),
        "clean_old_resources": bool(
            config_data.get("clean_old_resources", current["clean_old_resources"])
        ),
        "limit_per_run": max(10, int(config_data.get("limit_per_run", current["limit_per_run"]))),
    }
    return set_config_value(STORAGE_CLEANUP_CONFIG_KEY, payload)


SEARCH_SCHEDULER_CONFIG_KEY = "search_scheduler_settings"
PLUGIN_SETTINGS_KEY = "plugin_settings"


def get_search_scheduler_config() -> Dict[str, Any]:
    """获取三类搜索源的调度参数。"""
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
    """保存三类搜索源的调度参数。"""
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


def get_api_mode_config() -> Dict[str, Any]:
    """
    获取 API 模式与 UI 开关配置。
    从数据库系统配置中读取。
    """
    default_config = {
        "api_only": False,
        "enable_frontend": True,
        "search_scope": get_search_api_scope(),
        "search_limit": get_search_api_limit(),
        "search_scope_lock": get_search_api_scope_lock(),
        "search_limit_lock": get_search_api_limit_lock(),
        "transfer_api_key": get_transfer_api_key(),
    }

    raw_value = get_config_value(API_MODE_CONFIG_KEY)
    if raw_value:
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, dict):
                default_config["api_only"] = bool(parsed.get("api_only", False))
                default_config["enable_frontend"] = bool(parsed.get("enable_frontend", True))
        except (TypeError, json.JSONDecodeError):
            logger.warning("API 模式配置格式无效，使用默认配置")

    if default_config["api_only"]:
        default_config["enable_frontend"] = False

    return default_config


def is_api_only_enabled() -> bool:
    return get_api_mode_config()["api_only"]


def is_frontend_enabled() -> bool:
    return get_api_mode_config()["enable_frontend"]


def save_api_mode_config(
    api_only: bool = False,
    enable_frontend: bool = True,
    search_scope: str = "all",
    search_limit: int = 50,
    search_scope_lock: bool = False,
    search_limit_lock: bool = False,
    transfer_api_key: str = "",
    **kwargs
) -> bool:
    try:
        val = int(search_limit)
        clean_limit = max(1, min(val, 1000))
    except (TypeError, ValueError):
        clean_limit = 50

    config = {
        "api_only": bool(api_only),
        "enable_frontend": bool(enable_frontend),
        "search_scope": "own" if str(search_scope).strip().lower() in ("own", "local") else "all",
        "search_limit": clean_limit,
        "search_scope_lock": bool(search_scope_lock),
        "search_limit_lock": bool(search_limit_lock),
        "transfer_api_key": str(transfer_api_key or "").strip(),
    }
    save_search_api_scope(config["search_scope"])
    save_search_api_limit(config["search_limit"])
    save_search_api_scope_lock(config["search_scope_lock"])
    save_search_api_limit_lock(config["search_limit_lock"])
    save_transfer_api_key(config["transfer_api_key"])
    return set_config_value(API_MODE_CONFIG_KEY, config)


def get_search_api_scope() -> str:
    """
    获取 API 搜索默认作用域 (own: 仅站长收益库; all: 全网并发聚合)。
    """
    raw_value = get_config_value(SEARCH_API_SCOPE_KEY)
    if not raw_value:
        return "all"

    try:
        parsed = json.loads(raw_value)
        scope = str(parsed.get("scope", "all")).strip().lower()
        return "own" if scope in ("own", "local") else "all"
    except (TypeError, json.JSONDecodeError):
        return "all"


def save_search_api_scope(scope: str) -> bool:
    clean_scope = "own" if str(scope).strip().lower() in ("own", "local") else "all"
    return set_config_value(SEARCH_API_SCOPE_KEY, {"scope": clean_scope})


def get_search_api_limit() -> int:
    """获取 API 搜索默认单次返回结果数上限 (默认 50)"""
    raw_value = get_config_value(SEARCH_API_LIMIT_KEY)
    if not raw_value:
        return 50
    try:
        parsed = json.loads(raw_value)
        val = int(parsed.get("limit", 50))
        return max(1, min(val, 1000))
    except (TypeError, ValueError, json.JSONDecodeError):
        return 50


def save_search_api_limit(limit: int) -> bool:
    try:
        val = int(limit)
        clean_limit = max(1, min(val, 1000))
    except (TypeError, ValueError):
        clean_limit = 50
    return set_config_value(SEARCH_API_LIMIT_KEY, {"limit": clean_limit})


def get_search_api_scope_lock() -> bool:
    raw_value = get_config_value(SEARCH_API_SCOPE_LOCK_KEY)
    if not raw_value:
        return False
    try:
        return bool(json.loads(raw_value).get("locked", False))
    except (TypeError, json.JSONDecodeError):
        return False


def save_search_api_scope_lock(locked: bool) -> bool:
    return set_config_value(SEARCH_API_SCOPE_LOCK_KEY, {"locked": bool(locked)})


def get_search_api_limit_lock() -> bool:
    raw_value = get_config_value(SEARCH_API_LIMIT_LOCK_KEY)
    if not raw_value:
        return False
    try:
        return bool(json.loads(raw_value).get("locked", False))
    except (TypeError, json.JSONDecodeError):
        return False


def save_search_api_limit_lock(locked: bool) -> bool:
    return set_config_value(SEARCH_API_LIMIT_LOCK_KEY, {"locked": bool(locked)})




def get_transfer_api_key() -> str:
    """
    获取转存 API 校验 Key (若为空则表示公开不需要 Key)。
    """
    raw_value = get_config_value(TRANSFER_API_KEY_KEY)
    if not raw_value:
        return ""

    try:
        parsed = json.loads(raw_value)
        return str(parsed.get("api_key", "")).strip()
    except (TypeError, json.JSONDecodeError):
        return ""


def save_transfer_api_key(api_key: str) -> bool:
    return set_config_value(TRANSFER_API_KEY_KEY, {"api_key": str(api_key or "").strip()})


