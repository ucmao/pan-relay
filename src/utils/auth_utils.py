import datetime
from functools import wraps

import jwt
from flask import jsonify, redirect, request, url_for

from src.configs.app_config import SECRET_KEY


def create_jwt_token():
    """创建 JWT 令牌，有效期 24 小时"""
    now = datetime.datetime.now(datetime.timezone.utc)
    expiration = now + datetime.timedelta(hours=24)
    payload = {
        "exp": expiration,
        "iat": now,
        "sub": "admin",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token


def token_required(f):
    """JWT 令牌验证装饰器"""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")

        def _handle_unauthorized():
            is_api_request = (
                request.path.startswith("/admin/api/")
                or request.path.startswith("/api/")
                or request.is_json
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or "application/json" in request.headers.get("Accept", "")
            )
            if is_api_request:
                return jsonify({"success": False, "message": "未登录或登录态已失效，请重新登录"}), 401
            return redirect(url_for("auth.login"))

        if not token:
            return _handle_unauthorized()

        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return _handle_unauthorized()

        return f(*args, **kwargs)

    return decorated

