import logging
from flask import Blueprint, jsonify, request

from src.services.plugin_manager import plugin_manager

logger = logging.getLogger(__name__)

plugin_bp = Blueprint("plugin", __name__)


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
    keyword = str(payload.get("keyword") or "测试").strip()

    try:
        results = plugin.search(keyword)
        serialized = [item.to_dict() for item in results]
        return jsonify({
            "success": True,
            "plugin": plugin_name,
            "keyword": keyword,
            "count": len(serialized),
            "results": serialized,
        })
    except Exception as e:
        logger.error(f"测试插件 [{plugin_name}] 出错: {e}")
        return jsonify({
            "success": False,
            "plugin": plugin_name,
            "message": f"插件测试异常: {e}",
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
