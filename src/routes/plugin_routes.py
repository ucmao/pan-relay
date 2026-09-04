import logging
from flask import Blueprint, jsonify, request

from src.services.plugin_manager import plugin_manager
from src.utils.auth_utils import token_required
from src.utils.test_keywords import build_test_keywords

logger = logging.getLogger(__name__)

plugin_bp = Blueprint("plugin", __name__)


@plugin_bp.route("/admin/api/plugins", methods=["GET"])
@token_required
def get_admin_plugins_api():
    """
    获取系统中所有插件列表及元数据 (管理员接口)
    """
    plugins = plugin_manager.get_all_plugins()
    data = [p.to_dict() for p in plugins]
    return jsonify({
        "success": True,
        "total": len(data),
        "enabled_count": len([p for p in plugins if p.is_enabled]),
        "plugins": data,
    })


@plugin_bp.route("/admin/api/plugins/<plugin_name>/toggle", methods=["POST"])
@token_required
def toggle_admin_plugin_api(plugin_name):
    """
    切换指定插件的启用/停用状态 (管理员接口)
    """
    return toggle_plugin_api(plugin_name)


@plugin_bp.route("/admin/api/plugins/<plugin_name>/test", methods=["POST"])
@token_required
def test_admin_plugin_api(plugin_name):
    """
    在线测试单个插件检索 (管理员接口)
    """
    return test_plugin_api(plugin_name)


@plugin_bp.route("/admin/api/plugins/<plugin_name>/health", methods=["GET"])
@token_required
def health_admin_plugin_api(plugin_name):
    """
    检查指定插件连通性与健康度 (管理员接口)
    """
    return health_plugin_api(plugin_name)


@plugin_bp.route("/admin/api/plugins/reload", methods=["POST"])
@token_required
def reload_admin_plugins_api():
    """
    热重载重新扫描插件目录 (管理员接口)
    """
    try:
        plugins = plugin_manager.reload_plugins()
        data = [p.to_dict() for p in plugins]
        return jsonify({
            "success": True,
            "message": f"成功重新扫描插件目录，共载入 {len(data)} 个插件",
            "total": len(data),
            "enabled_count": len([p for p in plugins if p.is_enabled]),
            "plugins": data,
        })
    except Exception as e:
        logger.error(f"重新加载插件异常: {e}")
        return jsonify({"success": False, "message": f"重新载入插件失败: {e}"}), 500


@plugin_bp.route("/admin/api/plugins/enable-all", methods=["POST"])
@token_required
def enable_all_admin_plugins_api():
    """全部启用插件"""
    plugins = plugin_manager.get_all_plugins()
    for p in plugins:
        plugin_manager.enable_plugin(p.name)
    return jsonify({"success": True, "message": "已全部启用所有插件"})


@plugin_bp.route("/admin/api/plugins/disable-all", methods=["POST"])
@token_required
def disable_all_admin_plugins_api():
    """全部禁用插件"""
    plugins = plugin_manager.get_all_plugins()
    for p in plugins:
        plugin_manager.disable_plugin(p.name)
    return jsonify({"success": True, "message": "已全部停用所有插件"})


@plugin_bp.route("/api/plugins", methods=["GET"])
def get_plugins_api():
    """
    获取系统中所有已发现并注册的插件列表及元数据
    """
    plugins = plugin_manager.get_all_plugins()
    data = [p.to_dict() for p in plugins]
    return jsonify({
        "success": True,
        "total": len(data),
        "enabled_count": len([p for p in plugins if p.is_enabled]),
        "plugins": data,
    })


@plugin_bp.route("/api/plugins/<plugin_name>/toggle", methods=["POST"])
def toggle_plugin_api(plugin_name):
    """
    切换指定插件的启用/停用状态
    """
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        return jsonify({"success": False, "message": f"未找到插件: {plugin_name}"}), 404

    payload = request.get_json(silent=True) or {}
    if "is_enabled" in payload:
        new_status = bool(payload["is_enabled"])
        if new_status:
            plugin_manager.enable_plugin(plugin_name)
        else:
            plugin_manager.disable_plugin(plugin_name)
    else:
        # 默认取反切换
        if plugin.is_enabled:
            plugin_manager.disable_plugin(plugin_name)
        else:
            plugin_manager.enable_plugin(plugin_name)

    return jsonify({
        "success": True,
        "name": plugin_name,
        "is_enabled": plugin.is_enabled,
        "message": f"插件 [{plugin_name}] 状态已更新为: {'启用' if plugin.is_enabled else '停用'}",
    })


@plugin_bp.route("/api/plugins/<plugin_name>/test", methods=["POST"])
def test_plugin_api(plugin_name):
    """
    测试单个插件的搜索能力
    """
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        return jsonify({"success": False, "message": f"未找到插件: {plugin_name}"}), 404

    payload = request.get_json(silent=True) or {}
    keyword = str(payload.get("keyword") or "").strip() or None
    keywords = build_test_keywords(keyword)
    saw_empty_response = False
    last_error = None

    for test_keyword in keywords:
        try:
            results = plugin.search(test_keyword)
            if not results:
                saw_empty_response = True
                continue
            serialized = [item.to_dict() for item in results]
            return jsonify({
                "success": True,
                "plugin": plugin_name,
                "keyword": test_keyword,
                "tested_keywords": keywords,
                "count": len(serialized),
                "results": serialized,
            })
        except Exception as e:
            last_error = str(e)
            logger.warning("测试插件 [%s] 使用关键词“%s”异常，继续轮询: %s", plugin_name, test_keyword, e)

    if saw_empty_response:
        return jsonify({
            "success": True,
            "plugin": plugin_name,
            "keyword": None,
            "tested_keywords": keywords,
            "count": 0,
            "results": [],
            "message": "插件可调用，但轮询关键词均无结果",
        })

    logger.error("测试插件 [%s] 多关键词轮询均异常: %s", plugin_name, last_error)
    return jsonify({
        "success": False,
        "plugin": plugin_name,
        "tested_keywords": keywords,
        "message": f"插件多关键词测试均异常: {last_error or '未知异常'}",
    }), 500


@plugin_bp.route("/api/plugins/<plugin_name>/health", methods=["GET"])
def health_plugin_api(plugin_name):
    """
    检查指定插件的连通性与健康度
    """
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        return jsonify({"success": False, "message": f"未找到插件: {plugin_name}"}), 404

    try:
        ok, msg = plugin.health_check()
        return jsonify({
            "success": True,
            "plugin": plugin_name,
            "healthy": ok,
            "message": msg,
        })
    except Exception as e:
        return jsonify({
            "success": True,
            "plugin": plugin_name,
            "healthy": False,
            "message": str(e),
        })
