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
    get_frontend_link_check_config,
    is_excel_download_enabled,
    is_frontend_enabled,
    is_admin_ui_enabled,
    is_api_only_enabled,
)

app = Flask(__name__)

app.secret_key = SECRET_KEY

# 初始化 SQLite 数据库与表结构
init_sqlite_db()

# 注册蓝图
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
    return {'is_logged_in': is_logged_in}


@app.before_request
def check_ui_access():
    path = request.path

    # 若试图访问前台根路径但前台 UI 已关闭，自动重定向至后台管理登录页
    if path == "/" and not is_frontend_enabled():
        return redirect(url_for('auth.login'))

    # 若试图访问后台 HTML 页面但后台 UI 已关闭
    if path.startswith("/admin") and not path.startswith("/admin/api") and not is_admin_ui_enabled():
        return jsonify({
            "success": False,
            "message": "后台管理 UI 当前已被禁用",
        }), 403


# 首页，返回 HTML 文件或重定向
@app.route('/')
def search_index():
    if not is_frontend_enabled():
        return redirect(url_for('auth.login'))

    link_check_config = get_frontend_link_check_config()

    return render_template(
        'index.html',
        frontend_link_mode=get_frontend_link_mode(),
        allow_excel_download=is_excel_download_enabled(),
        enable_link_check=link_check_config.get("enable_link_check", True),
        default_hide_dead_links=link_check_config.get("default_hide_dead_links", False),
    )


# 独立 API 接入文档网页
@app.route('/docs')
def public_api_docs_page():
    return render_template('api_docs.html')



if __name__ == '__main__':
    port = int(os.getenv("PORT", 5004))
    logger.info(f"启动 Flask 应用，监听端口: {port}")
    app.run(host='0.0.0.0', port=port)
