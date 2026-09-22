import csv
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from flask import has_request_context, request

from src.db.logs import (
    cleanup_logs_before_days,
    clear_all_logs as db_clear_all_logs,
    delete_logs_by_filter,
    delete_logs_by_ids,
    get_logs_summary_stats,
    get_search_analytics_stats,
    insert_system_log,
    query_logs_for_export,
    query_search_logs,
    query_system_logs,
)

logger = logging.getLogger(__name__)


def get_current_client_ip() -> str:
    """
    从 Flask 请求上下文中获取客户端 IP 地址，兼容反向代理
    """
    if not has_request_context():
        return "127.0.0.1"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def record_log(
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
    安全记录一条系统运行/审计日志。
    具备全局异常捕获，即使数据库瞬时报错也绝不影响核心业务运行。
    """
    try:
        if not client_ip:
            client_ip = get_current_client_ip()
        return insert_system_log(
            log_type=log_type,
            action=action,
            query_text=query_text,
            status_code=status_code,
            error_message=error_message,
            duration_ms=duration_ms,
            result_count=result_count,
            client_ip=client_ip,
        )
    except Exception as err:
        logger.warning(f"静默记录日志时发生异常: {err}")
        return None


def list_logs(
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
    分页查询系统日志
    """
    return query_system_logs(
        page=page,
        page_size=page_size,
        q=q,
        log_type=log_type,
        status=status,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        order=order,
    )


def delete_logs(ids: List[int]) -> Tuple[bool, str, int]:
    """
    批量删除日志
    """
    return delete_logs_by_ids(ids)


def delete_logs_with_filter(
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
    按过滤条件或 ID 列表批量删除日志
    """
    return delete_logs_by_filter(
        ids=ids,
        q=q,
        log_type=log_type,
        status=status,
        channel=channel,
        result_filter=result_filter,
        start_date=start_date,
        end_date=end_date,
    )


def clear_all_logs() -> Tuple[bool, str, int]:
    """
    清空全部日志
    """
    return db_clear_all_logs()


def cleanup_old_logs(days: int = 7) -> Tuple[bool, str, int]:
    """
    清理指定天数之前的旧日志
    """
    return cleanup_logs_before_days(days)


def get_logs_summary() -> Dict[str, Any]:
    """
    获取后台日志 KPI 统计指标
    """
    return get_logs_summary_stats()


def export_logs_csv(
    ids: Optional[List[int]] = None,
    q: str = "",
    log_type: str = "",
    status: str = "",
    channel: str = "",
    result_filter: str = "",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """
    导出系统日志为带 UTF-8 BOM 的 CSV 文本
    """
    logs = query_logs_for_export(
        ids=ids,
        q=q,
        log_type=log_type,
        status=status,
        channel=channel,
        result_filter=result_filter,
        start_date=start_date,
        end_date=end_date,
    )

    output = io.StringIO()
    # 写入 UTF-8 BOM 便于 Excel 正常打开中文无乱码
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "日志ID",
        "时间",
        "类型",
        "动作/接口",
        "搜索词/请求内容",
        "状态码",
        "耗时(ms)",
        "命中数量",
        "客户端IP",
        "异常/错误信息",
    ])

    for row in logs:
        writer.writerow([
            row.get("id"),
            row.get("created_at"),
            row.get("log_type"),
            row.get("action"),
            row.get("query_text") or "",
            row.get("status_code"),
            row.get("duration_ms"),
            row.get("result_count"),
            row.get("client_ip") or "",
            row.get("error_message") or "",
        ])

    return output.getvalue()


def list_search_logs(
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
    分页查询搜索业务日志（Web / API）
    """
    return query_search_logs(
        page=page,
        page_size=page_size,
        q=q,
        channel=channel,
        result_filter=result_filter,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        order=order,
    )


def get_search_analytics() -> Dict[str, Any]:
    """
    获取搜索业务分析指标与热词榜
    """
    return get_search_analytics_stats()
