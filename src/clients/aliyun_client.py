import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.clients.base_client import BasePanClient

logger = logging.getLogger(__name__)


class AliyunPanClient(BasePanClient):
    def __init__(self, refresh_token: str) -> None:
        self.refresh_token = refresh_token.strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://www.alipan.com",
                "Referer": "https://www.alipan.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "X-Canary": "client=web,app=share,version=v2.3.1",
            }
        )
        self.access_token = ""
        self.drive_id = ""
        self._refresh_access_token()

    def store(
        self, share_url: str, to_dir: str = "root"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        share_id = self._extract_share_id(share_url)
        if not share_id:
            logger.error("阿里云盘链接解析失败: %s", share_url)
            return None, None, None

        share_info = self._post_anonymous(
            "https://api.aliyundrive.com/adrive/v3/share_link/get_share_by_anonymous",
            {"share_id": share_id},
        )
        if not share_info or not share_info.get("file_infos"):
            logger.error("阿里云盘获取分享信息失败: %s", share_info)
            return None, None, None

        share_token_data = self._request(
            "POST",
            "https://api.aliyundrive.com/v2/share_link/get_share_token",
            {"share_id": share_id},
        )
        share_token = (share_token_data or {}).get("share_token")
        if not share_token:
            logger.error("阿里云盘获取 share_token 失败: %s", share_token_data)
            return None, None, None

        file_infos = share_info["file_infos"]
        title = share_info.get("share_name") or file_infos[0].get("name") or "阿里云盘资源"

        requests_payload = []
        for idx, file_info in enumerate(file_infos):
            requests_payload.append(
                {
                    "body": {
                        "auto_rename": True,
                        "file_id": file_info["file_id"],
                        "share_id": share_id,
                        "to_drive_id": self.drive_id,
                        "to_parent_file_id": to_dir or "root",
                    },
                    "headers": {"Content-Type": "application/json"},
                    "id": str(idx),
                    "method": "POST",
                    "url": "/file/copy",
                }
            )

        batch_result = self._request(
            "POST",
            "https://api.aliyundrive.com/adrive/v4/batch",
            {"requests": requests_payload, "resource": "file"},
            extra_headers={"X-Share-Token": share_token},
        )
        responses = (batch_result or {}).get("responses") or []
        if not responses:
            logger.error("阿里云盘批量转存失败: %s", batch_result)
            return None, None, None

        new_file_ids: List[str] = []
        for item in responses:
            body = item.get("body") or {}
            if body.get("code"):
                logger.error("阿里云盘转存返回错误: %s", body)
                return None, None, None
            if body.get("file_id"):
                new_file_ids.append(body["file_id"])

        if not new_file_ids:
            logger.error("阿里云盘未返回转存后的 file_id")
            return None, None, None

        share_result = self._request(
            "POST",
            "https://api.aliyundrive.com/adrive/v2/share_link/create",
            {
                "drive_id": self.drive_id,
                "expiration": "",
                "share_pwd": "",
                "file_id_list": new_file_ids,
            },
        )
        share_url_new = (share_result or {}).get("share_url")
        if not share_url_new:
            logger.error("阿里云盘创建分享失败: %s", share_result)
            return None, None, None

        return json.dumps(new_file_ids, ensure_ascii=False), title, share_url_new

    def del_file(self, file_ids: List[str]) -> bool:
        if not file_ids:
            return False

        requests_payload = []
        for idx, file_id in enumerate(file_ids):
            requests_payload.append(
                {
                    "body": {"drive_id": self.drive_id, "file_id": file_id},
                    "headers": {"Content-Type": "application/json"},
                    "id": f"trash-{idx}",
                    "method": "POST",
                    "url": "/recyclebin/trash",
                }
            )

        result = self._request(
            "POST",
            "https://api.aliyundrive.com/adrive/v4/batch",
            {"requests": requests_payload, "resource": "file"},
        )
        responses = (result or {}).get("responses") or []
        return bool(responses)

    def _refresh_access_token(self) -> None:
        data = self._post_anonymous(
            "https://api.aliyundrive.com/token/refresh",
            {"refresh_token": self.refresh_token},
        )
        if not data or not data.get("access_token"):
            raise ValueError("阿里云盘 refresh_token 无效或已过期")

        self.access_token = data["access_token"]
        self.drive_id = (
            data.get("default_drive_id")
            or data.get("resource_drive_id")
            or data.get("backup_drive_id")
            or ""
        )
        if not self.drive_id:
            raise ValueError("阿里云盘未返回有效 drive_id")

        self.session.headers["Authorization"] = f"Bearer {self.access_token}"

    def _request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        headers = dict(self.session.headers)
        if extra_headers:
            headers.update(extra_headers)

        response = self.session.request(method, url, json=payload or {}, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()

    def _post_anonymous(self, url: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_share_id(url: str) -> str:
        match = re.search(r"/s/([a-zA-Z0-9]+)", url)
        if match:
            return match.group(1)
        return ""
