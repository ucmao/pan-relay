import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class XunleiDrive:
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
            logger.error("迅雷网盘获取 access_token 失败")
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
            logger.error("迅雷网盘获取分享信息失败: %s", detail)
            return None, None, None
        if detail.get("share_status") and detail.get("share_status") != "OK":
            logger.error("迅雷网盘分享状态异常: %s", detail)
            return None, None, None

        file_ids = [item["id"] for item in detail.get("files", []) if item.get("id")]
        if not file_ids or not detail.get("pass_code_token"):
            logger.error("迅雷网盘分享详情缺少必要字段")
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
            logger.error("迅雷网盘转存失败: %s", restore_result)
            return None, None, None

        task_result = self._wait_task(restore_result.get("restore_task_id"))
        if not task_result or task_result.get("progress") != 100:
            logger.error("迅雷网盘转存任务未完成: %s", task_result)
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
            logger.error("迅雷网盘创建分享失败: %s", share_result)
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
            return False
        return not bool(result.get("error_code"))

    def _get_access_token(self) -> str:
        if self.access_token:
            return self.access_token

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
        self.access_token = data.get("access_token", "")
        return self.access_token

    def _get_captcha_token(self, action: str) -> str:
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
        return response.json().get("captcha_token", "")

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
