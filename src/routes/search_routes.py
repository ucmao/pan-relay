# src/routes/search_routes.py

from flask import Blueprint, request, jsonify, Response

import json
import logging
import time

from src.pan_operator import create_share, del_share
from src.services.log_service import record_log
from src.services.search_service import (
    generate_search_stream_events,
    search_public_resources,
)
from src.services.link_checker import (
    check_link,
    check_links_batch,
    STATE_BAD,
)
from src.services.system_config_service import is_public_search_api_enabled
from src.services.temp_share_service import cleanup_expired_temp_shares, resolve_view_url
from src.utils.auth_utils import token_required
from src.utils.netdisk_utils import FRONTEND_DISPLAY_NETDISK_OPTIONS

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
    cloud_name = request.args.get("cloud_name", "", type=str).strip()
    check_status = request.args.get("check_status", "false").lower() in ("true", "1")
    filter_bad = request.args.get("filter_bad", "false").lower() in ("true", "1")

    if cloud_name and cloud_name not in FRONTEND_DISPLAY_NETDISK_OPTIONS:
        return jsonify({
            "success": False,
            "message": f"不支持的网盘类型: {cloud_name}",
            "supported_cloud_names": FRONTEND_DISPLAY_NETDISK_OPTIONS,
        }), 400

    success, message, results = search_public_resources(
        keyword=keyword,
        limit=limit,
        cloud_name=cloud_name,
    )

    if not success:
        status_code = 400 if "请提供搜索关键词" in message else 500
        return jsonify({"success": False, "message": message}), status_code

    if results and (check_status or filter_bad):
        check_items = [
            {
                "url": r.get("share_link") or r.get("url") or "",
                "password": r.get("password") or r.get("pwd") or "",
                "disk_type": r.get("cloud_name") or r.get("netdisk_name") or "",
            }
            for r in results
        ]
        check_res_list = check_links_batch(check_items)
        for item, chk in zip(results, check_res_list):
            item["health_state"] = chk.get("state")
            item["health_summary"] = chk.get("summary")
            if chk.get("file_count") is not None:
                item["file_count"] = chk.get("file_count")
        if filter_bad:
            results = [item for item in results if item.get("health_state") != STATE_BAD]

    return jsonify({"success": True, "total": len(results), "results": results})


@search_bp.route("/api/check/links", methods=["POST"])
def check_links_api():
    """
    批量检测网盘分享链接有效性接口
    """
    data = request.get_json(silent=True) or {}
    items = data.get("items")
    if not items or not isinstance(items, list):
        return jsonify({"success": False, "message": "缺少有效的 items 列表参数"}), 400

    results = check_links_batch(items)
    return jsonify({"success": True, "total": len(results), "results": results})


@search_bp.route("/api/check/link", methods=["GET"])
def check_single_link_api():
    """
    单条网盘分享链接检测接口
    """
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "message": "请提供待检测的网盘链接 (url)"}), 400

    password = request.args.get("password") or request.args.get("pwd")
    disk_type = request.args.get("disk_type") or request.args.get("cloud_name")
    force_refresh = request.args.get("refresh", "false").lower() in ("true", "1")

    res = check_link(url, password=password, disk_type=disk_type, force_refresh=force_refresh)
    return jsonify({"success": True, "data": res})


@search_bp.route("/create_share", methods=["POST"])
def create_share_route():
    start_time = time.time()
    try:
        share_data = request.get_json()
        if not share_data:
            record_log(
                log_type="transfer",
                action="transfer.create_share",
                query_text="",
                status_code=400,
                error_message="缺少参数",
                duration_ms=0,
            )
            return jsonify({"error": "缺少参数"}), 400
        result = create_share(share_data)
        duration_ms = int((time.time() - start_time) * 1000)
        query_text = share_data.get("share_url") or share_data.get("title")
        if result:
            logger.info(f"分享创建成功: {share_data.get('title')}")
            record_log(
                log_type="transfer",
                action="transfer.create_share",
                query_text=query_text,
                status_code=200,
                duration_ms=duration_ms,
                result_count=1,
            )
            return jsonify({"message": "分享创建成功", "success": True}), 200
        else:
            logger.warning(f"分享创建失败: {share_data.get('title')}")
            record_log(
                log_type="transfer",
                action="transfer.create_share",
                query_text=query_text,
                status_code=500,
                error_message="网盘转存/分享创建失败",
                duration_ms=duration_ms,
            )
            return jsonify({"error": "分享创建失败", "success": False}), 500
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="transfer",
            action="transfer.create_share",
            query_text=str(request.get_json(silent=True) or {}),
            status_code=500,
            error_message=str(e),
            duration_ms=duration_ms,
        )
        logger.error(f"创建分享时发生未知错误: {str(e)}", exc_info=True)
        return jsonify({"error": f"发生未知错误: {str(e)}"}), 500


@search_bp.route("/del_share", methods=["POST"])
def del_share_route():
    start_time = time.time()
    try:
        share_data = request.get_json()
        if not share_data:
            return jsonify({"error": "缺少参数"}), 400
        result = del_share(share_data)
        duration_ms = int((time.time() - start_time) * 1000)
        query_text = share_data.get("share_url") or ""
        if result:
            logger.info(f"分享删除成功: URL={share_data.get('share_url')}")
            record_log(
                log_type="transfer",
                action="transfer.del_share",
                query_text=query_text,
                status_code=200,
                duration_ms=duration_ms,
            )
            return jsonify({"message": "分享删除成功", "success": True}), 200
        else:
            logger.warning(f"分享删除失败: URL={share_data.get('share_url')}")
            record_log(
                log_type="transfer",
                action="transfer.del_share",
                query_text=query_text,
                status_code=500,
                error_message="删除转存分享失败",
                duration_ms=duration_ms,
            )
            return jsonify({"error": "分享删除失败", "success": False}), 500
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="transfer",
            action="transfer.del_share",
            query_text=str(request.get_json(silent=True) or {}),
            status_code=500,
            error_message=str(e),
            duration_ms=duration_ms,
        )
        logger.error(f"删除分享时发生未知错误: {str(e)}", exc_info=True)
        return jsonify({"error": f"发生未知错误: {str(e)}"}), 500


@search_bp.route("/api/view-link", methods=["POST"])
def resolve_view_link():
    start_time = time.time()
    data = request.get_json() or {}
    original_url = data.get("url", "")
    title = data.get("title", "未命名资源")
    netdisk_name = data.get("netdisk_name", "")

    if not original_url:
        record_log(
            log_type="transfer",
            action="transfer.view_link",
            query_text="",
            status_code=400,
            error_message="缺少链接参数",
            duration_ms=0,
        )
        return jsonify({"success": False, "message": "缺少链接参数"}), 400

    resolved = resolve_view_url(title=title, original_url=original_url, netdisk_name=netdisk_name)
    duration_ms = int((time.time() - start_time) * 1000)
    record_log(
        log_type="transfer",
        action="transfer.view_link",
        query_text=f"{original_url} [{netdisk_name or 'auto'}]",
        status_code=200 if resolved.get("mode") != "error" else 500,
        error_message=resolved.get("message") if resolved.get("mode") == "error" else None,
        duration_ms=duration_ms,
    )
    return jsonify({"success": True, **resolved})


@search_bp.route("/api/temp-shares/cleanup", methods=["POST"])
@token_required
def cleanup_temp_shares():
    cleaned_count = cleanup_expired_temp_shares()
    record_log(
        log_type="system",
        action="system.temp_shares_cleanup",
        status_code=200,
        result_count=cleaned_count,
    )
    return jsonify({"success": True, "cleaned_count": cleaned_count})
