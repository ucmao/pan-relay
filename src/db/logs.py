import datetime
import math
import logging
from datetime import date, timedelta
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
            "log_type": "log_type",
            "action": "action",
            "query_text": "query_text",
            "client_ip": "client_ip",
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


def delete_logs_by_filter(
    ids: Optional[List[int]] = None,
    q: str = "",
    log_type: str = "",
    status: str = "",
    channel: str = "",
    result_filter: str = "",
    start_date: str = "",
    end_date: str = "",
) -> Tuple[bool, str, int]:
    """
    根据指定条件（或全选筛选条件）批量删除日志
    """
    conn = get_db_connection()
    if not conn:
        return False, "无法连接到数据库", 0

    try:
        where_clauses = ["1=1"]
        params: List[Any] = []

        if ids and len(ids) > 0:
            placeholders = ",".join(["?"] * len(ids))
            where_clauses.append(f"id IN ({placeholders})")
            params.extend(ids)
        else:
            if log_type and log_type.strip():
                where_clauses.append("log_type = ?")
                params.append(log_type.strip())

            if channel == "web":
                where_clauses.append("action LIKE 'search.web%'")
            elif channel == "api":
                where_clauses.append("action LIKE 'search.api%'")

            if result_filter == "has_results":
                where_clauses.append("result_count > 0")
            elif result_filter == "zero_results":
                where_clauses.append("result_count = 0")

            if q and q.strip():
                kw = f"%{q.strip()}%"
                where_clauses.append("(query_text LIKE ? OR action LIKE ? OR error_message LIKE ? OR client_ip LIKE ?)")
                params.extend([kw, kw, kw, kw])

            if status and status.strip():
                st = status.strip().lower()
                if st in ("200", "success", "ok"):
                    where_clauses.append("status_code >= 200 AND status_code < 400")
                elif st in ("error", "fail", "failed", "500"):
                    where_clauses.append("status_code >= 400")
                elif st.isdigit():
                    where_clauses.append("status_code = ?")
                    params.append(int(st))

            if start_date and start_date.strip():
                where_clauses.append("date(created_at) >= date(?)")
                params.append(start_date.strip())
            if end_date and end_date.strip():
                where_clauses.append("date(created_at) <= date(?)")
                params.append(end_date.strip())

        where_sql = " AND ".join(where_clauses)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM system_logs WHERE {where_sql}", tuple(params))
        deleted_count = cursor.rowcount
        conn.commit()
        return True, f"成功删除 {deleted_count} 条日志记录", deleted_count
    except Error as err:
        logger.error(f"批量删除日志失败: {err}")
        conn.rollback()
        return False, f"删除失败: {str(err)}", 0
    finally:
        cursor.close()
        conn.close()


