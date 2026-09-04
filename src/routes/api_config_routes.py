# src/routes/api_config_routes.py

from flask import Blueprint, jsonify, request

import logging

from src.utils.auth_utils import token_required
from src.services.api_config_service import (
    read_api_configs_from_db,
    add_api_config_to_db,
    copy_api_config_in_db,
    update_api_config_in_db,
    delete_api_config_in_db,
    set_api_enabled_in_db,
    enable_all_apis_in_db,
    disable_all_apis_in_db,
    test_single_api,
    test_all_apis_and_update_status,
)

logger = logging.getLogger(__name__)

api_config_bp = Blueprint("api_config", __name__)


@api_config_bp.route("/admin/api/configs", methods=["GET"])
@token_required
def get_api_configs():
    """获取所有 API 配置 (需要 JWT 验证)"""
    configs = read_api_configs_from_db()
    return jsonify(configs)


@api_config_bp.route("/admin/api/configs", methods=["POST"])
@token_required
def add_api_config():
    """新增一条 API 配置 (需要 JWT 验证)"""
    new_config = request.get_json()
    success, message, new_id = add_api_config_to_db(new_config)
    if not success:
        return jsonify({"message": message}), 500
    return jsonify({"message": message, "id": new_id}), 201


@api_config_bp.route("/admin/api/configs/copy/<int:api_id>", methods=["POST"])
@token_required
def copy_api_config(api_id):
    """复制一条 API 配置 (需要 JWT 验证)"""
    success, message, new_id = copy_api_config_in_db(api_id)
    if not success:
        status_code = 404 if "未找到" in message else 500
        return jsonify({"message": message}), status_code
    return jsonify({"message": message, "id": new_id})


@api_config_bp.route("/admin/api/configs/<int:api_id>", methods=["PUT"])
@token_required
def update_api_config(api_id):
    """更新一条 API 配置 (需要 JWT 验证)"""
    updated_config = request.get_json()
    success, message = update_api_config_in_db(api_id, updated_config)
    if not success:
        # 根据 message 内容返回合适的状态码
        if "未找到" in message:
            return jsonify({"message": message}), 404
        if "状态异常" in message:
            return jsonify({"message": message}), 400
        if "数据库连接失败" in message:
            return jsonify({"message": message}), 500
        return jsonify({"message": message}), 500
    return jsonify({"message": message})


@api_config_bp.route("/admin/api/configs/<int:api_id>", methods=["DELETE"])
@token_required
def delete_api_config(api_id):
    """删除一条 API 配置 (需要 JWT 验证)"""
    success, message = delete_api_config_in_db(api_id)
    if not success:
        status_code = 404 if "未找到" in message else 500
        return jsonify({"message": message}), status_code
    return jsonify({"message": message})


@api_config_bp.route("/admin/api/configs/<int:api_id>/enabled", methods=["PUT"])
@token_required
def toggle_api_enabled(api_id):
    """切换单个 API 的启用状态 (需要 JWT 验证)"""
    data = request.get_json()
    is_enabled = bool(data.get("is_enabled"))
    success, message = set_api_enabled_in_db(api_id, is_enabled)
    if not success:
        if "未找到" in message:
            return jsonify({"message": message}), 404
        if "数据库连接失败" in message:
            return jsonify({"message": message}), 500
        return jsonify({"message": message}), 500
    return jsonify({"message": message})


@api_config_bp.route("/admin/api/configs/enable-all", methods=["PUT"])
@token_required
def enable_all_apis():
    """一键启用所有 API 配置 (需要 JWT 验证)"""
    success, message, _count = enable_all_apis_in_db()
    if not success:
        return jsonify({"message": message}), 500
    return jsonify({"message": message})


@api_config_bp.route("/admin/api/configs/disable-all", methods=["PUT"])
@token_required
def disable_all_apis():
    """一键禁用所有 API (需要 JWT 验证)"""
    success, message, _count = disable_all_apis_in_db()
    if not success:
        return jsonify({"message": message}), 500
    return jsonify({"message": message})


@api_config_bp.route("/admin/api/test", methods=["POST"])
@token_required
def test_api():
    """测试单个 API (需要 JWT 验证)"""
    api_config = request.get_json()
    api_id = api_config.get("id", "未知ID") if isinstance(api_config, dict) else "未知ID"
    logger.info(f"开始测试单个 API，配置: {api_config}")
    test_result = test_single_api(api_id, api_config, return_details=True)
    url, new_status, status_code, response_rule_status, response_time_ms = test_result[:5]
    if len(test_result) >= 8:
        test_outcome, result_count, matched_keyword = test_result[5:8]
    else:
        test_outcome = "success" if new_status else "error"
        result_count = 0
        matched_keyword = None

    if status_code is None:
        return (
            jsonify(
                {
                    "error": f"API {url} 测试出错，请查看日志",
                    "status": new_status,
                    "response_time_ms": response_time_ms,
                }
            ),
            500,
        )

    if test_outcome == "no_data":
        response_rule = "接口正常，轮询关键词均无结果"
    elif not (200 <= status_code < 300):
        response_rule = "请求失败"
    else:
        response_rule = "匹配成功" if response_rule_status else "匹配失败，请检查匹配规则"
    return jsonify(
        {
            "status_code": status_code,
            "response_rule": response_rule,
            "status_text": "无结果" if test_outcome == "no_data" else ("正常" if new_status else "异常"),
            "status": new_status,
            "test_outcome": test_outcome,
            "result_count": result_count,
            "matched_keyword": matched_keyword,
            "response_time_ms": response_time_ms,
        }
    )


@api_config_bp.route("/admin/api/test-all", methods=["GET", "POST"])
@token_required
def test_all_apis():
    """测试所有API配置并更新其状态 (需要 JWT 验证)"""
    res = test_all_apis_and_update_status()
    if len(res) == 3:
        success, message, summary = res
    else:
        success, message = res[:2]
        summary = {}

    status_code = 200 if success else 500
    return jsonify({
        "success": success,
        "message": message,
        "total": summary.get("total", 0),
        "healthy_count": summary.get("healthy_count", 0),
        "failed_count": summary.get("failed_count", 0),
        "results": summary.get("results", []),
    }), status_code

