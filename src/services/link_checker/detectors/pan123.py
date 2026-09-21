# src/services/link_checker/detectors/pan123.py

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from ..base import BaseDetector
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class Pan123Detector(BaseDetector):
    platform_name = "123云盘"
    domain_patterns = ["123pan.com", "123684.com", "123pan.cn"]
    supported_keywords = ["123pan", "123云盘"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(r"(?:123pan\.com|123\d{3}\.(?:com|cn))/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析123云盘分享码"}
        share_key = match.group(1)

        sess = session or requests.Session()
        api = f"https://www.123pan.com/api/share/info?shareKey={quote(share_key)}"
        headers = self.get_headers()

        try:
            resp = sess.get(api, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"123云盘请求失败: {e}"}

        code = data.get("code", -1)
        data_obj = data.get("data") or {}
        has_pwd = bool(data_obj.get("HasPwd", False))
        msg = str(data.get("message") or "")
        share_name = data_obj.get("ShareName") or data_obj.get("FileCount")

        if code == 0:
            file_count = data_obj.get("FileCount")
            if file_count is not None and file_count == 0 and not share_name:
                return {"state": STATE_BAD, "summary": "分享文件列表为空", "file_count": 0}
            return {"state": STATE_OK, "summary": "链接有效", "file_count": file_count}
        if has_pwd:
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        if msg:
            return {"state": STATE_BAD, "summary": msg}
        return {"state": STATE_BAD, "summary": "链接已失效"}
