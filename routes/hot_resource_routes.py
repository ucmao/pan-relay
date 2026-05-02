from flask import Blueprint, jsonify, render_template, request
import logging

from utils.auth_utils import token_required
from src.services.hot_resource_service import (
    list_resources,
    get_resource_detail,
    add_resource_and_share,
    update_resource_info,
    delete_resource_and_share,
)

logger = logging.getLogger(__name__)

resources_bp = Blueprint("resources", __name__)


@resources_bp.route("/hot-resource")
@token_required
def resources_page():
    """资源管理页面，需要JWT验证"""
    return render_template("hot_resource.html")


@resources_bp.route("/api/resources", methods=["GET"])
@token_required
def get_resources():
    """获取资源列表，支持分页和搜索功能"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    search = request.args.get("search", "", type=str)

    success, message, data = list_resources(page=page, page_size=page_size, search=search)
    if not success:
        return jsonify({"success": False, "message": message}), 500
    return jsonify({"success": True, "data": data})


@resources_bp.route("/api/resources/<int:resource_id>", methods=["GET"])
@token_required
def get_resource(resource_id):
    """获取单个资源详情"""
    success, message, resource = get_resource_detail(resource_id)
    if not success:
        status = 404 if message == "资源不存在" else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "data": resource})


@resources_bp.route("/api/resources", methods=["POST"])
@token_required
def add_resource():
    """添加新资源"""
    resource_data = request.get_json()
    success, message, new_id = add_resource_and_share(resource_data)
    if not success:
        status = 400 if "必填项" in message else 500 if "数据库" in message else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "message": message, "id": new_id}), 201


@resources_bp.route("/api/resources/<int:resource_id>", methods=["PUT"])
@token_required
def update_resource(resource_id):
    """更新资源信息"""
    resource_data = request.get_json()
    success, message = update_resource_info(resource_id, resource_data)
    if not success:
        status = 400 if "必填项" in message else 404 if message == "资源不存在" else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "message": message})


@resources_bp.route("/api/resources/<int:resource_id>", methods=["DELETE"])
@token_required
def delete_resource(resource_id):
    """删除资源"""
    success, message = delete_resource_and_share(resource_id)
    if not success:
        status = 404 if message == "资源不存在" else 500
        return jsonify({"success": False, "message": message}), status
    return jsonify({"success": True, "message": message})
