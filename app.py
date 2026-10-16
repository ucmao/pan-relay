import logging
import os
from src.configs.logging_setup import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from flask import Flask, render_template, jsonify, request, redirect, url_for
from src.routes.api_config_routes import api_config_bp
from src.routes.search_routes import search_bp
from src.routes.resource_routes import resources_bp
from src.routes.auth_routes import auth_bp
from src.routes.system_config_routes import system_config_bp
from src.routes.plugin_routes import plugin_bp
from src.routes.search_sources_routes import search_sources_bp
from src.routes.dashboard_routes import dashboard_bp
from src.routes.api_v1_routes import api_v1_bp
from src.routes.log_routes import log_bp
from src.configs.app_config import SECRET_KEY
from src.db.connection import init_sqlite_db
from src.services.scheduler_service import start_scheduler
from src.services.system_config_service import (
    get_frontend_link_mode,
    get_frontend_display_netdisk_config,
    get_frontend_link_check_config,
    get_dynamic_transfer_netdisk_config,
    is_excel_download_enabled,
    is_pc_qr_code_enabled,
    is_frontend_github_enabled,
    get_frontend_github_config,
    is_frontend_enabled,
    is_api_only_enabled,
    get_active_theme,
    get_site_logo,
    get_site_name,
    build_frontend_seo_meta,
    is_resource_request_enabled,
    is_hot_searches_enabled,
    get_hot_search_words,
    get_frontend_disclaimer_text,
)
from src.services.theme_service import theme_static_bp
from src.utils.netdisk_utils import get_netdisk_drive_type
import jinja2

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 配置多主题模板加载器支持
themes_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
app.jinja_loader = jinja2.ChoiceLoader([
    app.jinja_loader,
    jinja2.FileSystemLoader(themes_path),
])

app.secret_key = SECRET_KEY


FRONTEND_NETDISK_ICONS = {
    "夸克网盘": "kuake-dark.svg",
    "百度网盘": "icon_baiduwangpan-dark.svg",
    "阿里云盘": "ali-dark.svg",
    "迅雷网盘": "xunlei1-dark.svg",
    "UC网盘": "changyonglogo31-dark.svg",
    "光鸭云盘": "guangya-dark.svg",
    "悟空网盘": "wukong-dark.svg",
    "移动云盘": "yidong-dark.svg",
    "磁力链接": "zhongzi-dark.svg",
    "迅雷链接": "zhongzi-dark.svg",
    "电驴链接": "zhongzi-dark.svg",
}


def get_frontend_theme_netdisks():
    """准备模板二使用的前台网盘标签，遵循后台配置顺序并最多展示九项。"""
    enabled_netdisks = get_frontend_display_netdisk_config().get("enabled_netdisks", [])[:9]
    result = []
    for name in enabled_netdisks:
        label = name
        for suffix in ("网盘", "云盘", "链接"):
            if label.endswith(suffix):
                label = label[:-len(suffix)]
                break
        icon = FRONTEND_NETDISK_ICONS.get(name)
        result.append({
            "name": name,
            "label": label or name,
            "drive": get_netdisk_drive_type(name),
            "icon": f"/themes/aurora/assets/{icon}" if icon else "",
        })
    return result

# 初始化 SQLite 数据库与表结构
init_sqlite_db()

# 初始化管理员账号认证配置（初次启动哈希落库）
from src.services.admin_auth_service import init_admin_auth, is_using_default_password, get_admin_username
init_admin_auth()

# 注册蓝图
app.register_blueprint(theme_static_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_config_bp)
app.register_blueprint(search_bp)
app.register_blueprint(resources_bp)
app.register_blueprint(system_config_bp)
app.register_blueprint(plugin_bp)
app.register_blueprint(search_sources_bp)
app.register_blueprint(api_v1_bp)
app.register_blueprint(log_bp)
start_scheduler()

