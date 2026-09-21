# src/services/link_checker/detectors/pan115.py

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from src.utils.netdisk_utils import extract_password_from_url
from ..base import BaseDetector
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class Pan115Detector(BaseDetector):
    platform_name = "115网盘"
    domain_patterns = ["115.com", "115pan.com", "115cdn.com", "anxia.com"]
    supported_keywords = ["115", "115网盘"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(r"(?:115\.com|115pan\.com|115cdn\.com|anxia\.com)/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析115网盘分享码"}
        share_code = match.group(1)
        pwd = password or extract_password_from_url(url)

        if not pwd:
            return {"state": STATE_LOCKED, "summary": "115网盘需要提取码"}

        api = f"https://115cdn.com/webapi/share/snap?share_code={quote(share_code)}&receive_code={quote(pwd)}&offset=0&limit=20"
        headers = self.get_headers({
            "Referer": f"https://115cdn.com/s/{share_code}?password={pwd}",
            "X-Requested-With": "XMLHttpRequest",
        })

        sess = session or requests.Session()
        try:
            resp = sess.get(api, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"115网盘请求失败: {e}"}

        state = bool(data.get("state", False))
        error_msg = str(data.get("error") or "")
        count = (data.get("data") or {}).get("count", 0)

        if state and count > 0:
            return {"state": STATE_OK, "summary": "链接有效", "file_count": count}
        if state and count == 0:
            return {"state": STATE_BAD, "summary": "115分享内容为空", "file_count": 0}
        if error_msg:
            return {"state": STATE_BAD, "summary": error_msg}

        return {"state": STATE_BAD, "summary": "115分享链接已失效"}
