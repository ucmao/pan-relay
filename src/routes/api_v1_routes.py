# src/routes/api_v1_routes.py

from flask import Blueprint, jsonify, request, Response, render_template
import json
import logging
import time

from src.services.log_service import record_log
from src.services.search_service import (
    generate_search_stream_events,
    search_public_resources,
    search_in_database,
    filter_results_by_frontend_netdisks,
)
from src.services.link_checker import (
    check_link,
    check_links_batch,
    STATE_BAD,
    STATE_LOCKED,
)
from src.services.temp_share_service import resolve_view_url
from src.services.resource_service import list_resources
from src.services.system_config_service import (
    get_api_mode_config,
    get_search_api_scope,
    get_transfer_api_key,
    is_public_search_api_enabled,
)
from src.utils.netdisk_utils import FRONTEND_DISPLAY_NETDISK_OPTIONS

logger = logging.getLogger(__name__)

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@api_v1_bp.route("/status", methods=["GET"])
def api_status():
    """
    获取服务运行状态、API 模式配置及所有可用 API 节点列表。
    """
    mode_config = get_api_mode_config()
    return jsonify({
        "success": True,
        "service": "pan-relay",
        "version": "1.0.0",
        "status": "healthy",
        "api_mode": mode_config,
        "endpoints": {
            "status": "/api/v1/status",
            "search": "/api/v1/search",
            "search_stream": "/api/v1/search/stream",
            "transfer": "/api/v1/transfer",
            "link_check": "/api/v1/link/check",
            "resources": "/api/v1/resources",
            "docs": "/api/v1/docs",
        },
    })


def _enrich_and_filter_results(results: list, check_status: bool, filter_bad: bool) -> list:
    """对搜索结果进行并发测活注入 (health_state/summary/file_count) 与失效链接过滤"""
    if not results or (not check_status and not filter_bad):
        return results

    check_items = []
    for r in results:
        u = r.get("share_link") or r.get("url") or ""
        p = r.get("password") or r.get("pwd") or ""
        d = r.get("cloud_name") or r.get("netdisk_name") or ""
        check_items.append({"url": u, "password": p, "disk_type": d})

    check_res_list = check_links_batch(check_items)
    for item, chk in zip(results, check_res_list):
        item["health_state"] = chk.get("state")
        item["health_summary"] = chk.get("summary")
        if chk.get("file_count") is not None:
            item["file_count"] = chk.get("file_count")

    if filter_bad:
        results = [item for item in results if item.get("health_state") != STATE_BAD]

    return results


@api_v1_bp.route("/search", methods=["GET"])
def api_search():
    """
    步骤 1: 聚合资源查询接口
    - scope=own: 仅查询站长私有收益库资源 (响应极快、0开销、专属收益)
    - scope=all: 全网并发聚合查询 (私有库 + 爬虫 + TG)
    """
    start_time = time.time()
    if not is_public_search_api_enabled():
        record_log(
            log_type="search",
            action="search.api.v1",
            query_text=request.args.get("keyword", ""),
            status_code=403,
            error_message="公开聚合查询接口已被关闭",
        )
        return jsonify({"success": False, "message": "公开聚合查询接口已被关闭"}), 403

    keyword = request.args.get("keyword", "", type=str).strip()
    limit = request.args.get("limit", 100, type=int)
    cloud_name = request.args.get("cloud_name", "", type=str).strip()
    req_scope = request.args.get("scope", "", type=str).strip().lower()
    check_status = request.args.get("check_status", "false").lower() in ("true", "1")
    filter_bad = request.args.get("filter_bad", "false").lower() in ("true", "1")

    if not keyword:
        record_log(
            log_type="search",
            action="search.api.v1",
            query_text="",
            status_code=400,
            error_message="缺少必填参数: keyword",
        )
        return jsonify({"success": False, "message": "缺少必填参数: keyword"}), 400

    if cloud_name and cloud_name not in FRONTEND_DISPLAY_NETDISK_OPTIONS:
        record_log(
            log_type="search",
            action="search.api.v1",
            query_text=f"{keyword} [cloud={cloud_name}]",
            status_code=400,
            error_message=f"不支持的网盘类型: {cloud_name}",
        )
        return jsonify({
            "success": False,
            "message": f"不支持的网盘类型: {cloud_name}",
            "supported_cloud_names": list(FRONTEND_DISPLAY_NETDISK_OPTIONS),
        }), 400

    # 判断查询作用域
    scope = req_scope if req_scope in ("own", "all", "local") else get_search_api_scope()
    if scope == "local":
        scope = "own"

    if scope == "own":
        raw_items = search_in_database(keyword)
        filtered_items = filter_results_by_frontend_netdisks(raw_items)
        if cloud_name:
            filtered_items = [
                item for item in filtered_items
                if (getattr(item, "cloud_name", "") or item.get("cloud_name", "")) == cloud_name
            ]
        results = [
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in filtered_items[:limit]
        ]
        results = _enrich_and_filter_results(results, check_status=check_status, filter_bad=filter_bad)
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="search",
            action="search.api.v1.own",
            query_text=f"{keyword} [cloud={cloud_name or 'all'}]",
            status_code=200,
            duration_ms=duration_ms,
            result_count=len(results),
        )
        return jsonify({
            "success": True,
            "scope": "own",
            "total": len(results),
            "results": results,
        })

    success, message, results = search_public_resources(
        keyword=keyword,
        limit=limit,
        cloud_name=cloud_name,
    )

    if not success:
        return jsonify({"success": False, "message": message}), 500

    results = _enrich_and_filter_results(results, check_status=check_status, filter_bad=filter_bad)
    return jsonify({
        "success": True,
        "scope": "all",
        "total": len(results),
        "results": results,
    })


