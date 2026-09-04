import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.db.telegram_channels import (
    delete_channel,
    get_all_channels,
    get_channel,
    insert_channel,
    set_all_channels_enabled,
    set_channel_enabled,
    update_channel_health,
)

TG_CHANNEL_PATTERN = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def normalize_tg_channel(value: Any) -> str:
    channel = str(value or "").strip()
    if channel.startswith(("https://t.me/", "http://t.me/")):
        channel = urlparse(channel).path.strip("/")
        if channel.startswith("s/"):
            channel = channel[2:]
    return channel.lstrip("@").strip("/").strip()


def validate_tg_channel(value: Any) -> tuple[bool, str, str]:
    channel = normalize_tg_channel(value)
    if not channel:
        return False, "频道名称不能为空", ""
    if not TG_CHANNEL_PATTERN.fullmatch(channel):
        return False, "频道用户名仅支持 5-32 位字母、数字或下划线", channel
    return True, "", channel


def get_tg_channel_items() -> List[Dict[str, Any]]:
    items = []
    for row in get_all_channels():
        status = row.get("health_status") or "unknown"
        status_text = {
            "healthy": "正常",
            "no_data": "无结果",
            "error": "异常",
        }.get(status, "未检测")
        items.append({
            "id": row["id"],
            "channel": row["channel"],
            "url": f"https://t.me/s/{row['channel']}",
            "is_enabled": row["is_enabled"],
            "health": {
                "status": status,
                "status_text": status_text,
                "latency_ms": row.get("latency_ms", 0),
                "result_count": row.get("result_count", 0),
                "message": row.get("health_message") or "",
                "checked_at": row.get("checked_at"),
            },
        })
    return items


def add_tg_channel(value: Any, is_enabled: bool = True) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    valid, message, channel = validate_tg_channel(value)
    if not valid:
        return False, message, None
    success, message, channel_id = insert_channel(channel, is_enabled)
    if not success:
        return False, message, None
    return True, message, {
        "id": channel_id,
        "channel": channel,
        "url": f"https://t.me/s/{channel}",
        "is_enabled": bool(is_enabled),
        "health": {"status": "unknown", "status_text": "未检测"},
    }


def delete_tg_channel(value: Any) -> tuple[bool, str]:
    return delete_channel(normalize_tg_channel(value))


def set_tg_channel_enabled(value: Any, is_enabled: bool) -> tuple[bool, str]:
    return set_channel_enabled(normalize_tg_channel(value), is_enabled)


def set_all_tg_channels_enabled(is_enabled: bool) -> tuple[bool, str, int]:
    return set_all_channels_enabled(is_enabled)


def save_tg_channel_health(value: Any, result: Dict[str, Any]) -> bool:
    channel = normalize_tg_channel(value)
    if not get_channel(channel):
        return False
    if result.get("success") and int(result.get("count", 0)) > 0:
        status = "healthy"
    elif result.get("success"):
        status = "no_data"
    else:
        status = "error"
    return update_channel_health(
        channel=channel,
        health_status=status,
        latency_ms=int(result.get("latency_ms", 0) or 0),
        result_count=int(result.get("count", 0) or 0),
        health_message=str(result.get("message", "")),
    )
