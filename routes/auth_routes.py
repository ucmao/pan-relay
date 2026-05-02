# routes/auth.py

from flask import Blueprint, render_template, redirect, request, url_for
import logging

logger = logging.getLogger(__name__)

# 导入应用配置
from configs.app_config import ADMIN_USERNAME, ADMIN_PASSWORD
from utils.auth_utils import create_jwt_token

auth_bp = Blueprint('auth', __name__)

# 登录页面路由
@auth_bp.route('/admin', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # 创建JWT令牌
            token = create_jwt_token()
            
            # 创建响应对象，重定向到系统配置页面
            response = redirect(url_for('system_config.system_config_page'))
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
def logout():
    response = redirect(url_for('search_index'))
    # 删除JWT令牌cookie
    response.set_cookie('token', '', expires=0)
    return response