@api_v1_bp.route("/search/stream", methods=["GET"])
def api_search_stream():
    """
    步骤 1 (流式): SSE 实时流式返回搜索结果
    """
    keyword = request.args.get("keyword", "", type=str).strip()
    if not keyword:
        return jsonify({"success": False, "message": "缺少必填参数: keyword"}), 400

    def generate_events():
        for payload in generate_search_stream_events(keyword):
            yield f"data: {payload}\n\n"

    return Response(generate_events(), mimetype="text/event-stream")


@api_v1_bp.route("/transfer", methods=["POST"])
def api_transfer():
    """
    步骤 2: 替换/转存为系统专属资源接口。
    支持通过 Header 'X-API-Key' 或 'Authorization: Bearer <key>' 校验转存权限。
    """
    start_time = time.time()
    data = request.get_json(silent=True) or {}
    url = data.get("url") or data.get("share_url") or ""
    title = data.get("title", "未命名资源")
    netdisk_name = data.get("netdisk_name") or data.get("cloud_name") or ""

    # API Key 校验
    expected_api_key = get_transfer_api_key()
    if expected_api_key:
        req_key = (
            request.headers.get("X-API-Key")
            or request.headers.get("X-Api-Key")
            or request.args.get("api_key")
            or data.get("api_key")
        )
        if not req_key and request.headers.get("Authorization"):
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                req_key = auth[7:].strip()
            else:
                req_key = auth.strip()

        if not req_key or req_key != expected_api_key:
            record_log(
                log_type="api",
                action="api.v1.transfer",
                query_text=url,
                status_code=401,
                error_message="API Key 校验失败",
            )
            return jsonify({
                "success": False,
                "message": "API Key 校验失败，缺乏转存调用的有效授权",
            }), 401

    if not url:
        record_log(
            log_type="api",
            action="api.v1.transfer",
            query_text="",
            status_code=400,
            error_message="缺少必填参数: url",
        )
        return jsonify({"success": False, "message": "缺少必填参数: url"}), 400

    # 前置免登录测活检查 (提前阻断失效、下架、空文件或密码缺失的链接)
    skip_check = bool(data.get("skip_check", False))
    password = data.get("password") or data.get("pwd")
    if not skip_check:
        chk = check_link(url, password=password, disk_type=netdisk_name)
        if chk.get("state") == STATE_BAD:
            duration_ms = int((time.time() - start_time) * 1000)
            record_log(
                log_type="api",
                action=f"api.v1.transfer.{netdisk_name or 'auto'}.invalid",
                query_text=f"{url} [reason={chk.get('summary')}]",
                status_code=422,
                error_message=f"源链接已失效或为空: {chk.get('summary')}",
                duration_ms=duration_ms,
            )
            return jsonify({
                "success": False,
                "code": "LINK_INVALID",
                "message": f"源链接已失效、被下架或内容为空: {chk.get('summary')}",
                "data": chk,
            }), 422

        if chk.get("state") == STATE_LOCKED and not password:
            duration_ms = int((time.time() - start_time) * 1000)
            record_log(
                log_type="api",
                action=f"api.v1.transfer.{netdisk_name or 'auto'}.locked",
                query_text=url,
                status_code=422,
                error_message="源链接需要提取码",
                duration_ms=duration_ms,
            )
            return jsonify({
                "success": False,
                "code": "LINK_LOCKED",
                "message": "源链接需要提取码，请在请求体中提供 password 参数",
                "data": chk,
            }), 422

    try:
        resolved = resolve_view_url(title=title, original_url=url, netdisk_name=netdisk_name)
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="api",
            action=f"api.v1.transfer.{netdisk_name or 'auto'}",
            query_text=f"{url} [title={title}]",
            status_code=200 if resolved.get("mode") != "error" else 500,
            error_message=resolved.get("message") if resolved.get("mode") == "error" else None,
            duration_ms=duration_ms,
            result_count=1,
        )
        return jsonify({
            "success": True,
            "message": "资源转换与链接生成成功",
            "data": resolved,
        })
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="api",
            action=f"api.v1.transfer.{netdisk_name or 'auto'}",
            query_text=url,
            status_code=500,
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        logger.error(f"API v1 转存异常: {exc}", exc_info=True)
        return jsonify({"success": False, "message": f"转存处理失败: {str(exc)}"}), 500


