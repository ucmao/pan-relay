from flask import Blueprint, Response, jsonify, render_template, request
import concurrent.futures
import datetime
import json
import logging
import threading
import urllib.parse

logger = logging.getLogger(__name__)

from src.services.account_csv_service import (
    export_accounts_csv,
    generate_accounts_template_csv,
    import_accounts_from_csv,
)

from src.db.credentials import delete_cookie, get_cookie_by_cloud_name, save_cookie
from src.db.accounts import (
    create_account,
    update_account,
    delete_account,
    get_account_by_id,
    get_all_accounts,
    get_accounts_by_cloud,
)
from src.services.account_pool_manager import AccountPoolManager
from src.services.system_config_service import (
    get_public_search_api_config,
    get_allow_excel_download_config,
    get_pc_qr_code_config,
    is_pc_qr_code_enabled,
    save_pc_qr_code_config,
    get_frontend_github_config,
    is_frontend_github_enabled,
    save_frontend_github_config,
    get_frontend_link_check_config,

    get_frontend_display_netdisk_config,
    get_dynamic_transfer_netdisk_config,
    get_frontend_link_mode,
    get_transfer_target_dir,
    get_sensitive_words_config,
    get_ad_filter_config,
    get_custom_ad_injection_config,
    get_storage_cleanup_config,
    get_search_scheduler_config,
    get_api_mode_config,
    save_api_mode_config,
    get_security_config,
    save_security_config,
    add_ip_to_blacklist,
    remove_ip_from_blacklist,
    save_public_search_api_config,

    save_allow_excel_download_config,
    save_frontend_link_check_config,
    save_frontend_display_netdisk_config,
    save_dynamic_transfer_netdisk_config,
    save_frontend_link_mode,
    save_transfer_target_dir,
    save_sensitive_words_config,
    save_ad_filter_config,
    save_custom_ad_injection_config,
    save_storage_cleanup_config,
    save_search_scheduler_config,
)
from src.services.telegram_channel_service import (
    add_tg_channel,
    delete_tg_channel,
    get_tg_channel_items,
    normalize_tg_channel,
    save_tg_channel_health,
    set_all_tg_channels_enabled,
    set_tg_channel_enabled,
)
from src.services.telegram_search_service import test_telegram_connection
from src.utils.auth_utils import token_required
from src.utils.netdisk_utils import (
    FRONTEND_DISPLAY_NETDISK_OPTIONS,
    LINK_CHECK_NETDISK_OPTIONS,
    DYNAMIC_TRANSFER_NETDISK_OPTIONS,
)

system_config_bp = Blueprint("system_config", __name__)

DYNAMIC_TRANSFER_STATUS_CONFIGS = [
    {
        "cloud_name": "百度网盘",
        "credential_type": "Cookie",
        "min_length": 50,
    },
    {
        "cloud_name": "夸克网盘",
        "credential_type": "Cookie",
        "min_length": 50,
    },
    {
        "cloud_name": "阿里云盘",
        "credential_type": "Refresh Token",
        "min_length": 20,
    },
    {
        "cloud_name": "UC网盘",
        "credential_type": "Cookie",
        "min_length": 50,
    },
    {
        "cloud_name": "迅雷网盘",
        "credential_type": "Refresh Token",
        "min_length": 20,
    },
    {
        "cloud_name": "光鸭云盘",
        "credential_type": "Access Token / Refresh Token",
        "min_length": 10,
    },
    {
        "cloud_name": "悟空网盘",
        "credential_type": "Cookie / Session Token",
        "min_length": 10,
    },
    {
        "cloud_name": "移动云盘",
        "credential_type": "Authorization / Token",
        "min_length": 10,
    },
]


def save_or_delete_credential(cloud_name: str, credential: str):
    """
    有值则保存，无值则删除对应凭证。
    删除不存在的记录也视为成功，便于前端直接通过清空输入框来移除配置。
    """
    if credential:
        return save_cookie(cloud_name, credential)

    if get_cookie_by_cloud_name(cloud_name) is None:
        return True, "云盘凭证已清空"

    return delete_cookie(cloud_name)


