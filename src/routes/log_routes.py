import logging
from flask import Blueprint, Response, jsonify, render_template, request

from src.services.log_service import (
    cleanup_old_logs,
    clear_all_logs,
    delete_logs,
    export_logs_csv,
    get_logs_summary,
    list_logs,
)
from src.utils.auth_utils import token_required

logger = logging.getLogger(__name__)

log_bp = Blueprint("logs", __name__)


@log_bp.route("/admin/logs", methods=["GET"])
@token_required
def logs_page():
    """
    渲染后台运行日志管理页面
    """
    return render_template("admin_logs.html", active_page="logs")


@log_bp.route("/admin/api/logs", methods=["GET"])
@token_required
def get_logs_api():
    """
    分页并多维度筛选查询系统日志
    """
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 15, type=int)
    q = request.args.get("q", "", type=str)
    log_type = request.args.get("log_type", "", type=str)
    status = request.args.get("status", "", type=str)
    start_date = request.args.get("start_date", "", type=str)
    end_date = request.args.get("end_date", "", type=str)
    sort_by = request.args.get("sort_by", "created_at", type=str)
    order = request.args.get("order", "desc", type=str)

    success, message, data = list_logs(
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
    if not success:
        return jsonify({"success": False, "message": message}), 500
    return jsonify({"success": True, "data": data})


@log_bp.route("/admin/api/logs/stats", methods=["GET"])
@token_required
def get_logs_stats_api():
    """
    获取后台日志统计摘要（今日调用总量、今日搜索量、转存成功率等）
    """
    stats = get_logs_summary()
    return jsonify({"success": True, "data": stats})


@log_bp.route("/admin/api/logs/delete", methods=["POST"])
@token_required
def delete_logs_api():
    """
    批量删除指定 ID 的日志记录
    """
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids or not isinstance(ids, list):
        return jsonify({"success": False, "message": "请勾选待删除的日志记录"}), 400

    success, message, deleted_count = delete_logs(ids)
    if not success:
        return jsonify({"success": False, "message": message}), 500
    return jsonify({"success": True, "message": message, "deleted_count": deleted_count})


@log_bp.route("/admin/api/logs/clear", methods=["POST"])
@token_required
def clear_all_logs_api():
    """
    清空全部系统日志
    """
    success, message, deleted_count = clear_all_logs()
    if not success:
        return jsonify({"success": False, "message": message}), 500
    return jsonify({"success": True, "message": message, "deleted_count": deleted_count})


@log_bp.route("/admin/api/logs/cleanup", methods=["POST"])
@token_required
def cleanup_old_logs_api():
    """
    清理指定天数之前的旧日志 (默认 7 天)
    """
    data = request.get_json(silent=True) or {}
    days = data.get("days", 7)
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 7

    success, message, deleted_count = cleanup_old_logs(days=days)
    if not success:
        return jsonify({"success": False, "message": message}), 500
    return jsonify({"success": True, "message": message, "deleted_count": deleted_count})


@log_bp.route("/admin/api/logs/export", methods=["GET", "POST"])
@token_required
def export_logs_api():
    """
    导出系统日志为 CSV 文件
    """
    ids = None
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        ids = data.get("ids")
        q = data.get("q", "")
        log_type = data.get("log_type", "")
        status = data.get("status", "")
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
    else:
        q = request.args.get("q", "")
        log_type = request.args.get("log_type", "")
        status = request.args.get("status", "")
        start_date = request.args.get("start_date", "")
        end_date = request.args.get("end_date", "")
        ids_str = request.args.get("ids", "")
        if ids_str:
            ids = [int(i.strip()) for i in ids_str.split(",") if i.strip().isdigit()]

    csv_content = export_logs_csv(
        ids=ids,
        q=q,
        log_type=log_type,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )

    response = Response(csv_content, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=pan_relay_logs.csv"
    return response
