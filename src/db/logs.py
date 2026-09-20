import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)

SYSTEM_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS system_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  log_type TEXT NOT NULL,
  action TEXT NOT NULL,
  query_text TEXT DEFAULT NULL,
  status_code INTEGER NOT NULL DEFAULT 200,
  error_message TEXT DEFAULT NULL,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  result_count INTEGER DEFAULT 0,
  client_ip TEXT DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_logs_created_at ON system_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_type_created ON system_logs(log_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_status_created ON system_logs(status_code, created_at DESC);
"""


def ensure_system_logs_table() -> bool:
    """
    检查并确保 system_logs 数据表与相关索引已创建
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='system_logs';"
        )
        row = cursor.fetchone()
        if not row or row[0] == 0:
            cursor.close()
            conn.executescript(SYSTEM_LOGS_TABLE_SQL)
            conn.commit()
            logger.info("已成功初始化创建 system_logs 表与索引。")
        return True
    except Error as err:
        logger.error(f"确保 system_logs 数据表存在时出错: {err}")
        conn.rollback()
        return False
    finally:
        conn.close()


def insert_system_log(
    log_type: str,
    action: str,
    query_text: Optional[str] = None,
    status_code: int = 200,
    error_message: Optional[str] = None,
    duration_ms: int = 0,
    result_count: int = 0,
    client_ip: Optional[str] = None,
) -> Optional[int]:
    """
    插入单条系统运行或业务审计日志
    """
    ensure_system_logs_table()
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO system_logs (
                log_type, action, query_text, status_code, error_message,
                duration_ms, result_count, client_ip, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """,
            (
                str(log_type or "system")[:32],
                str(action or "unknown")[:64],
                str(query_text)[:2048] if query_text is not None else None,
                int(status_code or 200),
                str(error_message)[:4096] if error_message is not None else None,
                max(0, int(duration_ms or 0)),
                max(0, int(result_count or 0)),
                str(client_ip or "")[:64] if client_ip else None,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except Error as err:
        logger.error(f"写入系统运行日志失败: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def query_system_logs(
    page: int = 1,
    page_size: int = 15,
    q: str = "",
    log_type: str = "",
    status: str = "",
    start_date: str = "",
    end_date: str = "",
    sort_by: str = "created_at",
    order: str = "desc",
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    分页并多维度筛选查询系统日志
    """
    ensure_system_logs_table()
    conn = get_db_connection()
    if not conn:
        return False, "无法连接到 SQLite 数据库", {"total": 0, "logs": [], "page": page, "page_size": page_size}

    try:
        where_clauses = ["1=1"]
        params: List[Any] = []

        # 关键词模糊搜索
        if q and q.strip():
            kw = f"%{q.strip()}%"
            where_clauses.append("(query_text LIKE ? OR action LIKE ? OR error_message LIKE ? OR client_ip LIKE ?)")
            params.extend([kw, kw, kw, kw])

        # 日志类型筛选
        if log_type and log_type.strip():
            where_clauses.append("log_type = ?")
            params.append(log_type.strip())

        # 状态码筛选 (例如 '200' 成功 / 'error' 失败 >=400 / 具体的 404, 500)
        if status and status.strip():
            st = status.strip().lower()
            if st in ("200", "success", "ok"):
                where_clauses.append("status_code >= 200 AND status_code < 400")
            elif st in ("error", "fail", "failed", "500"):
                where_clauses.append("status_code >= 400")
            elif st.isdigit():
                where_clauses.append("status_code = ?")
                params.append(int(st))

        # 日期区间筛选 (YYYY-MM-DD)
        if start_date and start_date.strip():
            where_clauses.append("date(created_at) >= date(?)")
            params.append(start_date.strip())
        if end_date and end_date.strip():
            where_clauses.append("date(created_at) <= date(?)")
            params.append(end_date.strip())

        where_sql = " AND ".join(where_clauses)

        # 允许排序的字段白名单
        valid_sort_fields = {
            "created_at": "created_at",
            "duration_ms": "duration_ms",
            "status_code": "status_code",
            "result_count": "result_count",
            "id": "id",
        }
        sort_column = valid_sort_fields.get(sort_by, "created_at")
        sort_direction = "ASC" if str(order).lower() == "asc" else "DESC"

        # 查询总数
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM system_logs WHERE {where_sql}", tuple(params))
        total_count = cursor.fetchone()[0]

        # 计算分页
        page = max(1, int(page))
        page_size = max(1, min(200, int(page_size)))
        total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1
        offset = (page - 1) * page_size

        # 查询分页数据
        query_sql = f"""
            SELECT id, log_type, action, query_text, status_code, error_message,
                   duration_ms, result_count, client_ip, created_at
            FROM system_logs
            WHERE {where_sql}
            ORDER BY {sort_column} {sort_direction}
            LIMIT ? OFFSET ?
        """
        cursor.close()
        dict_cursor = conn.cursor(as_dict=True)
        dict_cursor.execute(query_sql, tuple(params + [page_size, offset]))
        logs = dict_cursor.fetchall() or []

        return True, "查询成功", {
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "logs": logs,
        }
    except Error as err:
        logger.error(f"查询系统日志失败: {err}")
        return False, f"查询失败: {str(err)}", {"total": 0, "logs": [], "page": page, "page_size": page_size}
    finally:
        conn.close()


def delete_logs_by_ids(ids: List[int]) -> Tuple[bool, str, int]:
    """
    批量删除指定 ID 的日志记录
    """
    if not ids:
        return True, "未指定待删除日志 ID", 0

    ensure_system_logs_table()
    conn = get_db_connection()
    if not conn:
        return False, "无法连接到数据库", 0

    try:
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(f"DELETE FROM system_logs WHERE id IN ({placeholders})", tuple(ids))
        deleted_count = cursor.rowcount
        conn.commit()
        return True, f"成功删除 {deleted_count} 条日志记录", deleted_count
    except Error as err:
        logger.error(f"删除系统日志失败: {err}")
        conn.rollback()
        return False, f"删除失败: {str(err)}", 0
    finally:
        cursor.close()
        conn.close()


def clear_all_logs() -> Tuple[bool, str, int]:
    """
    清空全部系统日志
    """
    ensure_system_logs_table()
    conn = get_db_connection()
    if not conn:
        return False, "无法连接到数据库", 0

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM system_logs")
        deleted_count = cursor.rowcount
        conn.commit()
        return True, f"已清空全部日志，共删除 {deleted_count} 条记录", deleted_count
    except Error as err:
        logger.error(f"清空日志失败: {err}")
        conn.rollback()
        return False, f"清空日志失败: {str(err)}", 0
    finally:
        cursor.close()
        conn.close()


def cleanup_logs_before_days(days: int = 7) -> Tuple[bool, str, int]:
    """
    清理指定天数之前的历史日志
    """
    days = max(1, int(days))
    ensure_system_logs_table()
    conn = get_db_connection()
    if not conn:
        return False, "无法连接到数据库", 0

    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM system_logs WHERE date(created_at) < date('now', 'localtime', ?)",
            (f"-{days} days",),
        )
        deleted_count = cursor.rowcount
        conn.commit()
        return True, f"已成功清理 {days} 天前的历史日志，共删除 {deleted_count} 条记录", deleted_count
    except Error as err:
        logger.error(f"清理历史日志失败: {err}")
        conn.rollback()
        return False, f"清理历史日志失败: {str(err)}", 0
    finally:
        cursor.close()
        conn.close()


