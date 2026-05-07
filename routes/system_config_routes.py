from flask import Blueprint, jsonify, render_template, request
import json

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


@system_config_bp.route("/admin/system-config", methods=["GET"])
@token_required
def system_config_page():
    return render_template(
        "system_config.html",
        frontend_netdisk_options=FRONTEND_DISPLAY_NETDISK_OPTIONS,
    )


@system_config_bp.route("/admin/api/frontend-display-netdisks", methods=["GET"])
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


@system_config_bp.route("/admin/api/frontend-display-netdisks", methods=["PUT"])
@token_required
def update_frontend_display_netdisks():
    data = request.get_json() or {}
    enabled_netdisks = data.get("enabled_netdisks", [])

    if not save_frontend_display_netdisk_config(enabled_netdisks):
        return jsonify({"success": False, "message": "前端显示网盘配置保存失败，请至少选择一个网盘"}), 400

    return jsonify({"success": True, "message": "前端显示网盘配置保存成功"})


@system_config_bp.route("/admin/api/frontend-link-mode", methods=["GET"])
@token_required
def get_frontend_link_mode_config():
    return jsonify({"success": True, "mode": get_frontend_link_mode()})


@system_config_bp.route("/admin/api/frontend-link-mode", methods=["PUT"])
@token_required
def update_frontend_link_mode_config():
    data = request.get_json() or {}
    mode = data.get("mode", "")

    if not save_frontend_link_mode(mode):
        return jsonify({"success": False, "message": "前端出链模式保存失败"}), 400

    return jsonify({"success": True, "message": "前端出链模式保存成功"})


@system_config_bp.route("/admin/api/public-search-api-config", methods=["GET"])
@token_required
def get_public_search_api():
    config = get_public_search_api_config()
    return jsonify({"success": True, "enabled": config["enabled"]})


@system_config_bp.route("/admin/api/public-search-api-config", methods=["PUT"])
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


@system_config_bp.route("/admin/api/cookie-config", methods=["GET"])
@system_config_bp.route("/admin/api/credential-config", methods=["GET"])
@token_required
def get_credential_config():
    baidu_cookie = get_cookie_by_cloud_name("百度网盘")
    quark_cookie = get_cookie_by_cloud_name("夸克网盘")
    aliyun_token = get_cookie_by_cloud_name("阿里云盘")
    uc_cookie = get_cookie_by_cloud_name("UC网盘")
    xunlei_raw = get_cookie_by_cloud_name("迅雷网盘") or ""
    try:
        xunlei_config = json.loads(xunlei_raw) if xunlei_raw else {}
    except json.JSONDecodeError:
        xunlei_config = {}
    return jsonify(
        {
            "baidu_cookie": baidu_cookie,
            "quark_cookie": quark_cookie,
            "aliyun_token": aliyun_token,
            "uc_cookie": uc_cookie,
            "xunlei_refresh_token": xunlei_config.get("refresh_token", ""),
            "xunlei_captcha_sign": xunlei_config.get("captcha_sign", ""),
            "xunlei_user_id": xunlei_config.get("user_id", ""),
        }
    )


@system_config_bp.route("/admin/api/cookie-config", methods=["POST"])
@system_config_bp.route("/admin/api/credential-config", methods=["POST"])
@token_required
def save_credential_config():
    data = request.get_json() or {}
    baidu_cookie = data.get("baidu_cookie", "")
    quark_cookie = data.get("quark_cookie", "")
    aliyun_token = data.get("aliyun_token", "")
    uc_cookie = data.get("uc_cookie", "")
    xunlei_refresh_token = data.get("xunlei_refresh_token", "")
    xunlei_captcha_sign = data.get("xunlei_captcha_sign", "")
    xunlei_user_id = data.get("xunlei_user_id", "")

    if baidu_cookie:
        success, message = save_cookie("百度网盘", baidu_cookie)
        if not success:
            return jsonify({"success": False, "message": message}), 500

    if quark_cookie:
        success, message = save_cookie("夸克网盘", quark_cookie)
        if not success:
            return jsonify({"success": False, "message": message}), 500

    if aliyun_token:
        success, message = save_cookie("阿里云盘", aliyun_token)
        if not success:
            return jsonify({"success": False, "message": message}), 500

    if uc_cookie:
        success, message = save_cookie("UC网盘", uc_cookie)
        if not success:
            return jsonify({"success": False, "message": message}), 500

    has_any_xunlei_field = any([xunlei_refresh_token, xunlei_captcha_sign, xunlei_user_id])
    has_all_xunlei_fields = all([xunlei_refresh_token, xunlei_captcha_sign, xunlei_user_id])
    if has_any_xunlei_field and not has_all_xunlei_fields:
        return jsonify({"success": False, "message": "迅雷网盘凭证需要同时填写 refresh_token、captcha_sign 和 user_id"}), 400

    if has_all_xunlei_fields:
        success, message = save_cookie(
            "迅雷网盘",
            json.dumps(
                {
                    "refresh_token": xunlei_refresh_token,
                    "captcha_sign": xunlei_captcha_sign,
                    "user_id": xunlei_user_id,
                },
                ensure_ascii=False,
            ),
        )
        if not success:
            return jsonify({"success": False, "message": message}), 500

    return jsonify({"success": True, "message": "云盘凭证保存成功"})
