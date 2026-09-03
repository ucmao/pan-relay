import json
import logging
from typing import Dict, List

from src.db.system_config_dao import get_config_value, set_config_value
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
