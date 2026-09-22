import logging
from typing import Any, Dict, List, Optional

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)
def get_active_temp_share(original_url: str, cloud_name: str) -> Optional[Dict[str, Any]]:

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(
            """
            SELECT id, original_url, title, cloud_name, temp_share_url, file_id, status, expires_at
            FROM temp_share
            WHERE original_url = ?
              AND cloud_name = ?
              AND status = 'active'
              AND expires_at > datetime('now')
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
            "UPDATE temp_share SET last_accessed_at = datetime('now') WHERE id = ?",
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
    expires_in_hours: Optional[int] = None,
    expires_in_minutes: Optional[int] = None,
) -> Optional[int]:
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        if expires_in_minutes is not None:
            mins = max(30, int(expires_in_minutes))
            cursor.execute(
                """
                INSERT INTO temp_share (
                  original_url, title, cloud_name, temp_share_url, file_id, status, expires_at, last_accessed_at
                )
                VALUES (?, ?, ?, ?, ?, 'active', datetime('now', '+' || ? || ' minutes'), datetime('now'))
                """,
                (original_url, title, cloud_name, temp_share_url, file_id, mins),
            )
        else:
            hours = int(expires_in_hours) if expires_in_hours is not None else 6
            cursor.execute(
                """
                INSERT INTO temp_share (
                  original_url, title, cloud_name, temp_share_url, file_id, status, expires_at, last_accessed_at
                )
                VALUES (?, ?, ?, ?, ?, 'active', datetime('now', '+' || ? || ' hours'), datetime('now'))
                """,
                (original_url, title, cloud_name, temp_share_url, file_id, hours),
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
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(
            """
            SELECT id, original_url, title, cloud_name, temp_share_url, file_id
            FROM temp_share
            WHERE status = 'active'
              AND expires_at <= datetime('now')
            ORDER BY expires_at ASC
            LIMIT ?
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
            SET status = 'deleted', deleted_at = datetime('now')
            WHERE id = ?
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


def mark_temp_share_deleted_by_url_or_file(url: Optional[str] = None, file_id: Optional[str] = None) -> int:
    """根据 temp_share_url、original_url 或 file_id 将有效临时分享记录标记为已删除"""
    if not url and not file_id:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    try:
        cursor = conn.cursor()
        clauses = []
        params = []
        if url:
            clauses.append("(temp_share_url = ? OR original_url = ?)")
            params.extend([url, url])
        if file_id:
            clauses.append("file_id = ?")
            params.append(str(file_id))

        sql = f"""
        UPDATE temp_share
        SET status = 'deleted', deleted_at = datetime('now')
        WHERE status = 'active' AND ({' OR '.join(clauses)})
        """
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    except Error as err:
        logger.error(f"按 URL/file_id 标记临时分享已删除失败: {err}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()
