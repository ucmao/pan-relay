# src/routes/auth_routes.py

from flask import Blueprint, render_template, redirect, request, url_for
import jwt
import logging

logger = logging.getLogger(__name__)

# 导入应用配置
from src.configs.app_config import ADMIN_USERNAME, ADMIN_PASSWORD
from src.configs.app_config import SECRET_KEY
from src.utils.auth_utils import create_jwt_token

auth_bp = Blueprint('auth', __name__)

# 登录页面路由
@auth_bp.route('/admin', methods=['GET', 'POST'])
def login():
    token = request.cookies.get('token')
    if request.method == 'GET' and token:
        try:
            jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return redirect(url_for('dashboard.dashboard_page'))
        except jwt.PyJWTError:
            pass

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            return render_template('login.html', error='账号或密码不能为空')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # 创建JWT令牌
            token = create_jwt_token()
            
            # 创建响应对象，重定向到后台资源页
            response = redirect(url_for('dashboard.dashboard_page'))
            # 设置JWT令牌到cookie
            response.set_cookie('token', token, httponly=True)
            
            logger.info(f"管理员 {username} 登录成功")
            return response
        else:
            logger.warning(f"管理员登录失败，用户名: {username}")
            return render_template('login.html', error='账号或密码错误')
    
    return render_template('login.html')

# 登出路由
@auth_bp.route('/logout')
@auth_bp.route('/admin/logout')
def logout():
    response = redirect(url_for('search_index'))
    # 删除JWT令牌cookie
    response.set_cookie('token', '', expires=0)
    return response