def _build_dynamic_transfer_statuses():
    statuses = []
    enabled_count = 0

    from src.db.accounts import get_accounts_by_cloud
    for config in DYNAMIC_TRANSFER_STATUS_CONFIGS:
        cloud_name = config["cloud_name"]
        credential_type = config["credential_type"]
        accounts = get_accounts_by_cloud(cloud_name)
        active_valid = [a for a in accounts if a.get("is_active") == 1 and a.get("is_valid") == 1]
        active_invalid = [a for a in accounts if a.get("is_active") == 1 and a.get("is_valid") != 1]

        if active_valid:
            status = {
                "cloud_name": cloud_name,
                "credential_type": credential_type,
                "status": "enabled",
                "title": f"就绪 ({len(active_valid)}号)",
                "description": f"账号池中有 {len(active_valid)} 个可用转存账号，已纳入动态调度与负载均衡池。",
            }
            enabled_count += 1
        elif active_invalid:
            status = {
                "cloud_name": cloud_name,
                "credential_type": credential_type,
                "status": "invalid",
                "title": "待检/失效",
                "description": f"已添加 {len(active_invalid)} 个账号但已被标记失效，建议前往「网盘账号池」重新测活或更新凭证。",
            }
        else:
            status = {
                "cloud_name": cloud_name,
                "credential_type": credential_type,
                "status": "missing",
                "title": "未配置",
                "description": f"账号池中暂无可用账号，动态转存时会回退原始链接。",
            }

        statuses.append(status)

    return {
        "statuses": statuses,
        "summary": {
            "enabled_count": enabled_count,
            "total_count": len(DYNAMIC_TRANSFER_STATUS_CONFIGS),
        },
    }


@system_config_bp.route("/admin/api-config", methods=["GET"])
@token_required
def api_config_page():
    tab = request.args.get("tab", "config")
    return render_template(
        "admin_api_config.html",
        active_page="config_api",
        current_tab=tab,
    )


@system_config_bp.route("/admin/frontend-config", methods=["GET"])
@token_required
def frontend_config_page():
    frontend_config = get_frontend_display_netdisk_config()
    api_mode_config = get_api_mode_config()
    link_check_config = get_frontend_link_check_config()
    dynamic_transfer_config = get_dynamic_transfer_netdisk_config()
    allow_excel = get_allow_excel_download_config()
    frontend_link_mode = get_frontend_link_mode()
    return render_template(
        "admin_frontend_config.html",
        frontend_netdisk_options=FRONTEND_DISPLAY_NETDISK_OPTIONS,
        link_check_netdisk_options=LINK_CHECK_NETDISK_OPTIONS,
        dynamic_transfer_netdisk_options=DYNAMIC_TRANSFER_NETDISK_OPTIONS,
        enabled_netdisks=set(frontend_config.get("enabled_netdisks", [])),
        link_check_netdisks=set(link_check_config.get("enabled_netdisks", [])),
        dynamic_transfer_netdisks=set(dynamic_transfer_config.get("enabled_netdisks", [])),
        enable_link_check=link_check_config.get("enabled", True),
        enable_frontend=api_mode_config.get("enable_frontend", True),
        allow_excel_download=allow_excel.get("allow_excel_download", True),
        enable_pc_qr_code=is_pc_qr_code_enabled(),
        enable_frontend_github=is_frontend_github_enabled(),
        frontend_link_mode=frontend_link_mode if isinstance(frontend_link_mode, str) else frontend_link_mode.get("mode", "view"),
        active_page="config_frontend",
    )


