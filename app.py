import logging
import os
from src.configs.logging_setup import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from flask import Flask, render_template
from src.routes.api_config_routes import api_config_bp
from src.routes.search_routes import search_bp
from src.routes.resource_routes import resources_bp
from src.routes.auth_routes import auth_bp
from src.routes.system_config_routes import system_config_bp
from src.routes.plugin_routes import plugin_bp
from src.routes.search_sources_routes import search_sources_bp
from src.configs.app_config import SECRET_KEY
from src.db.connection import init_sqlite_db
from src.services.scheduler_service import start_scheduler
from src.services.system_config_service import get_frontend_link_mode

app = Flask(__name__)


app.secret_key = SECRET_KEY

# 初始化 SQLite 数据库与表结构
init_sqlite_db()

# 注册蓝图
app.register_blueprint(auth_bp)
app.register_blueprint(api_config_bp)
app.register_blueprint(search_bp)
app.register_blueprint(resources_bp)
app.register_blueprint(system_config_bp)
app.register_blueprint(plugin_bp)
app.register_blueprint(search_sources_bp)
start_scheduler()

# 上下文处理器，将登录状态传递给所有模板
@app.context_processor
def inject_login_status():
    from flask import request
    import jwt
    token = request.cookies.get('token')
    is_logged_in = False
    try:
        if token:
            jwt.decode(token, app.secret_key, algorithms=['HS256'])
            is_logged_in = True
    except jwt.ExpiredSignatureError:
        pass
    except jwt.InvalidTokenError:
        pass
    return {'is_logged_in': is_logged_in}


# 首页，返回 HTML 文件
@app.route('/')
def search_index():
    return render_template('index.html', frontend_link_mode=get_frontend_link_mode())


if __name__ == '__main__':
    port = int(os.getenv("PORT", 5004))
    logger.info(f"启动 Flask 应用，监听端口: {port}")
    app.run(host='0.0.0.0', port=port)
