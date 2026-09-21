# src/services/link_checker/detectors/aliyun.py

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class AliyunDetector(BaseDetector):
    platform_name = "阿里云盘"
    domain_patterns = ["alipan.com", "aliyundrive.com", "drive.aliyun.com"]
    supported_keywords = ["aliyun", "alipan", "阿里"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(r"(?:alipan\.com|aliyundrive\.com|drive\.aliyun\.com)/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析阿里云盘分享ID"}
        share_id = match.group(1)

        sess = session or requests.Session()
        api = f"https://api.aliyundrive.com/adrive/v3/share_link/get_share_by_anonymous?share_id={quote(share_id)}"
        headers = self.get_headers({
            "Content-Type": "application/json",
            "Origin": "https://www.alipan.com",
            "Referer": "https://www.alipan.com/",
            "x-canary": "client=web,app=share,version=v2.3.1",
        })
        payload = {"share_id": share_id}

        try:
            resp = sess.post(api, json=payload, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"阿里云盘请求失败: {e}"}

        code = str(data.get("code") or "").lower()
        msg = str(data.get("message") or "")
        file_count = data.get("file_count")
        share_name = data.get("share_name") or data.get("share_title")
        share_status = str(data.get("share_status") or "").lower()

        if code:
            if contains_any(code, ["notfound", "cancelled", "canceled", "forbidden", "expired", "sharelink"]):
                return {"state": STATE_BAD, "summary": msg or "分享链接已失效或取消"}
            if contains_any(code, ["exceed", "frequency", "limit"]):
                return {"state": STATE_UNCERTAIN, "summary": "触发阿里云盘访问频次限制"}
            return {"state": STATE_UNCERTAIN, "summary": msg or code}

        # 深入判空：无文件列表或计数为0
        if file_count == 0 and not share_name:
            return {"state": STATE_BAD, "summary": "分享内容为空(file_count=0)", "file_count": 0}

        if share_status and share_status not in ("enabled", "normal"):
            if contains_any(share_status, ["forbidden", "cancel", "expired", "illegal", "invalid", "disabled"]):
                return {"state": STATE_BAD, "summary": msg or "分享状态异常/已失效"}

        if resp.status_code == 200 and (share_name or (file_count is not None and file_count > 0)):
            return {"state": STATE_OK, "summary": "链接有效", "file_count": file_count}

        return {"state": STATE_UNCERTAIN, "summary": msg or "无法断定链接状态"}