@system_config_bp.route("/admin/system-config", methods=["GET"])
@token_required
def system_config_page():
    tab = request.args.get("tab", "storage")
    return render_template(
        "system_config.html",
        frontend_netdisk_options=FRONTEND_DISPLAY_NETDISK_OPTIONS,
        active_page="config_system",
        current_tab=tab,
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


@system_config_bp.route("/admin/api/dynamic-transfer-netdisks", methods=["GET"])
@token_required
def get_dynamic_transfer_netdisks():
    config = get_dynamic_transfer_netdisk_config()
    return jsonify(
        {
            "success": True,
            "options": DYNAMIC_TRANSFER_NETDISK_OPTIONS,
            "enabled_netdisks": config["enabled_netdisks"],
        }
    )


@system_config_bp.route("/admin/api/dynamic-transfer-netdisks", methods=["PUT"])
@token_required
def update_dynamic_transfer_netdisks():
    data = request.get_json() or {}
    enabled_netdisks = data.get("enabled_netdisks", [])

    if not isinstance(enabled_netdisks, list):
        return jsonify({"success": False, "message": "动态转存网盘配置格式错误"}), 400

    if not save_dynamic_transfer_netdisk_config(enabled_netdisks):
        return jsonify({"success": False, "message": "动态转存网盘配置保存失败"}), 400

    return jsonify({
        "success": True,
        "message": "动态转存生效网盘配置保存成功",
        "data": {
            "options": DYNAMIC_TRANSFER_NETDISK_OPTIONS,
            "enabled_netdisks": enabled_netdisks,
        }
    })


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


@system_config_bp.route("/admin/api/pc-qr-code-config", methods=["GET"])
@token_required
def get_pc_qr_code_api():
    config = get_pc_qr_code_config()
    return jsonify({"success": True, "enabled": config["enabled"]})


@system_config_bp.route("/admin/api/pc-qr-code-config", methods=["PUT"])
@token_required
def update_pc_qr_code_api():
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", True))

    if not save_pc_qr_code_config(enabled):
        return jsonify({"success": False, "message": "PC转存二维码引导配置保存失败"}), 400

    return jsonify({"success": True, "message": f"PC转存二维码引导已{'开启' if enabled else '关闭'}"})


@system_config_bp.route("/admin/api/frontend-github-config", methods=["GET"])
@token_required
def get_frontend_github_api():
    config = get_frontend_github_config()
    return jsonify({"success": True, "enabled": config["enabled"]})


@system_config_bp.route("/admin/api/frontend-github-config", methods=["PUT"])
@token_required
def update_frontend_github_api():
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", True))

    if not save_frontend_github_config(enabled):
        return jsonify({"success": False, "message": "前台 GitHub 标识配置保存失败"}), 400

    return jsonify({"success": True, "message": f"前台 GitHub 标识展示已{'开启' if enabled else '关闭'}"})




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


@system_config_bp.route("/admin/api/allow-excel-download-config", methods=["GET"])
@token_required
def get_allow_excel_download():
    config = get_allow_excel_download_config()
    return jsonify({"success": True, "enabled": config["enabled"]})


@system_config_bp.route("/admin/api/allow-excel-download-config", methods=["PUT"])
@token_required
def update_allow_excel_download():
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", True))

    if not save_allow_excel_download_config(enabled):
        return jsonify({"success": False, "message": "Excel 导出配置保存失败"}), 400

    return jsonify(
        {
            "success": True,
            "message": "已允许前台下载 Excel" if enabled else "已禁止前台下载 Excel",
        }
    )


@system_config_bp.route("/admin/api/frontend-link-check-config", methods=["GET"])
@token_required
def get_frontend_link_check_route():
    config = get_frontend_link_check_config()
    return jsonify({
        "success": True,
        "enable_link_check": config["enable_link_check"],
        "enabled_check_pans": config.get("enabled_check_pans", LINK_CHECK_NETDISK_OPTIONS),
    })


@system_config_bp.route("/admin/api/frontend-link-check-config", methods=["PUT"])
@token_required
def update_frontend_link_check_route():
    data = request.get_json() or {}
    enable_link_check = bool(data.get("enable_link_check", True))
    enabled_check_pans = data.get("enabled_check_pans")

    if not save_frontend_link_check_config(enable_link_check, enabled_check_pans):
        return jsonify({"success": False, "message": "前台测活配置保存失败"}), 400

    saved_config = get_frontend_link_check_config()
    return jsonify({
        "success": True,
        "message": "前台测活与过滤配置保存成功",
        "data": {
            "enable_link_check": saved_config["enable_link_check"],
            "enabled_check_pans": saved_config["enabled_check_pans"],
        }
    })


@system_config_bp.route("/admin/api/credential-config", methods=["GET"])
@token_required
def get_credential_config():
    baidu_cookie = get_cookie_by_cloud_name("百度网盘")
    quark_cookie = get_cookie_by_cloud_name("夸克网盘")
    aliyun_token = get_cookie_by_cloud_name("阿里云盘")
    uc_cookie = get_cookie_by_cloud_name("UC网盘")
    xunlei_raw = get_cookie_by_cloud_name("迅雷网盘") or ""
    guangya_token = get_cookie_by_cloud_name("光鸭云盘")
    wukong_cookie = get_cookie_by_cloud_name("悟空网盘")
    caiyun_token = get_cookie_by_cloud_name("移动云盘")
    try:
        xunlei_config = json.loads(xunlei_raw) if xunlei_raw else {}
        if not isinstance(xunlei_config, dict):
            xunlei_config = {"refresh_token": str(xunlei_raw).strip()}
    except Exception:
        xunlei_config = {"refresh_token": str(xunlei_raw).strip()} if xunlei_raw else {}
    dynamic_transfer_status = _build_dynamic_transfer_statuses()
    return jsonify(
        {
            "baidu_cookie": baidu_cookie,
            "quark_cookie": quark_cookie,
            "aliyun_token": aliyun_token,
            "uc_cookie": uc_cookie,
            "xunlei_refresh_token": xunlei_config.get("refresh_token", ""),
            "xunlei_captcha_sign": xunlei_config.get("captcha_sign", ""),
            "xunlei_user_id": xunlei_config.get("user_id", ""),
            "guangya_token": guangya_token,
            "wukong_cookie": wukong_cookie,
            "caiyun_token": caiyun_token,
            "dynamic_transfer_statuses": dynamic_transfer_status["statuses"],
            "dynamic_transfer_summary": dynamic_transfer_status["summary"],
        }
    )


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
    guangya_token = data.get("guangya_token", "")
    wukong_cookie = data.get("wukong_cookie", "")
    caiyun_token = data.get("caiyun_token", "")

    for cloud_name, credential in [
        ("百度网盘", baidu_cookie),
        ("夸克网盘", quark_cookie),
        ("阿里云盘", aliyun_token),
        ("UC网盘", uc_cookie),
        ("光鸭云盘", guangya_token),
        ("悟空网盘", wukong_cookie),
        ("移动云盘", caiyun_token),
    ]:
        success, message = save_or_delete_credential(cloud_name, credential)
        if not success:
            return jsonify({"success": False, "message": message}), 500

    xunlei_credential = ""
    if xunlei_refresh_token:
        xunlei_credential = json.dumps(
            {
                "refresh_token": xunlei_refresh_token,
                "captcha_sign": xunlei_captcha_sign,
                "user_id": xunlei_user_id,
            },
            ensure_ascii=False,
        )

    success, message = save_or_delete_credential("迅雷网盘", xunlei_credential)
    if not success:
        return jsonify({"success": False, "message": message}), 500

    return jsonify({"success": True, "message": "云盘凭证保存成功"})


# ==================== 多账号池管理 API ====================

@system_config_bp.route("/admin/api/accounts", methods=["GET"])
@token_required
def list_accounts_api():
    cloud_name = request.args.get("cloud_name")
    accounts = get_all_accounts(cloud_name=cloud_name)

    total_space = sum(int(a.get("total_space_bytes") or 0) for a in accounts)
    used_space = sum(int(a.get("used_space_bytes") or 0) for a in accounts)
    left_space = sum(int(a.get("left_space_bytes") or 0) for a in accounts)
    active_count = sum(1 for a in accounts if a.get("is_active"))
    valid_count = sum(1 for a in accounts if a.get("is_valid") and a.get("is_active"))

    return jsonify({
        "success": True,
        "accounts": accounts,
        "summary": {
            "total_count": len(accounts),
            "active_count": active_count,
            "valid_count": valid_count,
            "total_space_bytes": total_space,
            "used_space_bytes": used_space,
            "left_space_bytes": left_space,
        }
    })


@system_config_bp.route("/admin/api/accounts", methods=["POST"])
@token_required
def create_account_api():
    data = request.get_json() or {}
    cloud_name = str(data.get("cloud_name", "")).strip()
    credential = str(data.get("credential", "")).strip()
    account_name = str(data.get("account_name", "")).strip()

    if not cloud_name or not credential:
        return jsonify({"success": False, "message": "网盘平台与账号凭证不能为空"}), 400

    if not account_name:
        account_name = f"{cloud_name}-账号"
        data["account_name"] = account_name

    account_id = create_account(data)
    if not account_id:
        return jsonify({"success": False, "message": "创建账号失败"}), 500

    auto_test = data.get("auto_test", True)
    if auto_test:
        def _bg_test(acc_id):
            try:
                mgr = AccountPoolManager.get_instance()
                mgr.inspect_and_refresh_account(acc_id)
            except Exception as e:
                logger.error(f"后台自动测活异常 account_id={acc_id}: {e}")

        threading.Thread(target=_bg_test, args=(account_id,), daemon=True).start()

    new_acc = get_account_by_id(account_id)
    return jsonify({
        "success": True,
        "message": "账号保存成功" + ("，已在后台启动自动测活与容量探测" if auto_test else ""),
        "account": new_acc,
        "is_testing": bool(auto_test),
        "test_result": {"tested": False, "async": bool(auto_test)},
    })


@system_config_bp.route("/admin/api/accounts/<int:account_id>", methods=["PUT"])
@token_required
def update_account_api(account_id: int):
    data = request.get_json() or {}
    existing = get_account_by_id(account_id)
    if not existing:
        return jsonify({"success": False, "message": "账号不存在"}), 404

    success = update_account(account_id, data)
    if not success:
        return jsonify({"success": False, "message": "更新账号失败"}), 500

    auto_test = data.get("auto_test", False) or data.get("retest", False) or ("credential" in data and data["credential"] != existing.get("credential"))
    if auto_test:
        def _bg_test(acc_id):
            try:
                mgr = AccountPoolManager.get_instance()
                mgr.inspect_and_refresh_account(acc_id)
            except Exception as e:
                logger.error(f"后台自动测活异常 account_id={acc_id}: {e}")

        threading.Thread(target=_bg_test, args=(account_id,), daemon=True).start()

    updated = get_account_by_id(account_id)
    return jsonify({
        "success": True,
        "message": "账号更新成功" + ("，已在后台启动自动测活与容量探测" if auto_test else ""),
        "account": updated,
        "is_testing": bool(auto_test),
    })


@system_config_bp.route("/admin/api/accounts/<int:account_id>", methods=["DELETE"])
@token_required
def delete_account_api(account_id: int):
    existing = get_account_by_id(account_id)
    if not existing:
        return jsonify({"success": False, "message": "账号不存在"}), 404

    success = delete_account(account_id)
    if not success:
        return jsonify({"success": False, "message": "删除账号失败"}), 500

    return jsonify({"success": True, "message": "账号删除成功"})


@system_config_bp.route("/admin/api/accounts/<int:account_id>/test", methods=["POST"])
@token_required
def test_account_api(account_id: int):
    existing = get_account_by_id(account_id)
    if not existing:
        return jsonify({"success": False, "message": "账号不存在"}), 404

    mgr = AccountPoolManager.get_instance()
    ok, msg, info = mgr.inspect_and_refresh_account(account_id)
    updated = get_account_by_id(account_id)

    return jsonify({
        "success": ok,
        "message": msg,
        "account": updated,
        "info": info,
    })


@system_config_bp.route("/admin/api/accounts/keepalive", methods=["POST"])
@token_required
def trigger_keepalive_api():
    mgr = AccountPoolManager.get_instance()
    res = mgr.keepalive_all_accounts()
    return jsonify({
        "success": True,
        "message": "账号保活与续期任务执行完成",
        "result": res,
    })


@system_config_bp.route("/admin/api/accounts/export-csv", methods=["GET"])
@token_required
def export_accounts_csv_api():
    """导出网盘账号池列表为 CSV"""
    cloud_name = request.args.get("cloud_name")
    csv_text = export_accounts_csv(cloud_name=cloud_name)
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{cloud_name}_" if cloud_name and cloud_name != "ALL" else ""
    ascii_filename = f"pan_relay_accounts_{prefix}{now_str}.csv"
    utf8_filename = urllib.parse.quote(f"网盘账号池_{prefix}{now_str}.csv")

    response = Response(csv_text, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}"
    return response


@system_config_bp.route("/admin/api/accounts/template-csv", methods=["GET"])
@token_required
def template_accounts_csv_api():
    """下载网盘账号批量导入 CSV 模板"""
    csv_text = generate_accounts_template_csv()
    ascii_filename = "pan_relay_accounts_template.csv"
    utf8_filename = urllib.parse.quote("网盘账号导入模板.csv")

    response = Response(csv_text, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}"
    return response


@system_config_bp.route("/admin/api/accounts/import-csv", methods=["POST"])
@token_required
def import_accounts_csv_api():
    """批量从 CSV 导入网盘账号"""
    auto_test = True
    if "auto_test" in request.args:
        auto_test = request.args.get("auto_test", "true").lower() in ("true", "1", "yes")
    elif "auto_test" in request.form:
        auto_test = request.form.get("auto_test", "true").lower() in ("true", "1", "yes")

    csv_data = None
    if "file" in request.files:
        file = request.files["file"]
        if not file or not file.filename:
            return jsonify({"success": False, "message": "未选择任何 CSV 文件"}), 400
        csv_data = file.read()
    elif request.is_json:
        data = request.get_json() or {}
        csv_data = data.get("csv_content", "")
        if "auto_test" in data:
            auto_test = bool(data.get("auto_test"))
    elif request.form and "csv_content" in request.form:
        csv_data = request.form.get("csv_content", "")

    if not csv_data:
        return jsonify({"success": False, "message": "上传的 CSV 数据为空"}), 400

    result = import_accounts_from_csv(csv_data, auto_test=auto_test)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code




@system_config_bp.route("/admin/api/search-scheduler-config", methods=["GET"])
@token_required
def get_search_scheduler_config_api():
    config = get_search_scheduler_config()
    return jsonify({"success": True, "config": config})


@system_config_bp.route("/admin/api/search-scheduler-config", methods=["PUT"])
@token_required
def update_search_scheduler_config_api():
    data = request.get_json() or {}
    success = save_search_scheduler_config(data)
    if not success:
        return jsonify({"success": False, "message": "搜索调度配置保存失败"}), 400

    return jsonify({
        "success": True,
        "message": "搜索调度配置保存成功",
        "config": get_search_scheduler_config(),
    })


@system_config_bp.route("/admin/api/tg-channels", methods=["GET"])
@token_required
def get_tg_channels_api():
    """获取 Telegram 公开频道列表及最近一次健康状态。"""
    channels = get_tg_channel_items()
    return jsonify({
        "success": True,
        "channels": channels,
        "summary": {
            "total_count": len(channels),
            "enabled_count": sum(1 for item in channels if item["is_enabled"]),
        },
    })


@system_config_bp.route("/admin/api/tg-channels", methods=["POST"])
@token_required
def add_tg_channel_api():
    data = request.get_json() or {}
    success, message, channel = add_tg_channel(
        data.get("channel"),
        bool(data.get("is_enabled", True)),
    )
    if not success:
        return jsonify({"success": False, "message": message}), 400
    return jsonify({"success": True, "message": message, "channel": channel}), 201


@system_config_bp.route("/admin/api/tg-channels/<string:channel>", methods=["DELETE"])
@token_required
def delete_tg_channel_api(channel):
    success, message = delete_tg_channel(channel)
    return jsonify({"success": success, "message": message}), 200 if success else 404


@system_config_bp.route("/admin/api/tg-channels/<string:channel>/enabled", methods=["PUT"])
@token_required
def toggle_tg_channel_api(channel):
    data = request.get_json() or {}
    if "is_enabled" not in data:
        return jsonify({"success": False, "message": "缺少 is_enabled 参数"}), 400
    success, message = set_tg_channel_enabled(channel, bool(data["is_enabled"]))
    return jsonify({"success": success, "message": message}), 200 if success else 404


@system_config_bp.route("/admin/api/tg-channels/enable-all", methods=["PUT"])
@token_required
def enable_all_tg_channels_api():
    success, message, count = set_all_tg_channels_enabled(True)
    return jsonify({"success": success, "message": message, "count": count}), 200 if success else 500


@system_config_bp.route("/admin/api/tg-channels/disable-all", methods=["PUT"])
@token_required
def disable_all_tg_channels_api():
    success, message, count = set_all_tg_channels_enabled(False)
    return jsonify({"success": success, "message": message, "count": count}), 200 if success else 500


def _run_and_record_tg_test(channel, keyword=None):
    result = test_telegram_connection(channel=channel, keyword=keyword)
    save_tg_channel_health(channel, result)
    return result


@system_config_bp.route("/admin/api/tg-channels/<string:channel>/test", methods=["POST"])
@token_required
def test_single_tg_channel_api(channel):
    normalized = normalize_tg_channel(channel)
    known_channels = {item["channel"] for item in get_tg_channel_items()}
    if normalized not in known_channels:
        return jsonify({"success": False, "message": "未找到该频道"}), 404
    data = request.get_json() or {}
    result = _run_and_record_tg_test(normalized, str(data.get("keyword", "")).strip() or None)
    return jsonify(result)


@system_config_bp.route("/admin/api/tg-channels/test-all", methods=["POST"])
@token_required
def test_all_tg_channels_api():
    data = request.get_json() or {}
    keyword = str(data.get("keyword", "")).strip() or None
    channels = [item["channel"] for item in get_tg_channel_items()]
    if not channels:
        return jsonify({"success": True, "message": "暂无可检测的频道", "results": []})

    config = get_search_scheduler_config()["tg"]
    workers = min(config["max_workers"], len(channels))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(test_telegram_connection, channel, keyword): channel
            for channel in channels
        }
        results = []
        for future in concurrent.futures.as_completed(futures):
            channel = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {
                    "success": False,
                    "channel": channel,
                    "message": str(error),
                    "latency_ms": 0,
                    "count": 0,
                    "results": [],
                }
            save_tg_channel_health(channel, result)
            results.append(result)

    healthy_count = sum(1 for result in results if result.get("success"))
    total = len(results)
    failed_count = total - healthy_count
    return jsonify({
        "success": True,
        "message": f"检测完成：{healthy_count}/{total} 个频道可连通",
        "total": total,
        "healthy_count": healthy_count,
        "failed_count": failed_count,
        "results": results,
    })


