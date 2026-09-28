# src/services/link_checker/detectors/xunlei.py

import hashlib
import json
import logging
import re
import threading
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from src.utils.netdisk_utils import extract_password_from_url
from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)

# Android 移动端签名体系 (com.xunlei.downloadprovider)
_CLIENT_ID = "Xp6vsxz_7IYVw2BB"
_CLIENT_VERSION = "8.31.0.9726"
_PACKAGE_NAME = "com.xunlei.downloadprovider"
_DEVICE_ID = "c24ecadc44c643637d127fb847dbe36d"
_USER_AGENT = (
    "ANDROID-com.xunlei.downloadprovider/8.31.0.9726 "
    "netWorkType/5G appid/40 deviceName/Xiaomi_M2004j7ac "
    "deviceModel/M2004J7AC OSVersion/12 protocolVersion/301 "
    "platformVersion/10 sdkVersion/512000 Oauth2Client/0.9 "
    "(Linux 4_14_186-perf-gddfs8vbb238b) (JAVA 0)"
)
_ALGORITHMS = [
    "9uJNVj/wLmdwKrJaVj/omlQ",
    "Oz64Lp0GigmChHMf/6TNfxx7O9PyopcczMsnf",
    "Eb+L7Ce+Ej48u",
    "jKY0",
    "ASr0zCl6v8W4aidjPK5KHd1Lq3t+vBFf41dqv5+fnOd",
    "wQlozdg6r1qxh0eRmt3QgNXOvSZO6q/GXK",
    "gmirk+ciAvIgA/cxUUCema47jr/YToixTT+Q6O",
    "5IiCoM9B1/788ntB",
    "P07JH0h6qoM6TSUAK2aL9T5s2QBVeY9JWvalf",
    "+oK0AN",
]

_TOKEN_CACHE: Dict[str, Any] = {"token": "", "expires_at": 0.0}
_TOKEN_LOCK = threading.Lock()


def _calc_captcha_sign(client_id: str, client_version: str, package_name: str, device_id: str, ts: int) -> str:
    s = f"{client_id}{client_version}{package_name}{device_id}{ts}"
    for salt in _ALGORITHMS:
        s = hashlib.md5((s + salt).encode("utf-8")).hexdigest()
    return f"1.{s}"


def _get_captcha_token(session: Optional[requests.Session] = None) -> str:
    """获取迅雷公共验证码令牌 (自动计算签名并带 TTL 缓存)"""
    global _TOKEN_CACHE
    now = time.time()
    with _TOKEN_LOCK:
        if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"]:
            return _TOKEN_CACHE["token"]

    ts = int(now * 1000)
    sign = _calc_captcha_sign(_CLIENT_ID, _CLIENT_VERSION, _PACKAGE_NAME, _DEVICE_ID, ts)
    sess = session or requests.Session()
    try:
        resp = sess.post(
            "https://xluser-ssl.xunlei.com/v1/shield/captcha/init",
            json={
                "client_id": _CLIENT_ID,
                "action": "get:/drive/v1/share",
                "device_id": _DEVICE_ID,
                "meta": {
                    "package_name": _PACKAGE_NAME,
                    "client_version": _CLIENT_VERSION,
                    "captcha_sign": sign,
                    "timestamp": str(ts),
                    "user_id": "",
                },
            },
            headers={
                "Content-Type": "application/json",
                "User-Agent": _USER_AGENT,
                "x-client-id": _CLIENT_ID,
                "x-device-id": _DEVICE_ID,
            },
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("captcha_token") or data.get("data", {}).get("captcha_token") or ""
            expires_in = int(data.get("expires_in") or data.get("data", {}).get("expires_in") or 300)
            if token:
                with _TOKEN_LOCK:
                    _TOKEN_CACHE["token"] = token
                    _TOKEN_CACHE["expires_at"] = now + expires_in - 20
                return token
    except Exception as exc:
        logger.debug("获取迅雷验证码令牌异常: %s", exc)

    return ""


class XunleiDetector(BaseDetector):
    platform_name = "迅雷云盘"
    domain_patterns = ["pan.xunlei.com", "xunlei.com"]
    supported_keywords = ["xunlei", "迅雷"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(r"pan\.xunlei\.com/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析迅雷网盘分享ID"}
        share_id = match.group(1)
        pwd = password or extract_password_from_url(url) or ""

        sess = session or requests.Session()
        captcha_token = _get_captcha_token(sess)

        api = f"https://api-pan.xunlei.com/drive/v1/share?share_id={quote(share_id)}&pass_code={quote(pwd)}&limit=20"
        headers = self.get_headers({
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "x-client-id": _CLIENT_ID,
            "x-device-id": _DEVICE_ID,
        })
        if captcha_token:
            headers["x-captcha-token"] = captcha_token

        try:
            resp = sess.get(api, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"迅雷网盘请求失败: {e}"}

        if resp.status_code in (404,):
            return {"state": STATE_BAD, "summary": "链接不存在或已失效"}

        share_status = str(data.get("share_status") or "")
        files = data.get("files") or []
        file_count = data.get("file_count", len(files))
        share_name = data.get("share_name")
        if not share_name and files:
            share_name = files[0].get("name", "")

        err_msg = str(data.get("error_description") or data.get("error") or "")
        error_code = data.get("error_code")
        error_details = data.get("error_details") or []
        detail_str = " ".join(str(d.get("detail", "")) for d in error_details if isinstance(d, dict))

        # 密码错误或需要提取码
        if (
            share_status in ("PASS_CODE_EMPTY", "PASS_CODE_ERROR")
            or contains_any(err_msg, ["pass_code", "提取码", "密码", "访问码"])
            or error_code == 1004
        ):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}

        # 链接有效
        if share_status == "OK" or file_count > 0 or share_name:
            if file_count == 0 and not share_name:
                return {"state": STATE_BAD, "summary": "分享链接无文件或内容为空", "file_count": 0}
            return {
                "state": STATE_OK,
                "summary": "链接有效",
                "file_count": file_count,
                "share_name": share_name,
            }

        # 明确失效或违规
        if share_status == "SENSITIVE_RESOURCE" or contains_any(err_msg, ["敏感", "侵权", "违规", "屏蔽"]):
            return {"state": STATE_BAD, "summary": "资源涉及侵权或敏感违规，已被官方屏蔽"}

        if contains_any(share_status, ["DELETED", "EXPIRED", "CANCELLED", "NOT_FOUND"]):
            return {"state": STATE_BAD, "summary": f"分享状态异常: {share_status}"}

        if (
            contains_any(err_msg, ["不存在", "已删除", "已取消", "已过期", "分享已关闭", "资源不存在"])
            or contains_any(detail_str, ["share_id invalid", "not found", "deleted", "expired"])
        ):
            return {"state": STATE_BAD, "summary": err_msg or "链接已失效或不存在"}

        # 验证码/风控/未认证限制：网盘资源本身可能正常，归为 STATE_UNCERTAIN
        if (
            contains_any(err_msg, ["captcha", "验证码", "token", "unauthenticated", "no client info", "sign"])
            or data.get("error") in ("captcha_invalid", "unauthenticated", "unauthorized")
        ):
            return {"state": STATE_UNCERTAIN, "summary": "迅雷官方限制(需验证码或凭证)，无法自动确认状态"}

        if err_msg:
            return {"state": STATE_UNCERTAIN, "summary": err_msg}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认迅雷分享状态"}
