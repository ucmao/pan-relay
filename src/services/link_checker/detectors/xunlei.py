# src/services/link_checker/detectors/xunlei.py

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from src.utils.netdisk_utils import extract_password_from_url
from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


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
        api = f"https://api-pan.xunlei.com/drive/v1/share?share_id={quote(share_id)}&pass_code={quote(pwd)}&limit=20"
        headers = self.get_headers({
            "Content-Type": "application/json",
            "Origin": "https://pan.xunlei.com",
            "Referer": "https://pan.xunlei.com/",
            "x-client-id": "ZUBzD9J_XPXfn7f7",
            "x-device-id": "5505bd0cab8c9469b98e5891d9fb3e0d",
        })

        try:
            resp = sess.get(api, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"迅雷网盘请求失败: {e}"}

        if resp.status_code in (404, 403):
            return {"state": STATE_BAD, "summary": "链接失效或不存在"}

        share_status = str(data.get("share_status") or "")
        file_count = data.get("file_count", 0)
        share_name = data.get("share_name")
        err_msg = str(data.get("error_description") or data.get("error") or "")

        if contains_any(err_msg, ["pass_code", "提取码", "密码"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}

        if share_status == "OK" or file_count > 0 or share_name:
            if file_count == 0 and not share_name:
                return {"state": STATE_BAD, "summary": "分享链接无文件或内容为空", "file_count": 0}
            return {"state": STATE_OK, "summary": "链接有效", "file_count": file_count}

        if share_status:
            return {"state": STATE_BAD, "summary": f"分享状态异常: {share_status}"}

        if err_msg:
            return {"state": STATE_BAD, "summary": err_msg}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认迅雷分享状态"}