@system_config_bp.route("/admin/api/tg-channels/batch-toggle", methods=["PUT", "POST"])
@token_required
def batch_toggle_tg_channels_api():
    data = request.get_json() or {}
    channels = data.get("channels", [])
    is_enabled = bool(data.get("is_enabled"))
    if not channels:
        return jsonify({"success": False, "message": "缺少频道标识列表"}), 400

    count = 0
    for ch in channels:
        success, _ = set_tg_channel_enabled(ch, is_enabled)
        if success:
            count += 1
    action_str = "启用" if is_enabled else "停用"
    return jsonify({"success": True, "message": f"成功批量{action_str} {count} 个频道", "count": count})


@system_config_bp.route("/admin/api/tg-channels/batch-delete", methods=["POST", "DELETE"])
@token_required
def batch_delete_tg_channels_api():
    data = request.get_json() or {}
    channels = data.get("channels", [])
    if not channels:
        return jsonify({"success": False, "message": "缺少要删除的频道列表"}), 400

    count = 0
    for ch in channels:
        success, _ = delete_tg_channel(ch)
        if success:
            count += 1
    return jsonify({"success": True, "message": f"成功批量删除 {count} 个频道", "count": count})


@system_config_bp.route("/admin/api/tg-channels/test-batch", methods=["POST"])
@token_required
def test_batch_tg_channels_api():
    data = request.get_json() or {}
    target_channels = set(data.get("channels", []))
    keyword = str(data.get("keyword", "")).strip() or None
    if not target_channels:
        return jsonify({"success": False, "message": "缺少要测试的频道列表"}), 400

    all_channels = [item["channel"] for item in get_tg_channel_items()]
    channels = [ch for ch in all_channels if ch in target_channels]
    if not channels:
        return jsonify({"success": True, "message": "暂无可检测的指定频道", "results": []})

    config = get_search_scheduler_config()["tg"]
    workers = min(config["max_workers"], len(channels))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(test_telegram_connection, channel, keyword): channel
            for channel in channels
        }
        results = []
        for future in concurrent.futures.as_completed(futures):
            channel = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {
                    "success": False,
                    "channel": channel,
                    "message": str(error),
                    "latency_ms": 0,
                    "count": 0,
                    "results": [],
                }
            save_tg_channel_health(channel, result)
            results.append(result)

    healthy_count = sum(1 for result in results if result.get("success"))
    total = len(results)
    failed_count = total - healthy_count
    return jsonify({
        "success": True,
        "message": f"检测完成：{healthy_count}/{total} 个频道可连通",
        "total": total,
        "healthy_count": healthy_count,
        "failed_count": failed_count,
        "results": results,
    })




