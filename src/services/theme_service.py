import os
import logging
from typing import List, Dict, Any, Optional
from flask import Blueprint, send_from_directory, abort, current_app

from src.services.system_config_service import get_active_theme, save_active_theme

logger = logging.getLogger(__name__)

# 项目根目录与 themes 目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
THEMES_DIR = os.path.join(BASE_DIR, "themes")

# 预置主题元信息
THEMES_METADATA = [
    {
        "id": "classic",
        "name": "模板 1 · 经典聚合风",
        "version": "1.2.0",
        "author": "Pan-Relay",
        "description": "系统经典网盘搜索聚合页面，支持高级筛选与快捷转存。",
        "preview": "/themes/classic/assets/preview.webp",
        "tags": ["经典聚合", "功能全面"],
    },
    {
        "id": "aurora",
        "name": "模板 2 · 极光双模风",
        "version": "1.0.0",
        "author": "Pan-Relay",
        "description": "现代极简双模流式主题，带3D动态热词球与网盘极速分类Tab。",
        "preview": "/themes/aurora/assets/preview.webp",
        "tags": ["极简极速", "暗黑双模"],
    },
    {
        "id": "cinema",
        "name": "模板 3 · 影视精选风",
        "version": "1.1.0",
        "author": "Pan-Relay",
        "description": "影视资源搜索首页，展示热搜词与站长精选资源。",
        "preview": "/themes/cinema/assets/preview.webp",
        "tags": ["影视搜索", "热搜榜单", "精选资源"],
    },
]

theme_static_bp = Blueprint("theme_static", __name__)


@theme_static_bp.route("/themes/<theme_name>/assets/<path:filename>")
def serve_theme_asset(theme_name: str, filename: str):
    """
    提供多主题静态资源文件的通用访问路由：
    /themes/{theme_name}/assets/{path:filename} -> themes/{theme_name}/static/{filename}
    """
    theme_static_dir = os.path.join(THEMES_DIR, theme_name, "static")
    if not os.path.exists(theme_static_dir):
        abort(404, description=f"Theme static directory not found: {theme_name}")
    return send_from_directory(theme_static_dir, filename)


def get_available_themes() -> List[Dict[str, Any]]:
    """获取所有可用主题列表，标注当前激活状态"""
    active_id = get_active_theme()
    result = []
    for meta in THEMES_METADATA:
        item = dict(meta)
        item["is_active"] = (item["id"] == active_id)
        result.append(item)
    return result


def switch_theme(theme_id: str) -> bool:
    """切换当前前台主题"""
    valid_ids = {t["id"] for t in THEMES_METADATA}
    if theme_id not in valid_ids:
        return False
    return save_active_theme(theme_id)
