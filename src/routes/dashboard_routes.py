import logging
from flask import Blueprint, jsonify, render_template

from src.services.dashboard_service import get_dashboard_summary
from src.utils.auth_utils import token_required

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/admin/dashboard", methods=["GET"])
@token_required
def dashboard_page():
    """
    渲染后台工作台仪表盘主页面
    """
    summary = get_dashboard_summary()
    logger.info("已成功加载后台工作台仪表盘页面")
    return render_template("dashboard.html", summary=summary, active_page="dashboard")


@dashboard_bp.route("/admin/api/dashboard/stats", methods=["GET"])
@token_required
def get_dashboard_stats_api():
    """
    提供给前端 AJAX 异步刷新的仪表盘数据 API
    """
    summary = get_dashboard_summary()
    return jsonify({"success": True, "data": summary})