@system_config_bp.route("/admin/api/tg-search-config/test", methods=["POST"])
@token_required
def test_tg_search_api():
    """测试指定 Telegram 公开频道的检索与连通性"""
    data = request.get_json() or {}
    channel = str(data.get("channel", "")).strip()
    keyword = str(data.get("keyword", "")).strip() or None
    proxy = data.get("proxy")
    timeout = data.get("timeout")
    if timeout is not None:
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = 10

    result = test_telegram_connection(
        channel=channel,
        keyword=keyword,
        proxy=proxy,
        timeout=timeout,
    )
    save_tg_channel_health(channel, result)
    return jsonify(result)


@system_config_bp.route("/admin/api/sensitive-words-config", methods=["GET"])
@token_required
def get_sensitive_words_config_api():
    """获取敏感词过滤配置与词库"""
    config = get_sensitive_words_config()
    return jsonify({"success": True, "config": config})


@system_config_bp.route("/admin/api/sensitive-words-config", methods=["PUT"])
@token_required
def update_sensitive_words_config_api():
    """更新敏感词过滤配置与词库"""
    data = request.get_json() or {}
    success = save_sensitive_words_config(data)
    if not success:
        return jsonify({"success": False, "message": "敏感词配置保存失败"}), 400

    return jsonify({
        "success": True,
        "message": "敏感词配置保存成功",
        "config": get_sensitive_words_config(),
    })