def get_logs_summary_stats() -> Dict[str, Any]:
    """
    统计系统运行指标，供后台日志顶栏与仪表盘大盘使用
    """
    ensure_system_logs_table()
    conn = get_db_connection()
    default_stats = {
        "today_total": 0,
        "today_search": 0,
        "today_transfer": 0,
        "today_api": 0,
        "today_errors": 0,
        "today_success_rate": 100.0,
        "today_avg_duration_ms": 0,
        "total_logs_count": 0,
    }
    if not conn:
        return default_stats

    try:
        cursor = conn.cursor(as_dict=True)

        # 统计历史总数
        cursor.execute("SELECT COUNT(*) as total FROM system_logs")
        total_row = cursor.fetchone()
        total_logs = total_row["total"] if total_row else 0

        # 统计今日数据
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_reqs,
                SUM(CASE WHEN log_type = 'search' THEN 1 ELSE 0 END) as search_reqs,
                SUM(CASE WHEN log_type = 'transfer' THEN 1 ELSE 0 END) as transfer_reqs,
                SUM(CASE WHEN log_type = 'api' THEN 1 ELSE 0 END) as api_reqs,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_reqs,
                AVG(duration_ms) as avg_duration
            FROM system_logs
            WHERE date(created_at) = date('now', 'localtime')
            """
        )
        row = cursor.fetchone() or {}
        today_total = row.get("total_reqs") or 0
        today_search = row.get("search_reqs") or 0
        today_transfer = row.get("transfer_reqs") or 0
        today_api = row.get("api_reqs") or 0
        today_errors = row.get("error_reqs") or 0
        avg_duration = round(float(row.get("avg_duration") or 0), 1)

        success_rate = (
            round(((today_total - today_errors) / today_total) * 100, 1)
            if today_total > 0
            else 100.0
        )

        return {
            "today_total": today_total,
            "today_search": today_search,
            "today_transfer": today_transfer,
            "today_api": today_api,
            "today_errors": today_errors,
            "today_success_rate": success_rate,
            "today_avg_duration_ms": avg_duration,
            "total_logs_count": total_logs,
        }
    except Error as err:
        logger.error(f"获取日志统计指标失败: {err}")
        return default_stats
    finally:
        conn.close()
