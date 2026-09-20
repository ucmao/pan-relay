import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.clients.base_client import BasePanClient

logger = logging.getLogger(__name__)

# 全局缓存，避免频繁刷新 Token 触发风控
# 结构: {refresh_token: {"access_token": str, "expires_at": float}}
_XUNLEI_ACCESS_TOKEN_CACHE: Dict[str, Dict[str, Any]] = {}
# 结构: {(device_id, action): {"captcha_token": str, "expires_at": float}}
_XUNLEI_CAPTCHA_TOKEN_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}


class XunleiPanClient(BasePanClient):
    client_id = "Xqp0kJBXWhwaTpB6"
    device_id = "925b7631473a13716b791d7f28289cad"

    def __init__(self, credential: Dict[str, str]) -> None:
        self.refresh_token = (credential.get("refresh_token") or "").strip()
        self.captcha_sign = (credential.get("captcha_sign") or "").strip()
        self.user_id = str(credential.get("user_id") or "").strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": "https://pan.xunlei.com",
                "Referer": "https://pan.xunlei.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/139.0.0.0 Safari/537.36"
                ),
                "x-client-id": self.client_id,
                "x-device-id": self.device_id,
            }
        )
        self.access_token = ""

    def store(
        self, share_url: str, to_dir: str = ""
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        share_id, pwd = self._parse_share_url(share_url)
        if not share_id:
            logger.error("迅雷网盘链接解析失败: %s", share_url)
            return None, None, None

        access_token = self._get_access_token()
        if not access_token:
            logger.error("迅雷网盘获取 access_token 失败，无法继续转存")
            return None, None, None

        detail = self._request_pan(
            "GET",
            "https://api-pan.xunlei.com/drive/v1/share",
            params={
                "share_id": share_id,
                "pass_code": pwd,
                "limit": 100,
                "pass_code_token": "",
                "page_token": "",
                "thumbnail_size": "SIZE_SMALL",
            },
            action="get:/drive/v1/share",
        )
        if not detail or detail.get("error_code"):
            err_msg = (detail or {}).get("error_description") or (detail or {}).get("error_code") or "未知错误"
            logger.error("迅雷网盘获取分享信息失败: %s (share_id=%s)", err_msg, share_id)
            return None, None, None

        share_status = detail.get("share_status")
        if share_status and share_status != "OK":
            if share_status == "SENSITIVE_RESOURCE":
                logger.error("迅雷网盘分享内容涉及侵权或敏感违规，已被官方屏蔽: share_id=%s", share_id)
            else:
                status_text = detail.get("share_status_text") or share_status
                logger.error("迅雷网盘分享状态异常: %s (share_id=%s)", status_text, share_id)
            return None, None, None

        file_ids = [item["id"] for item in detail.get("files", []) if item.get("id")]
        if not file_ids or not detail.get("pass_code_token"):
            logger.error("迅雷网盘分享详情缺少必要字段: file_ids=%s, pass_code_token=%s", file_ids, bool(detail.get("pass_code_token")))
            return None, None, None

        restore_result = self._request_pan(
            "POST",
            "https://api-pan.xunlei.com/drive/v1/share/restore",
            payload={
                "parent_id": to_dir or "",
                "share_id": share_id,
                "pass_code_token": detail["pass_code_token"],
                "ancestor_ids": [],
                "specify_parent_id": True,
                "file_ids": file_ids,
            },
            action="post:/drive/v1/share/restore",
        )
        if not restore_result or restore_result.get("error_code"):
            err_msg = (restore_result or {}).get("error_description") or (restore_result or {}).get("error_code") or "转存接口异常"
            logger.error("迅雷网盘转存失败: %s", err_msg)
            return None, None, None

        task_result = self._wait_task(restore_result.get("restore_task_id"))
        if not task_result or task_result.get("progress") != 100:
            err_msg = (task_result or {}).get("message") or "转存任务未完成或超时"
            logger.error("迅雷网盘转存任务失败: %s", err_msg)
            return None, None, None

        trace_file_ids = []
        raw_trace = ((task_result.get("params") or {}).get("trace_file_ids")) or ""
        if raw_trace:
            try:
                parsed = json.loads(raw_trace)
                if isinstance(parsed, dict):
                    trace_file_ids = list(parsed.values())
                elif isinstance(parsed, list):
                    trace_file_ids = parsed
            except json.JSONDecodeError:
                trace_file_ids = []

        if not trace_file_ids:
            logger.error("迅雷网盘未解析出转存后的文件 ID")
            return None, None, None

        share_result = self._request_pan(
            "POST",
            "https://api-pan.xunlei.com/drive/v1/share",
            payload={
                "file_ids": trace_file_ids,
                "share_to": "copy",
                "params": {
                    "subscribe_push": "false",
                    "WithPassCodeInLink": "true",
                },
                "title": "云盘资源分享",
                "restore_limit": "-1",
                "expiration_days": "-1",
            },
            action="post:/drive/v1/share",
        )
        if not share_result or share_result.get("error_code") or not share_result.get("share_url"):
            err_msg = (share_result or {}).get("error_description") or (share_result or {}).get("error_code") or "创建分享失败"
            logger.error("迅雷网盘创建分享失败: %s", err_msg)
            return None, None, None

        final_url = share_result["share_url"]
        if share_result.get("pass_code"):
            final_url = f"{final_url}?pwd={share_result['pass_code']}"

        title = (detail.get("files") or [{}])[0].get("name") or "迅雷网盘资源"
        return json.dumps(trace_file_ids, ensure_ascii=False), title, final_url

    def del_file(self, file_ids: List[str]) -> bool:
        normalized_ids = [item for item in file_ids if item]
        if not normalized_ids:
            return False

        result = self._request_pan(
            "POST",
            "https://api-pan.xunlei.com/drive/v1/files:batchDelete",
            payload={"ids": normalized_ids, "space": ""},
            action="post:/drive/v1/files:batchDelete",
        )
        if result is None:
            logger.error("迅雷网盘删除文件请求无响应: %s", normalized_ids)
            return False
        if result.get("error_code"):
            logger.error("迅雷网盘删除文件失败: %s", result.get("error_description") or result.get("error_code"))
            return False
        return True

    def _get_access_token(self) -> str:
        global _XUNLEI_ACCESS_TOKEN_CACHE

        now = time.time()
        cached = _XUNLEI_ACCESS_TOKEN_CACHE.get(self.refresh_token)
        if cached and cached.get("access_token") and now < cached.get("expires_at", 0) - 60:
            self.access_token = cached["access_token"]
            return self.access_token

        try:
            response = requests.post(
                "https://xluser-ssl.xunlei.com/v1/auth/token",
                json={
                    "client_id": self.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": self.session.headers["User-Agent"],
                    "x-client-id": self.client_id,
                    "x-device-id": self.device_id,
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("迅雷网盘获取 access_token 请求异常: %s", exc)
            return ""

        if data.get("code") != 0 or not data.get("data", {}).get("access_token"):
            err_msg = data.get("error_description") or data.get("msg") or data.get("code")
            logger.error("迅雷网盘 refresh_token 认证失败: %s", err_msg)
            return ""

        token_data = data["data"]
        self.access_token = token_data.get("access_token", "")
        expires_in = int(token_data.get("expires_in", 7200))
        new_refresh_token = token_data.get("refresh_token")

        # 缓存 Access Token
        _XUNLEI_ACCESS_TOKEN_CACHE[self.refresh_token] = {
            "access_token": self.access_token,
            "expires_at": now + expires_in,
        }

        # 轮换机制：若返回新的 refresh_token，自动更新数据库凭证
        if new_refresh_token and new_refresh_token != self.refresh_token:
            logger.info("迅雷网盘返回新的 refresh_token，正在执行自动轮换持久化...")
            try:
                from src.db.credentials import update_xunlei_refresh_token
                update_xunlei_refresh_token(new_refresh_token)
                _XUNLEI_ACCESS_TOKEN_CACHE[new_refresh_token] = _XUNLEI_ACCESS_TOKEN_CACHE.pop(self.refresh_token)
                self.refresh_token = new_refresh_token
            except Exception as exc:
                logger.warning("迅雷网盘持久化新 refresh_token 异常: %s", exc)

        return self.access_token

    def _get_captcha_token(self, action: str) -> str:
        global _XUNLEI_CAPTCHA_TOKEN_CACHE

        now = time.time()
        cache_key = (self.device_id, action)
        cached = _XUNLEI_CAPTCHA_TOKEN_CACHE.get(cache_key)
        if cached and cached.get("captcha_token") and now < cached.get("expires_at", 0) - 10:
            return cached["captcha_token"]

        try:
            response = requests.post(
                "https://xluser-ssl.xunlei.com/v1/shield/captcha/init",
                json={
                    "client_id": self.client_id,
                    "action": action,
                    "device_id": self.device_id,
                    "meta": {
                        "package_name": "pan.xunlei.com",
                        "client_version": "1.92.23",
                        "captcha_sign": self.captcha_sign,
                        "timestamp": str(int(time.time() * 1000)),
                        "user_id": self.user_id,
                    },
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": self.session.headers["User-Agent"],
                    "x-client-id": self.client_id,
                    "x-device-id": self.device_id,
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error("迅雷网盘获取 captcha_token 异常: %s", exc)
            return ""

        captcha_token = data.get("data", {}).get("captcha_token", "")
        expires_in = int(data.get("data", {}).get("expires_in", 300))
        if captcha_token:
            _XUNLEI_CAPTCHA_TOKEN_CACHE[cache_key] = {
                "captcha_token": captcha_token,
                "expires_at": now + expires_in,
            }

        return captcha_token

    def _wait_task(self, task_id: str, retries: int = 20) -> Optional[Dict[str, Any]]:
        if not task_id:
            return None
        for _ in range(retries):
            result = self._request_pan(
                "GET",
                f"https://api-pan.xunlei.com/drive/v1/tasks/{task_id}",
                action="get:/drive/v1/tasks",
            )
            if result and not result.get("error_code") and result.get("progress") == 100:
                return result
            time.sleep(0.5)
        return result if "result" in locals() else None

    def _request_pan(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        action: str = "get:/drive/v1/share",
    ) -> Optional[Dict[str, Any]]:
        access_token = self._get_access_token()
        captcha_token = self._get_captcha_token(action)
        if not access_token or not captcha_token:
            return None

        headers = dict(self.session.headers)
        headers["Authorization"] = f"Bearer {access_token}"
        headers["x-captcha-token"] = captcha_token

        response = self.session.request(
            method,
            url,
            json=payload if payload is not None else None,
            params=params,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_share_url(url: str) -> Tuple[str, str]:
        share_match = re.search(r"/s/([^?#/]+)", url)
        pwd_match = re.search(r"pwd=([a-zA-Z0-9]+)", url)
        return (
            share_match.group(1) if share_match else "",
            pwd_match.group(1) if pwd_match else "",
        )