@system_config_bp.route("/admin/api/transfer-target-dir", methods=["GET"])
@token_required
def get_transfer_target_dir_api():
    """获取转存目标目录配置"""
    target_dir = get_transfer_target_dir()
    return jsonify({"success": True, "target_dir": target_dir})


@system_config_bp.route("/admin/api/transfer-target-dir", methods=["POST", "PUT"])
@token_required
def update_transfer_target_dir_api():
    """更新转存目标目录配置"""
    data = request.get_json() or {}
    target_dir = data.get("target_dir", "")
    success = save_transfer_target_dir(target_dir)
    if not success:
        return jsonify({"success": False, "message": "转存目标目录配置保存失败"}), 500

    return jsonify({
        "success": True,
        "message": "转存目标目录配置保存成功",
        "target_dir": get_transfer_target_dir(),
    })


@system_config_bp.route("/admin/api/ad-filter-config", methods=["GET"])
@token_required
def get_ad_filter_config_api():
    """获取广告过滤配置与关键词库"""
    config = get_ad_filter_config()
    return jsonify({"success": True, "config": config})


@system_config_bp.route("/admin/api/ad-filter-config", methods=["PUT", "POST"])
@token_required
def update_ad_filter_config_api():
    """更新广告过滤配置与关键词库"""
    data = request.get_json() or {}
    success = save_ad_filter_config(data)
    if not success:
        return jsonify({"success": False, "message": "广告过滤配置保存失败"}), 400

    return jsonify({
        "success": True,
        "message": "广告过滤配置保存成功",
        "config": get_ad_filter_config(),
    })