def query_logs_for_export(
    ids: Optional[List[int]] = None,
    q: str = "",
    log_type: str = "",
    status: str = "",
    channel: str = "",
    result_filter: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 20000,
) -> List[Dict[str, Any]]:
    """
    查询用于导出 CSV 的日志数据（支持勾选 ID 或全量多维过滤）
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        where_clauses = ["1=1"]
        params: List[Any] = []

        if ids and len(ids) > 0:
            placeholders = ",".join(["?"] * len(ids))
            where_clauses.append(f"id IN ({placeholders})")
            params.extend(ids)
        else:
            if log_type and log_type.strip():
                where_clauses.append("log_type = ?")
                params.append(log_type.strip())

            if channel == "web":
                where_clauses.append("action LIKE 'search.web%'")
            elif channel == "api":
                where_clauses.append("action LIKE 'search.api%'")

            if result_filter == "has_results":
                where_clauses.append("result_count > 0")
            elif result_filter == "zero_results":
                where_clauses.append("result_count = 0")

            if q and q.strip():
                kw = f"%{q.strip()}%"
                where_clauses.append("(query_text LIKE ? OR action LIKE ? OR error_message LIKE ? OR client_ip LIKE ?)")
                params.extend([kw, kw, kw, kw])

            if status and status.strip():
                st = status.strip().lower()
                if st in ("200", "success", "ok"):
                    where_clauses.append("status_code >= 200 AND status_code < 400")
                elif st in ("error", "fail", "failed", "500"):
                    where_clauses.append("status_code >= 400")
                elif st.isdigit():
                    where_clauses.append("status_code = ?")
                    params.append(int(st))

            if start_date and start_date.strip():
                where_clauses.append("date(created_at) >= date(?)")
                params.append(start_date.strip())
            if end_date and end_date.strip():
                where_clauses.append("date(created_at) <= date(?)")
                params.append(end_date.strip())

        where_sql = " AND ".join(where_clauses)
        dict_cursor = conn.cursor(as_dict=True)
        dict_cursor.execute(
            f"""
            SELECT id, log_type, action, query_text, status_code, error_message,
                   duration_ms, result_count, client_ip, created_at
            FROM system_logs
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            tuple(params + [limit]),
        )
        return dict_cursor.fetchall() or []
    except Error as err:
        logger.error(f"导出查询日志失败: {err}")
        return []
    finally:
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
                SUM(CASE WHEN log_type = 'transfer' AND status_code < 400 THEN 1 ELSE 0 END) as transfer_success_reqs,
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
        today_transfer_success = row.get("transfer_success_reqs") or 0
        today_api = row.get("api_reqs") or 0
        today_errors = row.get("error_reqs") or 0
        avg_duration = round(float(row.get("avg_duration") or 0), 1)

        success_rate = (
            round(((today_total - today_errors) / today_total) * 100, 1)
            if today_total > 0
            else 100.0
        )
        transfer_success_rate = (
            round((today_transfer_success / today_transfer) * 100, 1)
            if today_transfer > 0
            else 100.0
        )

        return {
            "today_total": today_total,
            "today_search": today_search,
            "today_transfer": today_transfer,
            "today_transfer_success": today_transfer_success,
            "today_transfer_success_rate": transfer_success_rate,
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
            "channel": "action",
            "action": "action",
            "keyword": "query_text",
            "query_text": "query_text",
            "client_ip": "client_ip",
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


def get_usage_trend(days: int = 7) -> Dict[str, Any]:
    """
    获取指定周期内的 API 与搜索每日调用量与成功解析趋势数据（含平滑贝塞尔曲线及渐变闭合路径）
    """
    today = date.today()
    conn = get_db_connection()
    if not conn:
        return {
            "trend": [],
            "max_val": 0,
            "y_max": 10,
            "calls_path": "",
            "successes_path": "",
            "calls_area_path": "",
            "successes_area_path": "",
            "calls_line": "",
            "successes_line": "",
            "calls_area": "",
            "successes_area": "",
            "y_ticks": [],
        }

    try:
        cursor = conn.cursor(as_dict=True)
        if days == 0:
            cursor.execute("SELECT min(date(created_at)) as min_date FROM system_logs WHERE log_type = 'search'")
            row_min = cursor.fetchone()
            if row_min and row_min.get("min_date"):
                try:
                    min_date = datetime.datetime.strptime(row_min["min_date"], "%Y-%m-%d").date()
                    total_days = max(7, (today - min_date).days + 1)
                except ValueError:
                    total_days = 7
            else:
                total_days = 7
        else:
            total_days = max(1, days)

        sql = (
            "SELECT date(created_at) as day, "
            "COUNT(*) as calls, "
            "SUM(CASE WHEN result_count > 0 AND status_code < 400 THEN 1 ELSE 0 END) as successes "
            "FROM system_logs "
            "WHERE log_type = 'search' "
        )
        params: List[Any] = []
        if days > 0:
            sql += "AND date(created_at) >= date('now', 'localtime', ?) "
            params.append(f"-{total_days - 1} days")
        sql += "GROUP BY day ORDER BY day ASC"

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall() or []
        row_map = {row["day"]: row for row in rows if row.get("day")}

        daily_stats = []
        max_val = 0
        for i in range(total_days - 1, -1, -1):
            day_date = today - timedelta(days=i)
            day_str = day_date.strftime("%Y-%m-%d")
            short_date = day_date.strftime("%m-%d")
            item = row_map.get(day_str)
            calls = item["calls"] if item and item.get("calls") else 0
            successes = item["successes"] if item and item.get("successes") else 0
            if calls > max_val:
                max_val = calls
            daily_stats.append({
                "date": day_str,
                "short_date": short_date,
                "calls": calls,
                "successes": successes,
                "failures": max(0, calls - successes),
            })

        num_points = len(daily_stats)
        if num_points <= 10:
            step = 1
        elif num_points <= 31:
            step = 5
        elif num_points <= 90:
            step = 15
        elif num_points <= 180:
            step = 30
        else:
            step = 60

        for idx, item in enumerate(daily_stats):
            item["show_label"] = (idx % step == 0) or (idx == num_points - 1)

        def _calc_nice_ticks(mv: int, top_m: float = 20.0, h: float = 160.0):
            if mv <= 0:
                ym = 10
                raw_ticks = [10, 8, 6, 4, 2, 0]
            elif mv <= 3:
                ym = 3
                raw_ticks = [3, 2, 1, 0]
            elif mv <= 5:
                ym = 5
                raw_ticks = [5, 4, 3, 2, 1, 0]
            elif mv <= 8:
                ym = 8
                raw_ticks = [8, 6, 4, 2, 0]
            elif mv <= 12:
                ym = 12
                raw_ticks = [12, 9, 6, 3, 0]
            elif mv <= 15:
                ym = 15
                raw_ticks = [15, 12, 9, 6, 3, 0]
            elif mv <= 20:
                ym = 20
                raw_ticks = [20, 15, 10, 5, 0]
            elif mv <= 30:
                ym = 30
                raw_ticks = [30, 24, 18, 12, 6, 0]
            elif mv <= 50:
                ym = math.ceil(mv / 10) * 10
                step_val = 10 if ym <= 30 else (ym // 5)
                raw_ticks = list(range(ym, -1, -step_val))
                if raw_ticks[-1] != 0:
                    raw_ticks.append(0)
            elif mv <= 100:
                ym = math.ceil(mv / 10) * 10
                step_val = max(10, ym // 5)
                raw_ticks = list(range(ym, -1, -step_val))
                if raw_ticks[-1] != 0:
                    raw_ticks.append(0)
            else:
                mag = 10 ** math.floor(math.log10(mv))
                norm = mv / mag
                if norm <= 1.5:
                    step_val = int(0.25 * mag) if mag >= 10 else 1
                    ym = int(1.5 * mag)
                elif norm <= 2.0:
                    step_val = int(0.4 * mag) if mag >= 10 else 1
                    ym = int(2.0 * mag)
                elif norm <= 5.0:
                    step_val = int(0.5 * mag) if mag >= 10 else 1
                    ym = int(math.ceil(norm) * mag)
                else:
                    step_val = int(1.0 * mag) if mag >= 10 else 1
                    ym = int(math.ceil(norm / 2) * 2 * mag)
                raw_ticks = list(range(ym, -1, -step_val))
                if raw_ticks[-1] != 0:
                    raw_ticks.append(0)

            ticks = []
            for v in raw_ticks:
                y_pos = round(top_m + h * (1 - v / ym), 1)
                ticks.append({
                    "val": f"{v:,}",
                    "raw_val": v,
                    "y": y_pos,
                })
            return ym, ticks

        def _points_to_bezier_path(coords: List[Tuple[float, float]], min_y: float = 20.0, max_y: float = 180.0, tension: float = 0.2) -> str:
            if not coords:
                return ""
            if len(coords) == 1:
                return f"M {coords[0][0]:.1f} {coords[0][1]:.1f}"
            if len(coords) == 2:
                return f"M {coords[0][0]:.1f} {coords[0][1]:.1f} L {coords[1][0]:.1f} {coords[1][1]:.1f}"

            path = [f"M {coords[0][0]:.1f} {coords[0][1]:.1f}"]
            n = len(coords)
            for i in range(n - 1):
                p0 = coords[max(0, i - 1)]
                p1 = coords[i]
                p2 = coords[i + 1]
                p3 = coords[min(n - 1, i + 2)]

                if p1[1] == max_y and p2[1] == max_y:
                    path.append(f"L {p2[0]:.1f} {p2[1]:.1f}")
                    continue

                cp1x = p1[0] + (p2[0] - p0[0]) * tension
                cp1y = max(min_y, min(max_y, p1[1] + (p2[1] - p0[1]) * tension))
                cp2x = p2[0] - (p3[0] - p1[0]) * tension
                cp2y = max(min_y, min(max_y, p2[1] - (p3[1] - p1[1]) * tension))

                path.append(f"C {cp1x:.1f} {cp1y:.1f}, {cp2x:.1f} {cp2y:.1f}, {p2[0]:.1f} {p2[1]:.1f}")
            return " ".join(path)

        width = 620
        height = 160
        left_margin = 50
        top_margin = 20
        bottom_y = top_margin + height

        y_max, y_ticks = _calc_nice_ticks(max_val, top_margin, height)

        coords_calls = []
        coords_successes = []
        points_calls = []
        points_successes = []

        for i, item in enumerate(daily_stats):
            x = round(left_margin + i * (width / max(1, num_points - 1)), 1)
            y_c = round(top_margin + height * (1 - item["calls"] / y_max), 1)
            y_s = round(top_margin + height * (1 - item["successes"] / y_max), 1)
            item["x"] = x
            item["y_calls"] = y_c
            item["y_successes"] = y_s
            coords_calls.append((x, y_c))
            coords_successes.append((x, y_s))
            points_calls.append(f"{x},{y_c}")
            points_successes.append(f"{x},{y_s}")

        calls_path = _points_to_bezier_path(coords_calls, min_y=top_margin, max_y=bottom_y)
        successes_path = _points_to_bezier_path(coords_successes, min_y=top_margin, max_y=bottom_y)

        first_x = daily_stats[0]["x"]
        last_x = daily_stats[-1]["x"]

        calls_area_path = f"{calls_path} L {last_x:.1f} {bottom_y:.1f} L {first_x:.1f} {bottom_y:.1f} Z"
        successes_area_path = f"{successes_path} L {last_x:.1f} {bottom_y:.1f} L {first_x:.1f} {bottom_y:.1f} Z"

        calls_line = " ".join(points_calls)
        successes_line = " ".join(points_successes)
        calls_area = f"{first_x},{bottom_y} {calls_line} {last_x},{bottom_y}"
        successes_area = f"{first_x},{bottom_y} {successes_line} {last_x},{bottom_y}"

        return {
            "trend": daily_stats,
            "max_val": max_val,
            "y_max": y_max,
            "calls_path": calls_path,
            "successes_path": successes_path,
            "calls_area_path": calls_area_path,
            "successes_area_path": successes_area_path,
            "calls_line": calls_line,
            "successes_line": successes_line,
            "calls_area": calls_area,
            "successes_area": successes_area,
            "y_ticks": y_ticks,
        }
    except Exception as err:
        logger.error(f"获取趋势图表数据失败: {err}")
        return {
            "trend": [],
            "max_val": 0,
            "y_max": 10,
            "calls_path": "",
            "successes_path": "",
            "calls_area_path": "",
            "successes_area_path": "",
            "calls_line": "",
            "successes_line": "",
            "calls_area": "",
            "successes_area": "",
            "y_ticks": [],
        }
    finally:
        conn.close()


def get_platform_distribution(days: int = 7) -> Dict[str, Any]:
    """
    统计指定周期内各平台/云盘及服务渠道的使用分布（含 SVG 环形 Donut 切片路径）
    """
    conn = get_db_connection()
    if not conn:
        return {
            "total_calls": 0,
            "total_calls_formatted": "0",
            "total_successes": 0,
            "total_successes_formatted": "0",
            "total_failures": 0,
            "total_failures_formatted": "0",
            "total_success_rate": 100.0,
            "platform_count": 0,
            "items": [],
        }

    try:
        cursor = conn.cursor(as_dict=True)
        sql = (
            "SELECT "
            "  CASE "
            "    WHEN action LIKE 'search.web%' THEN 'Web 前台搜索' "
            "    WHEN action LIKE 'search.api%' THEN 'API 开放接口' "
            "    ELSE '其他检索调用' "
            "  END as platform_name, "
            "  COUNT(*) as calls, "
            "  SUM(CASE WHEN result_count > 0 AND status_code < 400 THEN 1 ELSE 0 END) as successes "
            "FROM system_logs "
            "WHERE log_type = 'search' "
        )
        params: List[Any] = []
        if days > 0:
            sql += "AND date(created_at) >= date('now', 'localtime', ?) "
            params.append(f"-{days - 1} days")
        sql += "GROUP BY platform_name ORDER BY calls DESC"

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall() or []
        total_calls = sum(r["calls"] for r in rows) if rows else 0

        PALETTE = [
            "#4f46e5", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6",
            "#06b6d4", "#ef4444", "#3b82f6", "#14b8a6", "#f97316",
            "#6366f1", "#84cc16", "#d946ef", "#0284c7", "#e11d48",
            "#7c3aed", "#059669", "#d97706", "#2563eb", "#db2777",
        ]

        items = []
        if total_calls > 0:
            cx, cy = 100.0, 100.0
            r_out, r_in = 88.0, 64.0
            current_angle = 0.0

            for idx, row in enumerate(rows):
                name = row["platform_name"]
                calls = row["calls"]
                successes = row["successes"] or 0
                failures = max(0, calls - successes)
                success_rate = round((successes / calls) * 100, 1) if calls > 0 else 0.0
                percentage = round((calls / total_calls) * 100, 1)
                color = PALETTE[idx % len(PALETTE)]

                slice_angle = (calls / total_calls) * 2 * math.pi
                if slice_angle >= 2 * math.pi - 1e-4:
                    slice_angle = 2 * math.pi - 1e-4

                start_angle = current_angle
                end_angle = current_angle + slice_angle
                current_angle = end_angle

                x1_out = cx + r_out * math.sin(start_angle)
                y1_out = cy - r_out * math.cos(start_angle)
                x2_out = cx + r_out * math.sin(end_angle)
                y2_out = cy - r_out * math.cos(end_angle)

                x2_in = cx + r_in * math.sin(end_angle)
                y2_in = cy - r_in * math.cos(end_angle)
                x1_in = cx + r_in * math.sin(start_angle)
                y1_in = cy - r_in * math.cos(start_angle)

                large_arc = 1 if slice_angle > math.pi else 0

                path_d = (
                    f"M {x1_out:.2f} {y1_out:.2f} "
                    f"A {r_out} {r_out} 0 {large_arc} 1 {x2_out:.2f} {y2_out:.2f} "
                    f"L {x2_in:.2f} {y2_in:.2f} "
                    f"A {r_in} {r_in} 0 {large_arc} 0 {x1_in:.2f} {y1_in:.2f} Z"
                )

                items.append({
                    "platform": name,
                    "calls": calls,
                    "calls_formatted": f"{calls:,}",
                    "successes": successes,
                    "successes_formatted": f"{successes:,}",
                    "failures": failures,
                    "failures_formatted": f"{failures:,}",
                    "success_rate": success_rate,
                    "percentage": percentage,
                    "color": color,
                    "path_d": path_d,
                })

        total_successes = sum(r["successes"] or 0 for r in rows) if rows else 0
        total_failures = max(0, total_calls - total_successes)
        total_success_rate = round((total_successes / total_calls) * 100, 1) if total_calls > 0 else 100.0

        return {
            "total_calls": total_calls,
            "total_calls_formatted": f"{total_calls:,}",
            "total_successes": total_successes,
            "total_successes_formatted": f"{total_successes:,}",
            "total_failures": total_failures,
            "total_failures_formatted": f"{total_failures:,}",
            "total_success_rate": total_success_rate,
            "platform_count": len(rows),
            "items": items,
        }
    except Exception as err:
        logger.error(f"获取平台分布数据失败: {err}")
        return {
            "total_calls": 0,
            "total_calls_formatted": "0",
            "total_successes": 0,
            "total_successes_formatted": "0",
            "total_failures": 0,
            "total_failures_formatted": "0",
            "total_success_rate": 100.0,
            "platform_count": 0,
            "items": [],
        }
    finally:
        conn.close()


def get_top_zero_keywords(days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
    """
    统计指定周期内高频零结果关键词 Top 10 (帮助站长定向补库)
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(as_dict=True)
        sql = (
            "SELECT "
            "  query_text, "
            "  COUNT(*) as zero_count, "
            "  MAX(created_at) as last_searched "
            "FROM system_logs "
            "WHERE log_type = 'search' "
            "  AND result_count = 0 "
            "  AND query_text IS NOT NULL AND query_text != '' "
        )
        params: List[Any] = []
        if days > 0:
            sql += "AND date(created_at) >= date('now', 'localtime', ?) "
            params.append(f"-{days - 1} days")
        sql += "GROUP BY query_text ORDER BY zero_count DESC, last_searched DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall() or []

        # 整理关键词
        aggregated: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            raw = (r.get("query_text") or "").strip()
            clean_kw = raw.split(" [cloud=")[0].split(" [title=")[0].split(" [reason=")[0].strip()
            if not clean_kw:
                continue
            if clean_kw in aggregated:
                aggregated[clean_kw]["count"] += r["zero_count"]
                if str(r.get("last_searched", "")) > str(aggregated[clean_kw]["last_searched"]):
                    aggregated[clean_kw]["last_searched"] = r["last_searched"]
            else:
                aggregated[clean_kw] = {
                    "keyword": clean_kw,
                    "count": r["zero_count"],
                    "last_searched": r.get("last_searched", ""),
                }

        sorted_items = sorted(aggregated.values(), key=lambda x: x["count"], reverse=True)[:limit]
        max_count = max((item["count"] for item in sorted_items), default=1)
        for item in sorted_items:
            item["pct"] = round((item["count"] / max_count) * 100, 1)

        return sorted_items
    except Exception as err:
        logger.error(f"获取零结果搜索词失败: {err}")
        return []
    finally:
        conn.close()


def get_top_hot_keywords(days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
    """
    统计指定周期内热门搜索关键词 Top 10
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(as_dict=True)
        sql = (
            "SELECT "
            "  query_text, "
            "  COUNT(*) as search_count, "
            "  AVG(result_count) as avg_results, "
            "  MAX(created_at) as last_searched "
            "FROM system_logs "
            "WHERE log_type = 'search' "
            "  AND query_text IS NOT NULL AND query_text != '' "
        )
        params: List[Any] = []
        if days > 0:
            sql += "AND date(created_at) >= date('now', 'localtime', ?) "
            params.append(f"-{days - 1} days")
        sql += "GROUP BY query_text ORDER BY search_count DESC, last_searched DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall() or []

        aggregated: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            raw = (r.get("query_text") or "").strip()
            clean_kw = raw.split(" [cloud=")[0].split(" [title=")[0].split(" [reason=")[0].strip()
            if not clean_kw:
                continue
            avg_res = round(float(r.get("avg_results") or 0), 1)
            if clean_kw in aggregated:
                aggregated[clean_kw]["count"] += r["search_count"]
                if str(r.get("last_searched", "")) > str(aggregated[clean_kw]["last_searched"]):
                    aggregated[clean_kw]["last_searched"] = r["last_searched"]
            else:
                aggregated[clean_kw] = {
                    "keyword": clean_kw,
                    "count": r["search_count"],
                    "avg_results": avg_res,
                    "last_searched": r.get("last_searched", ""),
                }

        sorted_items = sorted(aggregated.values(), key=lambda x: x["count"], reverse=True)[:limit]
        max_count = max((item["count"] for item in sorted_items), default=1)
        for item in sorted_items:
            item["pct"] = round((item["count"] / max_count) * 100, 1)

        return sorted_items
    except Exception as err:
        logger.error(f"获取热门搜索词失败: {err}")
        return []
    finally:
        conn.close()

