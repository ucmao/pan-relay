import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)
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
                SUM(CASE WHEN action LIKE 'search.api%' OR action LIKE 'api.%' OR log_type = 'api' THEN 1 ELSE 0 END) as api_reqs,
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


def query_search_logs(
    page: int = 1,
    page_size: int = 15,
    q: str = "",
    channel: str = "",
    result_filter: str = "",
    start_date: str = "",
    end_date: str = "",
    sort_by: str = "created_at",
    order: str = "desc",
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    专门查询搜索业务明细日志（包括 Web 前台搜索与开放 API 搜索）。
    """
    conn = get_db_connection()
    if not conn:
        return False, "无法连接到 SQLite 数据库", {"total": 0, "logs": [], "page": page, "page_size": page_size}

    try:
        where_clauses = ["log_type = 'search'"]
        params: List[Any] = []

        # 渠道过滤: web / api
        if channel == "web":
            where_clauses.append("action LIKE 'search.web%'")
        elif channel == "api":
            where_clauses.append("action LIKE 'search.api%'")

        # 结果命中过滤: has_results (命中>0) / zero_results (命中=0)
        if result_filter == "has_results":
            where_clauses.append("result_count > 0")
        elif result_filter == "zero_results":
            where_clauses.append("result_count = 0")

        # 关键词模糊搜索
        if q and q.strip():
            kw = f"%{q.strip()}%"
            where_clauses.append("(query_text LIKE ? OR client_ip LIKE ?)")
            params.extend([kw, kw])

        # 日期区间筛选 (YYYY-MM-DD)
        if start_date and start_date.strip():
            where_clauses.append("date(created_at) >= date(?)")
            params.append(start_date.strip())
        if end_date and end_date.strip():
            where_clauses.append("date(created_at) <= date(?)")
            params.append(end_date.strip())

        where_sql = " AND ".join(where_clauses)

        valid_sort_fields = {
            "created_at": "created_at",
            "duration_ms": "duration_ms",
            "result_count": "result_count",
            "id": "id",
        }
        sort_column = valid_sort_fields.get(sort_by, "created_at")
        sort_direction = "ASC" if str(order).lower() == "asc" else "DESC"

        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM system_logs WHERE {where_sql}", tuple(params))
        total_count = cursor.fetchone()[0]

        page = max(1, int(page))
        page_size = max(1, min(200, int(page_size)))
        total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1
        offset = (page - 1) * page_size

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
        rows = dict_cursor.fetchall() or []

        formatted_logs = []
        for r in rows:
            action = r.get("action") or ""
            is_api = action.startswith("search.api")
            channel_type = "api" if is_api else "web"
            channel_label = "开放 API" if is_api else "Web 前台"

            raw_query = (r.get("query_text") or "").strip()
            keyword = raw_query
            cloud_name = ""
            if " [cloud=" in raw_query and raw_query.endswith("]"):
                parts = raw_query.rsplit(" [cloud=", 1)
                keyword = parts[0]
                cloud_name = parts[1][:-1]
                if cloud_name == "all":
                    cloud_name = ""

            formatted_logs.append({
                "id": r["id"],
                "channel": channel_type,
                "channel_label": channel_label,
                "action": action,
                "raw_query": raw_query,
                "keyword": keyword or "—",
                "cloud_name": cloud_name,
                "result_count": r.get("result_count", 0),
                "status_code": r.get("status_code", 200),
                "error_message": r.get("error_message"),
                "duration_ms": r.get("duration_ms", 0),
                "client_ip": r.get("client_ip") or "—",
                "created_at": r.get("created_at") or "",
            })

        return True, "查询成功", {
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "logs": formatted_logs,
        }
    except Error as err:
        logger.error(f"查询搜索日志失败: {err}")
        return False, f"查询失败: {str(err)}", {"total": 0, "logs": [], "page": page, "page_size": page_size}
    finally:
        conn.close()


def get_search_analytics_stats() -> Dict[str, Any]:
    """
    统计搜索行为与分析指标（今日搜索量、Web/API占比、命中率、Top 搜索热词、高频零结果待补词）
    """
    conn = get_db_connection()
    default_stats = {
        "today_total_searches": 0,
        "today_web_searches": 0,
        "today_api_searches": 0,
        "today_hit_searches": 0,
        "today_zero_searches": 0,
        "today_hit_rate": 100.0,
        "today_avg_duration_ms": 0,
        "top_keywords": [],
        "top_zero_keywords": [],
    }
    if not conn:
        return default_stats

    try:
        cursor = conn.cursor(as_dict=True)

        # 1. 统计今日搜索汇总
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_searches,
                SUM(CASE WHEN action LIKE 'search.web%' THEN 1 ELSE 0 END) as web_searches,
                SUM(CASE WHEN action LIKE 'search.api%' THEN 1 ELSE 0 END) as api_searches,
                SUM(CASE WHEN result_count > 0 THEN 1 ELSE 0 END) as hit_searches,
                SUM(CASE WHEN result_count = 0 THEN 1 ELSE 0 END) as zero_searches,
                AVG(duration_ms) as avg_duration
            FROM system_logs
            WHERE log_type = 'search'
              AND date(created_at) = date('now', 'localtime')
            """
        )
        row = cursor.fetchone() or {}
        today_total = row.get("total_searches") or 0
        today_web = row.get("web_searches") or 0
        today_api = row.get("api_searches") or 0
        today_hit = row.get("hit_searches") or 0
        today_zero = row.get("zero_searches") or 0
        avg_duration = round(float(row.get("avg_duration") or 0), 1)

        hit_rate = (
            round((today_hit / today_total) * 100, 1)
            if today_total > 0
            else 100.0
        )

        # 2. 统计近 7 天 Top 10 热门搜索词
        cursor.execute(
            """
            SELECT
                query_text,
                COUNT(*) as search_count,
                AVG(result_count) as avg_results,
                MAX(created_at) as last_searched
            FROM system_logs
            WHERE log_type = 'search'
              AND query_text IS NOT NULL AND query_text != ''
              AND date(created_at) >= date('now', 'localtime', '-7 days')
            GROUP BY query_text
            ORDER BY search_count DESC, last_searched DESC
            LIMIT 10
            """
        )
        top_raw_keywords = cursor.fetchall() or []
        top_keywords = []
        for item in top_raw_keywords:
            raw = (item["query_text"] or "").strip()
            clean_kw = raw.split(" [cloud=")[0] if " [cloud=" in raw else raw
            top_keywords.append({
                "keyword": clean_kw,
                "count": item["search_count"],
                "avg_results": round(float(item["avg_results"] or 0), 1),
                "last_searched": item["last_searched"],
            })

        # 3. 统计近 7 天高频零结果关键词 Top 10 (帮助站长补库)
        cursor.execute(
            """
            SELECT
                query_text,
                COUNT(*) as zero_count,
                MAX(created_at) as last_searched
            FROM system_logs
            WHERE log_type = 'search'
              AND result_count = 0
              AND query_text IS NOT NULL AND query_text != ''
              AND date(created_at) >= date('now', 'localtime', '-7 days')
            GROUP BY query_text
            ORDER BY zero_count DESC, last_searched DESC
            LIMIT 10
            """
        )
        zero_raw_keywords = cursor.fetchall() or []
        top_zero_keywords = []
        for item in zero_raw_keywords:
            raw = (item["query_text"] or "").strip()
            clean_kw = raw.split(" [cloud=")[0] if " [cloud=" in raw else raw
            top_zero_keywords.append({
                "keyword": clean_kw,
                "count": item["zero_count"],
                "last_searched": item["last_searched"],
            })

        return {
            "today_total_searches": today_total,
            "today_web_searches": today_web,
            "today_api_searches": today_api,
            "today_hit_searches": today_hit,
            "today_zero_searches": today_zero,
            "today_hit_rate": hit_rate,
            "today_avg_duration_ms": avg_duration,
            "top_keywords": top_keywords,
            "top_zero_keywords": top_zero_keywords,
        }
    except Error as err:
        logger.error(f"获取搜索分析统计失败: {err}")
        return default_stats
    finally:
        conn.close()
