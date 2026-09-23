from flask import Blueprint, jsonify, render_template, request
import concurrent.futures
import json

from src.db.credentials import delete_cookie, get_cookie_by_cloud_name, save_cookie
from src.services.system_config_service import (
    get_public_search_api_config,
    get_allow_excel_download_config,
    get_frontend_link_check_config,
    get_frontend_display_netdisk_config,
    get_frontend_link_mode,
    get_transfer_target_dir,
    get_sensitive_words_config,
    get_ad_filter_config,
    get_custom_ad_injection_config,
    get_storage_cleanup_config,
    get_search_scheduler_config,
    get_api_mode_config,
    save_api_mode_config,
    save_public_search_api_config,
    save_allow_excel_download_config,
    save_frontend_link_check_config,
    save_frontend_display_netdisk_config,
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
from src.utils.netdisk_utils import FRONTEND_DISPLAY_NETDISK_OPTIONS

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
        "credential_type": "Refresh Token / Captcha Sign / User ID",
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

    for config in DYNAMIC_TRANSFER_STATUS_CONFIGS:
        cloud_name = config["cloud_name"]
        credential_type = config["credential_type"]
        raw_credential = (get_cookie_by_cloud_name(cloud_name) or "").strip()

        status = {
            "cloud_name": cloud_name,
            "credential_type": credential_type,
            "status": "missing",
            "title": "未配置",
            "description": f"未填写 {credential_type}，动态转存时会回退原始链接。",
        }

        if cloud_name == "迅雷网盘":
            if raw_credential:
                try:
                    parsed = json.loads(raw_credential)
                except json.JSONDecodeError:
                    parsed = {}

                required_fields = ("refresh_token", "captcha_sign", "user_id")
                has_all_fields = isinstance(parsed, dict) and all(str(parsed.get(field, "")).strip() for field in required_fields)

                if has_all_fields:
                    status = {
                        "cloud_name": cloud_name,
                        "credential_type": credential_type,
                        "status": "enabled",
                        "title": "已就绪",
                        "description": "已检测到完整凭证，动态查看时会优先生成临时分享链接。",
                    }
                    enabled_count += 1
                else:
                    status = {
                        "cloud_name": cloud_name,
                        "credential_type": credential_type,
                        "status": "invalid",
                        "title": "凭证不完整",
                        "description": "需要同时填写 refresh_token、captcha_sign 和 user_id。",
                    }

            statuses.append(status)
            continue

        if raw_credential:
            if len(raw_credential) >= config["min_length"]:
                status = {
                    "cloud_name": cloud_name,
                    "credential_type": credential_type,
                    "status": "enabled",
                    "title": "已就绪",
                    "description": "已检测到可用凭证，动态查看时会优先生成临时分享链接。",
                }
                enabled_count += 1
            else:
                status = {
                    "cloud_name": cloud_name,
                    "credential_type": credential_type,
                    "status": "invalid",
                    "title": "凭证可能失效",
                    "description": "已保存凭证，但基础校验未通过，建议重新获取后保存。",
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
    return render_template(
        "admin_frontend_config.html",
        frontend_netdisk_options=FRONTEND_DISPLAY_NETDISK_OPTIONS,
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
        "default_hide_dead_links": config["default_hide_dead_links"],
    })


@system_config_bp.route("/admin/api/frontend-link-check-config", methods=["PUT"])
@token_required
def update_frontend_link_check_route():
    data = request.get_json() or {}
    enable_link_check = bool(data.get("enable_link_check", True))
    default_hide_dead_links = bool(data.get("default_hide_dead_links", False))

    if not save_frontend_link_check_config(enable_link_check, default_hide_dead_links):
        return jsonify({"success": False, "message": "前台测活配置保存失败"}), 400

    return jsonify({
        "success": True,
        "message": "前台测活与过滤配置保存成功",
        "data": {
            "enable_link_check": enable_link_check,
            "default_hide_dead_links": default_hide_dead_links,
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
    except json.JSONDecodeError:
        xunlei_config = {}
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

    has_any_xunlei_field = any([xunlei_refresh_token, xunlei_captcha_sign, xunlei_user_id])
    has_all_xunlei_fields = all([xunlei_refresh_token, xunlei_captcha_sign, xunlei_user_id])
    if has_any_xunlei_field and not has_all_xunlei_fields:
        return jsonify({"success": False, "message": "迅雷网盘凭证需要同时填写 refresh_token、captcha_sign 和 user_id"}), 400

    xunlei_credential = ""
    if has_all_xunlei_fields:
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
    """更新 API 模式及前台 UI 开关与安全转存 Key 配置"""
    data = request.get_json() or {}
    api_only = data.get("api_only", False)
    enable_frontend = data.get("enable_frontend", True)
    search_scope = data.get("search_scope", "own")
    transfer_api_key = data.get("transfer_api_key", "")

    success = save_api_mode_config(
        api_only=api_only,
        enable_frontend=enable_frontend,
        search_scope=search_scope,
        transfer_api_key=transfer_api_key,
    )
    if not success:
        return jsonify({"success": False, "message": "API 模式配置保存失败"}), 400

    return jsonify({
        "success": True,
        "message": "API 模式配置保存成功",
        "config": get_api_mode_config(),
    })






