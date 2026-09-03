# src/routes/search_routes.py

from flask import Blueprint, request, jsonify, Response

import json
import logging

from src.pan_operator import create_share, del_share
from src.services.search_service import (
    generate_search_stream_events,
    search_public_resources,
)
from src.services.system_config_service import is_public_search_api_enabled
from src.services.temp_share_service import cleanup_expired_temp_shares, resolve_view_url
from src.utils.auth_utils import token_required

logger = logging.getLogger(__name__)

search_bp = Blueprint("search", __name__)


@search_bp.route("/api/search_stream", methods=["GET"])
def search_stream():
    """
    使用 Server-Sent Events (SSE) 实时流式返回搜索结果。
    """
    keyword = request.args.get("keyword")
    if not keyword:
        return jsonify({"error": "请提供搜索关键词"}), 400

    logger.info(f"用户 SSE 搜索关键词: {keyword}")

    def generate_events():
        for payload in generate_search_stream_events(keyword):
            yield f"data: {payload}\n\n"

    return Response(generate_events(), mimetype="text/event-stream")


@search_bp.route("/api", methods=["GET"])
def search_api():
    """
    对外公开的聚合搜索接口
    """
    if not is_public_search_api_enabled():
        return jsonify({"success": False, "message": "公开聚合接口当前已关闭"}), 403

    keyword = request.args.get("keyword", "", type=str)
    limit = request.args.get("limit", 100, type=int)

    success, message, results = search_public_resources(keyword=keyword, limit=limit)

    if not success:
        status_code = 400 if "请提供搜索关键词" in message else 500
        return jsonify({"success": False, "message": message}), status_code

    return jsonify({"success": True, "total": len(results), "results": results})


@search_bp.route("/create_share", methods=["POST"])
def create_share_route():
    try:
        share_data = request.get_json()
        if not share_data:
            return jsonify({"error": "缺少参数"}), 400
        result = create_share(share_data)
        if result:
            logger.info(f"分享创建成功: {share_data.get('title')}")
            return jsonify({"message": "分享创建成功", "success": True}), 200
        else:
            logger.warning(f"分享创建失败: {share_data.get('title')}")
            return jsonify({"error": "分享创建失败", "success": False}), 500
    except Exception as e:
        logger.error(f"创建分享时发生未知错误: {str(e)}", exc_info=True)
        return jsonify({"error": f"发生未知错误: {str(e)}"}), 500


@search_bp.route("/del_share", methods=["POST"])
def del_share_route():
    try:
        share_data = request.get_json()
        if not share_data:
            return jsonify({"error": "缺少参数"}), 400
        result = del_share(share_data)
        if result:
            logger.info(f"分享删除成功: URL={share_data.get('share_url')}")
            return jsonify({"message": "分享删除成功", "success": True}), 200
        else:
            logger.warning(f"分享删除失败: URL={share_data.get('share_url')}")
            return jsonify({"error": "分享删除失败", "success": False}), 500
    except Exception as e:
        logger.error(f"删除分享时发生未知错误: {str(e)}", exc_info=True)
        return jsonify({"error": f"发生未知错误: {str(e)}"}), 500


@search_bp.route("/api/view-link", methods=["POST"])
def resolve_view_link():
    data = request.get_json() or {}
    original_url = data.get("url", "")
    title = data.get("title", "未命名资源")
    netdisk_name = data.get("netdisk_name", "")

    if not original_url:
        return jsonify({"success": False, "message": "缺少链接参数"}), 400

    resolved = resolve_view_url(title=title, original_url=original_url, netdisk_name=netdisk_name)
    return jsonify({"success": True, **resolved})


@search_bp.route("/api/temp-shares/cleanup", methods=["POST"])
@token_required
def cleanup_temp_shares():
    cleaned_count = cleanup_expired_temp_shares()
    return jsonify({"success": True, "cleaned_count": cleaned_count})
