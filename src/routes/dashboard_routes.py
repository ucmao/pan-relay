import logging
from flask import Blueprint, jsonify, render_template, request

from src.services.dashboard_service import get_dashboard_summary
from src.utils.auth_utils import token_required

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/admin/dashboard", methods=["GET"])
@token_required
def dashboard_page():
    """
    渲染后台工作台仪表盘主页面（支持动态周期 days: 7, 30, 90, 180, 0）
    """
    raw_days = request.args.get("days", default=7, type=int)
    current_days = raw_days if raw_days in (7, 30, 90, 180, 0) else 7

    summary = get_dashboard_summary(days=current_days)
    logger.info(f"已成功加载后台工作台仪表盘页面 (周期: {current_days} 天)")
    return render_template(
        "dashboard.html",
        summary=summary,
        current_days=current_days,
        chart_data=summary.get("chart_data", {}),
        pie_data=summary.get("pie_data", {}),
        top_zero_keywords=summary.get("top_zero_keywords", []),
        top_hot_keywords=summary.get("top_hot_keywords", []),
        active_page="dashboard",
    )


@dashboard_bp.route("/admin/api/dashboard/stats", methods=["GET"])
@token_required
def get_dashboard_stats_api():
    """
    提供给前端 AJAX 异步刷新的仪表盘数据 API
    """
    raw_days = request.args.get("days", default=7, type=int)
    current_days = raw_days if raw_days in (7, 30, 90, 180, 0) else 7
    summary = get_dashboard_summary(days=current_days)
    return jsonify({"success": True, "data": summary})


@dashboard_bp.route("/admin/docs", methods=["GET"])
@token_required
def admin_docs_page():
    """
    重定向至开放 API 配置内置的开发者指南 Tab
    """
    from flask import redirect, url_for
    return redirect(url_for("system_config.api_config_page", tab="docs"))

