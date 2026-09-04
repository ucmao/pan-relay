import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)


def get_all_channels() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(as_dict=True)
    try:
        cursor.execute(
            "SELECT id, channel, title, is_enabled, health_status, latency_ms, result_count, "
            "health_message, checked_at, created_at, updated_at "
            "FROM telegram_channel ORDER BY id ASC"
        )
        rows = cursor.fetchall()
        return [
            {
                **row,
                "is_enabled": bool(row["is_enabled"]),
                "latency_ms": int(row["latency_ms"] or 0),
                "result_count": int(row["result_count"] or 0),
            }
            for row in rows
        ]
    except Error as error:
        logger.error("读取 Telegram 频道列表失败: %s", error)
        return []
    finally:
        cursor.close()
        conn.close()


def get_enabled_channel_names() -> List[str]:
    return [item["channel"] for item in get_all_channels() if item["is_enabled"]]


def get_channel(channel: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor(as_dict=True)
    try:
        cursor.execute(
            "SELECT id, channel, title, is_enabled, health_status, latency_ms, result_count, "
            "health_message, checked_at, created_at, updated_at "
            "FROM telegram_channel WHERE channel = ?",
            (channel,),
        )
        row = cursor.fetchone()
        if row:
            row["is_enabled"] = bool(row["is_enabled"])
        return row
    except Error as error:
        logger.error("读取 Telegram 频道 @%s 失败: %s", channel, error)
        return None
    finally:
        cursor.close()
        conn.close()


def insert_channel(channel: str, is_enabled: bool = True, title: Optional[str] = None) -> Tuple[bool, str, Optional[int]]:
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", None
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO telegram_channel (channel, title, is_enabled) VALUES (?, ?, ?)",
            (channel, title, 1 if is_enabled else 0),
        )
        conn.commit()
        return True, f"频道 @{channel} 添加成功", cursor.lastrowid
    except Error as error:
        conn.rollback()
        if "UNIQUE constraint failed" in str(error):
            return False, f"频道 @{channel} 已存在", None
        logger.error("添加 Telegram 频道 @%s 失败: %s", channel, error)
        return False, f"频道添加失败: {error}", None
    finally:
        cursor.close()
        conn.close()


def update_channel_title(channel: str, title: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE telegram_channel SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE channel = ?",
            (title, channel),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Error as error:
        conn.rollback()
        logger.error("更新 Telegram 频道 @%s 标题失败: %s", channel, error)
        return False
    finally:
        cursor.close()
        conn.close()


def delete_channel(channel: str) -> Tuple[bool, str]:
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM telegram_channel WHERE channel = ?", (channel,))
        conn.commit()
        if cursor.rowcount == 0:
            return False, "未找到该频道"
        return True, f"频道 @{channel} 已删除"
    except Error as error:
        conn.rollback()
        logger.error("删除 Telegram 频道 @%s 失败: %s", channel, error)
        return False, f"频道删除失败: {error}"
    finally:
        cursor.close()
        conn.close()


def set_channel_enabled(channel: str, is_enabled: bool) -> Tuple[bool, str]:
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE telegram_channel SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE channel = ?",
            (1 if is_enabled else 0, channel),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return False, "未找到该频道"
        return True, f"频道 @{channel} 已{'启用' if is_enabled else '停用'}"
    except Error as error:
        conn.rollback()
        logger.error("更新 Telegram 频道 @%s 状态失败: %s", channel, error)
        return False, f"频道状态更新失败: {error}"
    finally:
        cursor.close()
        conn.close()


def set_all_channels_enabled(is_enabled: bool) -> Tuple[bool, str, int]:
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", 0
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE telegram_channel SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP",
            (1 if is_enabled else 0,),
        )
        conn.commit()
        count = cursor.rowcount
        return True, f"已{'启用' if is_enabled else '停用'}全部 {count} 个频道", count
    except Error as error:
        conn.rollback()
        logger.error("批量更新 Telegram 频道状态失败: %s", error)
        return False, f"批量更新频道状态失败: {error}", 0
    finally:
        cursor.close()
        conn.close()


def update_channel_health(
    channel: str,
    health_status: str,
    latency_ms: int,
    result_count: int,
    health_message: str,
) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE telegram_channel SET health_status = ?, latency_ms = ?, result_count = ?, "
            "health_message = ?, checked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE channel = ?",
            (health_status, latency_ms, result_count, health_message, channel),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Error as error:
        conn.rollback()
        logger.error("保存 Telegram 频道 @%s 健康状态失败: %s", channel, error)
        return False
    finally:
        cursor.close()
        conn.close()


def seed_channels(channels: Iterable[str], disabled_channels: Iterable[str], titles: Optional[Dict[str, str]] = None) -> int:
    """仅在频道表为空时写入版本内置的初始频道。"""
    conn = get_db_connection()
    if not conn:
        return 0
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM telegram_channel")
        if cursor.fetchone()[0] > 0:
            return 0
        disabled = set(disabled_channels)
        title_map = titles or {}
        rows = [(channel, title_map.get(channel), 0 if channel in disabled else 1) for channel in channels]
        cursor.executemany(
            "INSERT INTO telegram_channel (channel, title, is_enabled) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
        return len(rows)
    except Error as error:
        conn.rollback()
        logger.error("初始化 Telegram 频道失败: %s", error)
        return 0
    finally:
        cursor.close()
        conn.close()
