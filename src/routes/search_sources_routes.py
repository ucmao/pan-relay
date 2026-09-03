import logging
from flask import Blueprint, render_template, request

from src.utils.auth_utils import token_required

logger = logging.getLogger(__name__)

search_sources_bp = Blueprint("search_sources", __name__)


@search_sources_bp.route("/admin/sources", methods=["GET"])
@token_required
def sources_page():
    """
    检索源统一治理页面 (包含 API 检索源、插件扩展、Telegram 频道多 Tab 切换)
    """
    tab = request.args.get("tab", "api").strip().lower()
    if tab not in ("api", "plugins", "telegram"):
        tab = "api"
    logger.info(f"已验证管理员访问检索源统一治理工作区 (Tab: {tab})")
    return render_template("search_sources.html", active_tab=tab, active_page="sources")