@system_config_bp.route("/admin/api/storage-cleanup-config", methods=["GET"])
@token_required
def get_storage_cleanup_config_api():
    """获取存储优化与自动清理策略配置及统计信息"""
    from src.services.storage_cleanup_service import get_storage_stats
    stats = get_storage_stats()
    return jsonify({"success": True, "data": stats})


@system_config_bp.route("/admin/api/storage-cleanup-config", methods=["PUT", "POST"])
@token_required
def update_storage_cleanup_config_api():
    """更新存储优化与自动清理策略配置"""
    data = request.get_json() or {}
    success = save_storage_cleanup_config(data)
    if not success:
        return jsonify({"success": False, "message": "存储自动清理配置保存失败"}), 400

    from src.services.scheduler_service import reload_storage_cleanup_job
    reload_storage_cleanup_job()

    return jsonify({
        "success": True,
        "message": "存储自动清理配置保存成功",
        "config": get_storage_cleanup_config(),
    })


@system_config_bp.route("/admin/api/custom-ad-config", methods=["GET"])
@token_required
def get_custom_ad_config_api():
    """获取自定义引流广告植入配置"""
    config = get_custom_ad_injection_config()
    return jsonify({"success": True, "config": config})


@system_config_bp.route("/admin/api/custom-ad-config", methods=["PUT", "POST"])
@token_required
def update_custom_ad_config_api():
    """更新自定义引流广告植入配置"""
    data = request.get_json() or {}
    success = save_custom_ad_injection_config(data)
    if not success:
        return jsonify({"success": False, "message": "自定义广告配置保存失败"}), 400

    return jsonify({
        "success": True,
        "message": "自定义广告配置保存成功",
        "config": get_custom_ad_injection_config(),
    })


