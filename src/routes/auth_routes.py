# src/routes/auth_routes.py

import logging
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
import jwt

from src.configs.app_config import SECRET_KEY
from src.db.logs import insert_system_log
from src.services.admin_auth_service import (
    change_admin_password,
    get_admin_username,
    is_using_default_password,
    verify_admin_credentials,
)
from src.utils.auth_utils import create_jwt_token, token_required

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


# 登录页面路由
@auth_bp.route('/login', methods=['GET', 'POST'])
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

        is_valid, msg = verify_admin_credentials(username, password)
        if is_valid:
            token = create_jwt_token(username=username)
            response = redirect(url_for('dashboard.dashboard_page'))
            response.set_cookie('token', token, httponly=True)

            logger.info(f"管理员 {username} 登录成功")
            insert_system_log(
                log_type="admin",
                action="管理员登录成功",
                query_text=f"用户名: {username}",
                status_code=200,
                client_ip=request.remote_addr,
            )
            return response
        else:
            logger.warning(f"管理员登录失败，用户名: {username}")
            insert_system_log(
                log_type="admin",
                action="管理员登录失败",
                query_text=f"用户名: {username}",
                status_code=401,
                error_message=msg,
                client_ip=request.remote_addr,
            )
            return render_template('login.html', error='账号或密码错误')

    return render_template('login.html')


# 登出路由
@auth_bp.route('/logout')
@auth_bp.route('/admin/logout')
def logout():
    response = redirect(url_for('search_index'))
    response.set_cookie('token', '', expires=0)
    return response


# 修改密码接口
@auth_bp.route('/admin/api/change_password', methods=['POST'])
@auth_bp.route('/admin/api/change-password', methods=['POST'])
@token_required
def api_change_password():
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    old_password = str(payload.get('old_password') or '').strip()
    new_password = str(payload.get('new_password') or '').strip()
    confirm_password = str(payload.get('confirm_password') or '').strip()
    new_username = str(payload.get('username') or '').strip() or None

    if not old_password:
        return jsonify({'success': False, 'message': '请输入当前原密码'}), 400
    if not new_password:
        return jsonify({'success': False, 'message': '请输入新密码'}), 400
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '新密码长度至少需要 6 位字符'}), 400
    if confirm_password and new_password != confirm_password:
        return jsonify({'success': False, 'message': '两次输入的新密码不一致'}), 400

    success, message = change_admin_password(
        old_password=old_password,
        new_password=new_password,
        new_username=new_username,
    )

    if not success:
        return jsonify({'success': False, 'message': message}), 400

    current_user = new_username or get_admin_username()
    insert_system_log(
        log_type="admin",
        action="修改管理员密码成功",
        query_text=f"管理员: {current_user}",
        status_code=200,
        client_ip=request.remote_addr,
    )

    # 密码修改成功后无缝签发新 Token 刷新 Cookie
    new_token = create_jwt_token(username=current_user)
    resp = jsonify({'success': True, 'message': '密码修改成功'})
    resp.set_cookie('token', new_token, httponly=True)
    return resp


# 检查密码状态接口（查询是否为初始默认弱密码）
@auth_bp.route('/admin/api/password_status', methods=['GET'])
@token_required
def api_password_status():
    return jsonify({
        'success': True,
        'data': {
            'username': get_admin_username(),
            'is_default_password': is_using_default_password(),
        }
    })
