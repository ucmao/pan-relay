import logging
from typing import Any, Dict, List, Optional

from src.db.connection import DictCursor, Error, get_db_connection

logger = logging.getLogger(__name__)

TEMP_SHARE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS temp_share (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  original_url TEXT NOT NULL,
  title TEXT DEFAULT NULL,
  cloud_name TEXT NOT NULL,
  temp_share_url TEXT NOT NULL,
  file_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  expires_at DATETIME NOT NULL,
  last_accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  deleted_at DATETIME DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_temp_share_lookup ON temp_share(cloud_name, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_temp_share_original ON temp_share(original_url);
"""


def ensure_temp_share_table() -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        conn.executescript(TEMP_SHARE_TABLE_SQL)
        conn.commit()
        return True
    except Error as err:
        logger.error(f"初始化 temp_share 表失败: {err}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_active_temp_share(original_url: str, cloud_name: str) -> Optional[Dict[str, Any]]:
    if not ensure_temp_share_table():
        return None

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(DictCursor)
        cursor.execute(
            """
            SELECT id, original_url, title, cloud_name, temp_share_url, file_id, status, expires_at
            FROM temp_share
            WHERE original_url = %s
              AND cloud_name = %s
              AND status = 'active'
              AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (original_url, cloud_name),
        )
        return cursor.fetchone()
    except Error as err:
        logger.error(f"查询有效临时分享失败: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def touch_temp_share(record_id: int) -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE temp_share SET last_accessed_at = NOW() WHERE id = %s",
            (record_id,),
        )
        conn.commit()
        return True
    except Error as err:
        logger.error(f"更新临时分享访问时间失败: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def create_temp_share_record(
    original_url: str,
    title: str,
    cloud_name: str,
    temp_share_url: str,
    file_id: str,
    expires_in_hours: int,
) -> Optional[int]:
    if not ensure_temp_share_table():
        return None

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO temp_share (
              original_url, title, cloud_name, temp_share_url, file_id, status, expires_at, last_accessed_at
            )
            VALUES (?, ?, ?, ?, ?, 'active', datetime('now', '+' || ? || ' hours'), datetime('now'))
            """,
            (original_url, title, cloud_name, temp_share_url, file_id, expires_in_hours),
        )
        conn.commit()
        return cursor.lastrowid
    except Error as err:
        logger.error(f"创建临时分享记录失败: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def list_expired_temp_shares(limit: int = 50) -> List[Dict[str, Any]]:
    if not ensure_temp_share_table():
        return []

    conn = get_db_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(DictCursor)
        cursor.execute(
            """
            SELECT id, original_url, title, cloud_name, temp_share_url, file_id
            FROM temp_share
            WHERE status = 'active'
              AND expires_at <= NOW()
            ORDER BY expires_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        return cursor.fetchall()
    except Error as err:
        logger.error(f"查询过期临时分享失败: {err}")
        return []
    finally:
        cursor.close()
        conn.close()


def mark_temp_share_deleted(record_id: int) -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE temp_share
            SET status = 'deleted', deleted_at = NOW()
            WHERE id = %s
            """,
            (record_id,),
        )
        conn.commit()
        return True
    except Error as err:
        logger.error(f"标记临时分享已删除失败: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()
