from flask import Blueprint, jsonify, render_template, request

from src.db.cookie_config_dao import get_cookie_by_cloud_name, save_cookie
from src.services.system_config_service import (
    get_public_search_api_config,
    get_frontend_display_netdisk_config,
    get_frontend_link_mode,
    save_public_search_api_config,
    save_frontend_display_netdisk_config,
    save_frontend_link_mode,
)
from utils.auth_utils import token_required
from utils.netdisk_utils import FRONTEND_DISPLAY_NETDISK_OPTIONS

system_config_bp = Blueprint("system_config", __name__)


@system_config_bp.route("/system-config", methods=["GET"])
@token_required
def system_config_page():
    return render_template(
        "system_config.html",
        frontend_netdisk_options=FRONTEND_DISPLAY_NETDISK_OPTIONS,
    )


@system_config_bp.route("/api/frontend-display-netdisks", methods=["GET"])
@token_required
def get_frontend_display_netdisks():
    config = get_frontend_display_netdisk_config()
    return jsonify(
        {
            "success": True,
            "options": FRONTEND_DISPLAY_NETDISK_OPTIONS,
            "enabled_netdisks": config["enabled_netdisks"],
        }
    )


@system_config_bp.route("/api/frontend-display-netdisks", methods=["PUT"])
@token_required
def update_frontend_display_netdisks():
    data = request.get_json() or {}
    enabled_netdisks = data.get("enabled_netdisks", [])

    if not save_frontend_display_netdisk_config(enabled_netdisks):
        return jsonify({"success": False, "message": "前端显示网盘配置保存失败，请至少选择一个网盘"}), 400

    return jsonify({"success": True, "message": "前端显示网盘配置保存成功"})


@system_config_bp.route("/api/frontend-link-mode", methods=["GET"])
@token_required
def get_frontend_link_mode_config():
    return jsonify({"success": True, "mode": get_frontend_link_mode()})


@system_config_bp.route("/api/frontend-link-mode", methods=["PUT"])
@token_required
def update_frontend_link_mode_config():
    data = request.get_json() or {}
    mode = data.get("mode", "")

    if not save_frontend_link_mode(mode):
        return jsonify({"success": False, "message": "前端出链模式保存失败"}), 400

    return jsonify({"success": True, "message": "前端出链模式保存成功"})


@system_config_bp.route("/api/public-search-api-config", methods=["GET"])
@token_required
def get_public_search_api():
    config = get_public_search_api_config()
    return jsonify({"success": True, "enabled": config["enabled"]})


@system_config_bp.route("/api/public-search-api-config", methods=["PUT"])
@token_required
def update_public_search_api():
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", True))

    if not save_public_search_api_config(enabled):
        return jsonify({"success": False, "message": "公开聚合接口配置保存失败"}), 400

    return jsonify(
        {
            "success": True,
            "message": "公开聚合接口已开启" if enabled else "公开聚合接口已关闭",
        }
    )


@system_config_bp.route("/cookie-config", methods=["GET"])
@token_required
def get_cookie_config():
    baidu_cookie = get_cookie_by_cloud_name("百度网盘")
    quark_cookie = get_cookie_by_cloud_name("夸克网盘")
    return jsonify({"baidu_cookie": baidu_cookie, "quark_cookie": quark_cookie})


@system_config_bp.route("/cookie-config", methods=["POST"])
@token_required
def save_cookie_config():
    data = request.get_json() or {}
    baidu_cookie = data.get("baidu_cookie", "")
    quark_cookie = data.get("quark_cookie", "")

    if baidu_cookie:
        success, message = save_cookie("百度网盘", baidu_cookie)
        if not success:
            return jsonify({"success": False, "message": message}), 500

    if quark_cookie:
        success, message = save_cookie("夸克网盘", quark_cookie)
        if not success:
            return jsonify({"success": False, "message": message}), 500

    return jsonify({"success": True, "message": "Cookie配置保存成功"})
