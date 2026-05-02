import logging
from typing import Any, Dict, List, Optional

from mysql.connector import Error

from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)

TEMP_SHARE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS temp_share (
  id int(11) NOT NULL AUTO_INCREMENT COMMENT '主键',
  original_url text NOT NULL COMMENT '原始分享链接',
  title varchar(255) DEFAULT NULL COMMENT '资源标题',
  cloud_name varchar(100) NOT NULL COMMENT '网盘名称',
  temp_share_url text NOT NULL COMMENT '临时分享链接',
  file_id varchar(255) NOT NULL COMMENT '转存后的文件ID或路径',
  status varchar(20) NOT NULL DEFAULT 'active' COMMENT '状态: active/deleted/failed',
  expires_at datetime NOT NULL COMMENT '过期时间',
  last_accessed_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后访问时间',
  created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted_at datetime DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (id),
  KEY idx_temp_share_lookup (cloud_name, status, expires_at),
  KEY idx_temp_share_original (original_url(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='搜索页动态转存临时分享表'
"""


def ensure_temp_share_table() -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(TEMP_SHARE_TABLE_SQL)
        conn.commit()
        return True
    except Error as err:
        logger.error(f"初始化 temp_share 表失败: {err}")
        conn.rollback()
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_active_temp_share(original_url: str, cloud_name: str) -> Optional[Dict[str, Any]]:
    if not ensure_temp_share_table():
        return None

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
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
        if conn.is_connected():
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
        if conn.is_connected():
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
            VALUES (%s, %s, %s, %s, %s, 'active', DATE_ADD(NOW(), INTERVAL %s HOUR), NOW())
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
        if conn.is_connected():
            cursor.close()
            conn.close()


def list_expired_temp_shares(limit: int = 50) -> List[Dict[str, Any]]:
    if not ensure_temp_share_table():
        return []

    conn = get_db_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(dictionary=True)
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
        if conn.is_connected():
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
        if conn.is_connected():
            cursor.close()
            conn.close()
