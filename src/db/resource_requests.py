import logging
from typing import Any, Dict, List, Optional, Tuple

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)


def create_resource_request(
    resource_name: str,
    contact: Optional[str] = None,
    note: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> Tuple[bool, str, Optional[int]]:
    """
    新建用户求片/需求提交记录。
    """
    resource_name = str(resource_name or "").strip()
    if not resource_name:
        return False, "资源名称不能为空", None

    contact = str(contact or "").strip()[:100] if contact else None
    note = str(note or "").strip()[:500] if note else None
    client_ip = str(client_ip or "").strip()[:50] if client_ip else None

    conn = get_db_connection()
    if not conn:
        return False, "数据库连接不可用", None

    try:
        cursor = conn.cursor()
        sql = (
            "INSERT INTO resource_requests (resource_name, contact, note, status, client_ip) "
            "VALUES (?, ?, ?, 'pending', ?)"
        )
        cursor.execute(sql, (resource_name, contact, note, client_ip))
        conn.commit()
        request_id = cursor.lastrowid
        logger.info(f"成功记录用户求片需求: ID={request_id}, 资源='{resource_name}', IP={client_ip}")
        return True, "求片需求已成功提交", request_id
    except Error as err:
        logger.error(f"写入求片需求失败: {err}")
        conn.rollback()
        return False, f"数据库写入失败: {err}", None
    finally:
        cursor.close()
        conn.close()


def get_resource_requests(
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    分页查询用户求片列表及总数。
    """
    conn = get_db_connection()
    if not conn:
        return [], 0

    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    offset = (page - 1) * page_size

    where_clauses = []
    params: List[Any] = []

    if status and status != "all":
        where_clauses.append("status = ?")
        params.append(status)

    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        where_clauses.append("(resource_name LIKE ? OR contact LIKE ? OR note LIKE ?)")
        params.extend([kw, kw, kw])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_sql = f"SELECT COUNT(*) FROM resource_requests {where_sql}"
    query_sql = (
        f"SELECT id, resource_name, contact, note, status, client_ip, created_at, updated_at "
        f"FROM resource_requests {where_sql} "
        f"ORDER BY created_at DESC LIMIT ? OFFSET ?"
    )

    try:
        cursor = conn.cursor()
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        cursor = conn.cursor(as_dict=True)
        cursor.execute(query_sql, params + [page_size, offset])
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "resource_name": row["resource_name"],
                "contact": row["contact"] or "",
                "note": row["note"] or "",
                "status": row["status"] or "pending",
                "client_ip": row["client_ip"] or "",
                "created_at": str(row["created_at"]) if row.get("created_at") else "",
                "updated_at": str(row["updated_at"]) if row.get("updated_at") else "",
            })
        return results, total_count
    except Error as err:
        logger.error(f"查询求片列表失败: {err}")
        return [], 0
    finally:
        cursor.close()
        conn.close()


def get_resource_request_counts() -> Dict[str, int]:
    """
    获取求片数量概览（全部、待处理、已处理、已忽略）。
    """
    conn = get_db_connection()
    if not conn:
        return {"total": 0, "pending": 0, "completed": 0, "ignored": 0}

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) FROM resource_requests GROUP BY status")
        rows = cursor.fetchall()
        counts = {"total": 0, "pending": 0, "completed": 0, "ignored": 0}
        for status, count in rows:
            counts["total"] += count
            if status in counts:
                counts[status] = count
        return counts
    except Error as err:
        logger.error(f"统计求片数量失败: {err}")
        return {"total": 0, "pending": 0, "completed": 0, "ignored": 0}
    finally:
        cursor.close()
        conn.close()


def update_resource_request_status(request_id: int, status: str) -> bool:
    """
    更新求片处理状态: pending (待处理) / completed (已满足) / ignored (已忽略)
    """
    valid_statuses = {"pending", "completed", "ignored"}
    if status not in valid_statuses:
        return False

    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        sql = "UPDATE resource_requests SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        cursor.execute(sql, (status, request_id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as err:
        logger.error(f"更新求片状态失败: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def delete_resource_request(request_id: int) -> bool:
    """
    删除指定的求片记录。
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM resource_requests WHERE id = ?", (request_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as err:
        logger.error(f"删除求片记录失败: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()
