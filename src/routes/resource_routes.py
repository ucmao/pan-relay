from flask import Blueprint, jsonify, render_template, request
import logging

from src.utils.auth_utils import token_required
from src.services.resource_service import (
    list_resources,
    get_resource_detail,
    add_resource_and_share,
    update_resource_info,
    delete_resource_and_share,
)

logger = logging.getLogger(__name__)

resources_bp = Blueprint("resources", __name__)


@resources_bp.route("/admin/resources")
@token_required
def resources_page():
    """资源管理页面，需要JWT验证"""
    return render_template("resource.html")


@resources_bp.route("/admin/api/resources", methods=["GET"])
@token_required
def get_resources():
    """获取资源列表，支持分页、搜索与排序功能"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    search = request.args.get("search", "", type=str)
    sort_by = request.args.get("sort_by", "id", type=str)
    order = request.args.get("order", "desc", type=str)

    success, message, data = list_resources(
        page=page, page_size=page_size, search=search, sort_by=sort_by, order=order
    )
    if not success:
        return jsonify({"success": False, "message": message}), 500
    return jsonify({"success": True, "data": data})


@resources_bp.route("/admin/api/resources/<int:resource_id>", methods=["GET"])
@token_required
def get_resource(resource_id):
    """获取单个资源详情"""
    success, message, resource = get_resource_detail(resource_id)
    if not success:
        status = 404 if message == "资源不存在" else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "data": resource})


@resources_bp.route("/admin/api/resources", methods=["POST"])
@token_required
def add_resource():
    """添加新资源"""
    resource_data = request.get_json()
    success, message, new_id = add_resource_and_share(resource_data)
    if not success:
        status = 400 if "必填项" in message else 500 if "数据库" in message else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "message": message, "id": new_id}), 201


@resources_bp.route("/admin/api/resources/<int:resource_id>", methods=["PUT"])
@token_required
def update_resource(resource_id):
    """更新资源信息"""
    resource_data = request.get_json()
    success, message = update_resource_info(resource_id, resource_data)
    if not success:
        status = 400 if "必填项" in message else 404 if message == "资源不存在" else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "message": message})


@resources_bp.route("/admin/api/resources/<int:resource_id>", methods=["DELETE"])
@token_required
def delete_resource(resource_id):
    """删除资源"""
    raw_flag = request.args.get("delete_netdisk_file", None)
    if raw_flag is None:
        payload = request.get_json(silent=True) or {}
        delete_netdisk_file = bool(payload.get("delete_netdisk_file", False))
    else:
        delete_netdisk_file = str(raw_flag).lower() in ("true", "1", "yes")

    success, message = delete_resource_and_share(resource_id, delete_netdisk_file=delete_netdisk_file)
    if not success:
        status = 404 if message == "资源不存在" else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "message": message})


@resources_bp.route("/admin/api/resources/audit", methods=["POST"])
@token_required
def audit_resources_route():
    """批量巡检入库资源有效性与健康状态"""
    from src.services.resource_health_service import audit_resources_batch

    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids")
    limit = max(1, min(int(payload.get("limit", 100)), 500))
    max_workers = max(1, min(int(payload.get("max_workers", 4)), 10))

    if ids and not isinstance(ids, list):
        return jsonify({"success": False, "message": "ids 必须为资源ID列表"}), 400

    result = audit_resources_batch(resource_ids=ids, limit=limit, max_workers=max_workers)
    return jsonify({"success": True, "message": "巡检完成", "data": result})


@resources_bp.route("/admin/api/resources/<int:resource_id>/check", methods=["POST"])
@token_required
def check_single_resource_route(resource_id):
    """单条资源实时健康测活与更新"""
    from src.services.resource_health_service import audit_single_resource

    success, message, result = audit_single_resource(resource_id)
    if not success:
        status = 404 if message == "资源不存在" else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "message": message, "data": result})


@resources_bp.route("/admin/api/resources/cleanup-dead", methods=["POST"])
@token_required
def cleanup_dead_resources_route():
    """一键清理标记为失效 (bad) 的死链资源"""
    from src.services.resource_health_service import cleanup_dead_resources

    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get("dry_run", False))
    limit = max(1, min(int(payload.get("limit", 100)), 500))

    result = cleanup_dead_resources(dry_run=dry_run, limit=limit)
    msg = f"成功检测到 {result['total_found']} 条失效资源，已清理 {result['cleaned_count']} 条"
    return jsonify({"success": True, "message": msg, "data": result})


@resources_bp.route("/admin/api/resources/health-stats", methods=["GET"])
@token_required
def get_resource_health_stats_route():
    """获取资源库各健康状态数据统计"""
    from src.services.resource_health_service import get_resource_health_overview

    stats = get_resource_health_overview()
    return jsonify({"success": True, "data": stats})

