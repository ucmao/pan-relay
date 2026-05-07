import datetime
from functools import wraps

import jwt
from flask import request, redirect, url_for

from configs.app_config import SECRET_KEY


def create_jwt_token():
    """创建 JWT 令牌，有效期 24 小时"""
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    payload = {
        "exp": expiration,
        "iat": datetime.datetime.utcnow(),
        "sub": "admin",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token


def token_required(f):
    """JWT 令牌验证装饰器"""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")

        if not token:
            return redirect(url_for("auth.login"))

        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return redirect(url_for("auth.login"))
        except jwt.InvalidTokenError:
            return redirect(url_for("auth.login"))

        return f(*args, **kwargs)

    return decorated