@system_config_bp.route("/admin/api/storage-cleanup/run", methods=["POST"])
@token_required
def run_storage_cleanup_now_api():
    """立即手动触发一次完整存储优化与过期资源清理"""
    from src.services.storage_cleanup_service import cleanup_all_storage
    result = cleanup_all_storage()
    return jsonify({"success": True, "message": "存储优化与清理任务执行完毕", "result": result})


@system_config_bp.route("/admin/api/api-mode-config", methods=["GET"])
@token_required
def get_api_mode_config_api():
    """获取 API_ONLY 模式及 UI 开关配置"""
    config = get_api_mode_config()
    return jsonify({"success": True, "config": config})


@system_config_bp.route("/admin/api/api-mode-config", methods=["PUT", "POST"])
@token_required
def update_api_mode_config_api():
    """更新 API 模式、前台 UI 开关、检索默认参数与安全转存 Key 配置"""
    data = request.get_json() or {}
    api_only = data.get("api_only", False)
    enable_frontend = data.get("enable_frontend", True)
    search_scope = data.get("search_scope", "all")
    search_limit = data.get("search_limit", 50)
    search_scope_lock = bool(data.get("search_scope_lock", False))
    search_limit_lock = bool(data.get("search_limit_lock", False))
    transfer_api_key = data.get("transfer_api_key", "")

    success = save_api_mode_config(
        api_only=api_only,
        enable_frontend=enable_frontend,
        search_scope=search_scope,
        search_limit=search_limit,
        search_scope_lock=search_scope_lock,
        search_limit_lock=search_limit_lock,
        transfer_api_key=transfer_api_key,
    )
    if not success:
        return jsonify({"success": False, "message": "API 模式配置保存失败"}), 400

    return jsonify({
        "success": True,
        "message": "API 模式与默认检索配置保存成功",
        "config": get_api_mode_config(),
    })


@system_config_bp.route("/admin/api/security-config", methods=["GET"])
@token_required
def get_security_config_api():
    """获取安全防护配置（IP 黑名单、频控、最小关键词长度等）"""
    config = get_security_config()
    return jsonify({"success": True, "config": config})


@system_config_bp.route("/admin/api/security-config", methods=["PUT", "POST"])
@token_required
def update_security_config_api():
    """更新安全防护配置"""
    data = request.get_json(silent=True) or {}
    success = save_security_config(data)
    if not success:
        return jsonify({"success": False, "message": "安全防护配置保存失败"}), 400
    return jsonify({
        "success": True,
        "message": "安全防护配置保存成功",
        "config": get_security_config(),
    })


@system_config_bp.route("/admin/api/ip-blacklist/add", methods=["POST"])
@token_required
def add_ip_blacklist_api():
    """快捷添加 IP 到黑名单"""
    data = request.get_json(silent=True) or {}
    ip = str(data.get("ip", "")).strip()
    if not ip:
        return jsonify({"success": False, "message": "缺少有效的 IP 参数"}), 400
    success = add_ip_to_blacklist(ip)
    if success:
        return jsonify({"success": True, "message": f"IP {ip} 已成功加入封禁黑名单", "config": get_security_config()})
    return jsonify({"success": False, "message": "添加黑名单失败"}), 500


@system_config_bp.route("/admin/api/ip-blacklist/remove", methods=["POST", "DELETE"])
@token_required
def remove_ip_blacklist_api():
    """从黑名单中移除 IP"""
    data = request.get_json(silent=True) or {}
    ip = str(data.get("ip", "")).strip()
    if not ip:
        return jsonify({"success": False, "message": "缺少有效的 IP 参数"}), 400
    success = remove_ip_from_blacklist(ip)
    if success:
        return jsonify({"success": True, "message": f"IP {ip} 已从黑名单解封", "config": get_security_config()})
    return jsonify({"success": False, "message": "解封 IP 失败"}), 500