# 上下文处理器，将登录状态传递给所有模板
@app.context_processor
def inject_login_status():
    token = request.cookies.get('token')
    is_logged_in = False
    try:
        if token:
            import jwt
            jwt.decode(token, app.secret_key, algorithms=['HS256'])
            is_logged_in = True
    except Exception:
        pass

    is_default_pwd = False
    admin_name = 'Admin'
    if is_logged_in:
        try:
            is_default_pwd = is_using_default_password()
            admin_name = get_admin_username()
        except Exception:
            pass

    return {
        'is_logged_in': is_logged_in,
        'enable_frontend_github': is_frontend_github_enabled(),
        'frontend_footer_text': get_frontend_github_config().get('footer_text', 'Pan-Relay 聚合分发中枢 · 极速流式引擎'),
        'frontend_disclaimer_text': get_frontend_disclaimer_text(),
        'is_default_admin_password': is_default_pwd,
        'admin_username': admin_name,
        'site_logo': get_site_logo(),
        'site_name': get_site_name(),
        'enable_resource_request': is_resource_request_enabled(),
        'enable_hot_searches': is_hot_searches_enabled(),
        'hot_search_words': get_hot_search_words(),
    }


@app.before_request
def check_ui_access():
    path = request.path

    # 若试图访问前台根路径但前台 UI 已关闭，自动重定向至后台管理登录页
    if path == "/" and not is_frontend_enabled():
        return redirect(url_for('auth.login'))


# 首页，支持根据当前激活主题渲染不同模板
@app.route('/')
def search_index():
    if not is_frontend_enabled():
        return redirect(url_for('auth.login'))

    active_theme = get_active_theme()
    link_mode = get_frontend_link_mode()
    link_check_config = get_frontend_link_check_config()
    dynamic_transfer_config = get_dynamic_transfer_netdisk_config()
    search_term = request.args.get('keyword') or request.args.get('q') or request.args.get('kw') or ''

    ctx = {
        'seo_meta': build_frontend_seo_meta('search' if search_term.strip() else 'home', search_term),
        'frontend_link_mode': link_mode,
        'allow_excel_download': (link_mode != "view") and is_excel_download_enabled(),
        'enable_link_check': link_check_config.get("enable_link_check", True),
        'enabled_check_pans': link_check_config.get("enabled_check_pans", []),
        'enabled_dynamic_transfer_pans': dynamic_transfer_config.get("enabled_netdisks", []),
        'enable_pc_qr_code': is_pc_qr_code_enabled(),
        'enable_frontend_github': is_frontend_github_enabled(),
        'frontend_footer_text': get_frontend_github_config().get('footer_text', 'Pan-Relay 聚合分发中枢 · 极速流式引擎'),
        'enable_resource_request': is_resource_request_enabled(),
        'enable_hot_searches': is_hot_searches_enabled(),
        'hot_search_words': get_hot_search_words(),
        'frontend_theme_netdisks': get_frontend_theme_netdisks(),
    }

    if active_theme in ("aurora", "sougs"):
        return render_template('aurora/templates/index.html', **ctx)
    return render_template('default/templates/index.html', **ctx)


# 搜索结果页 (主要用于 aurora 主题或独立搜索 URL)
@app.route('/search')
def search_page():
    if not is_frontend_enabled():
        return redirect(url_for('auth.login'))

    active_theme = get_active_theme()
    q = request.args.get('q') or request.args.get('keyword') or ''
    link_mode = get_frontend_link_mode()
    link_check_config = get_frontend_link_check_config()

    if active_theme in ("aurora", "sougs"):
        return render_template(
            'aurora/templates/search.html',
            query=q,
            seo_meta=build_frontend_seo_meta('search', q),
            frontend_link_mode=link_mode,
            enable_link_check=link_check_config.get("enable_link_check", True),
            enabled_check_pans=link_check_config.get("enabled_check_pans", []),
            enable_pc_qr_code=is_pc_qr_code_enabled(),
            enable_resource_request=is_resource_request_enabled(),
            enable_hot_searches=is_hot_searches_enabled(),
            hot_search_words=get_hot_search_words(),
            frontend_theme_netdisks=get_frontend_theme_netdisks(),
        )
    return redirect(url_for('search_index', keyword=q))


# 独立 API 接入文档网页
@app.route('/docs')
def public_api_docs_page():
    return render_template('api_docs.html')



if __name__ == '__main__':
    port = int(os.getenv("PORT", 5004))
    logger.info(f"启动 Flask 应用，监听端口: {port}")
    app.run(host='0.0.0.0', port=port)