@api_v1_bp.route("/link/check", methods=["POST"])
def api_link_check():
    """
    网盘链接有效性检测接口 (支持单条及批量检测)
    """
    start_time = time.time()
    data = request.get_json(silent=True) or {}

    # 1. 批量检测模式
    items = data.get("items")
    if items and isinstance(items, list):
        results = check_links_batch(items)
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="api",
            action="api.v1.link_check.batch",
            query_text=f"批量检测 {len(items)} 条链接",
            status_code=200,
            duration_ms=duration_ms,
            result_count=len(results),
        )
        return jsonify({"success": True, "mode": "batch", "total": len(results), "results": results})

    # 2. 单条检测模式
    url = data.get("url") or request.args.get("url", "").strip()
    if not url:
        record_log(
            log_type="api",
            action="api.v1.link_check.single",
            query_text="",
            status_code=400,
            error_message="缺少待检测链接",
        )
        return jsonify({"success": False, "message": "请提供待检测的网盘链接 (url 或 items 列表)"}), 400

    password = data.get("password") or data.get("pwd")
    disk_type = data.get("disk_type") or data.get("cloud_name")
    force_refresh = bool(data.get("refresh", False))

    res = check_link(url, password=password, disk_type=disk_type, force_refresh=force_refresh)
    return jsonify({"success": True, "mode": "single", "data": res})


@api_v1_bp.route("/resources", methods=["GET"])
def api_list_resources():
    """
    查看库内已保存的转存资源列表接口
    """
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    search = request.args.get("search", "", type=str)

    success, message, data = list_resources(page=page, page_size=page_size, search=search)
    if not success:
        return jsonify({"success": False, "message": message}), 500
    return jsonify({"success": True, "data": data})


@api_v1_bp.route("/docs", methods=["GET"])
def api_docs():
    """
    开发者 API 接入指南说明接口 (支持网页 HTML 渲染与 JSON 规范返回)
    """
    docs_payload = {
        "title": "pan-relay 开发者 REST API 指南",
        "description": "提供两步走 (1. 查询资源 -> 2. 转存替换) 及网盘连接检测服务",
        "workflow": [
            "步骤 1: 调用 GET /api/v1/search?keyword=...&scope=own 搜索站长收益资源。",
            "步骤 2: 当用户选中资源时，调用 POST /api/v1/transfer 将链接转换为本系统转存链接 (支持 Header X-API-Key)。",
            "步骤 3: 前端/小程序直接向用户展示步骤 2 生成的转存链接。",
        ],
        "endpoints": [
            {
                "path": "/api/v1/status",
                "method": "GET",
                "summary": "获取服务运行状态与 API 模式配置",
            },
            {
                "path": "/api/v1/search",
                "method": "GET",
                "summary": "步骤 1: 搜索资源",
                "parameters": {
                    "keyword": "关键词 (必填)",
                    "scope": "搜索范围 (own: 仅站长收益库; all: 全网聚合，默认按后台配置)",
                    "cloud_name": "指定网盘 (可选)",
                    "limit": "条数限制 (默认 100)",
                },
            },
            {
                "path": "/api/v1/search/stream",
                "method": "GET",
                "summary": "步骤 1 (SSE): 实时流式搜索",
                "parameters": {"keyword": "关键词 (必填)"},
            },
            {
                "path": "/api/v1/transfer",
                "method": "POST",
                "summary": "步骤 2: 将资源转存并替换为专属网盘链接",
                "headers": {"X-API-Key": "后台配置的转存 Key (若后台未配置则无需传递)"},
                "body": {"url": "原始分享链接 (必填)", "title": "资源标题", "netdisk_name": "网盘类型"},
            },
            {
                "path": "/api/v1/link/check",
                "method": "POST",
                "summary": "检测网盘链接测活 (单条/批量)",
                "body": {"url": "待检测链接", "password": "提取码 (可选)", "items": "批量检测列表 (可选)"},
            },
            {
                "path": "/api/v1/resources",
                "method": "GET",
                "summary": "获取已保存转存资源列表",
                "parameters": {"page": "页码", "page_size": "每页条数", "search": "筛选关键词"},
            },
        ],
    }

    accept = request.headers.get("Accept", "")
    wants_json = (
        request.args.get("format") == "json"
        or "application/json" in accept
        or request.is_json
    )

    if wants_json and "text/html" not in accept:
        return jsonify(docs_payload)

    return render_template("api_docs.html")

