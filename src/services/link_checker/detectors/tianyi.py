# src/services/link_checker/detectors/tianyi.py

import logging
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from src.utils.netdisk_utils import extract_password_from_url
from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class TianyiDetector(BaseDetector):
    platform_name = "天翼云盘"
    domain_patterns = ["cloud.189.cn", "189.cn"]
    supported_keywords = ["tianyi", "189", "天翼"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(r"cloud\.189\.cn/(?:t/|web/share\?code=)([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析天翼云盘分享码"}
        share_code = match.group(1)
        pwd = password or extract_password_from_url(url) or ""

        share_param = share_code if not pwd else f"{share_code}（访问码：{pwd}）"
        api = f"https://cloud.189.cn/api/open/share/getShareInfoByCodeV2.action?shareCode={quote(share_param)}&noCache={time.time()}"
        headers = self.get_headers({
            "Referer": url,
            "sign-type": "1",
        })

        sess = session or requests.Session()
        try:
            resp = sess.get(api, headers=headers, timeout=8)
            text = resp.text
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"天翼云盘请求失败: {e}"}

        if "<shareVO>" in text or "<shareId>" in text or "<fileName>" in text:
            return {"state": STATE_OK, "summary": "链接有效"}
        if contains_any(text, ["needaccesscode", "erroraccesscode", "访问码", "提取码", "密码"]):
            return {"state": STATE_LOCKED, "summary": "需要访问码/提取码"}
        if contains_any(text, ["sharenotfound", "filenotfound", "shareexpirederror", "不存在", "失效", "取消", "过期"]):
            return {"state": STATE_BAD, "summary": "天翼链接已失效或不存在"}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认天翼云盘状态"}
