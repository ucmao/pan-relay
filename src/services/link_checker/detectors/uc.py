# src/services/link_checker/detectors/uc.py

import logging
import re
from typing import Any, Dict, Optional

import requests

from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class UCDetector(BaseDetector):
    platform_name = "UC网盘"
    domain_patterns = ["drive.uc.cn", "pan.uc.cn"]
    supported_keywords = ["uc"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(r"(?:drive\.uc\.cn|pan\.uc\.cn)/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析UC网盘分享码"}

        sess = session or requests.Session()
        headers = self.get_headers({
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
        })
        try:
            resp = sess.get(url, headers=headers, timeout=8, allow_redirects=True)
            text = resp.text
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"UC请求失败: {e}"}

        if resp.status_code == 404:
            return {"state": STATE_BAD, "summary": "链接不存在(404)"}

        if contains_any(text, ["失效", "不存在", "违规", "删除", "已过期", "被取消"]):
            return {"state": STATE_BAD, "summary": "链接已失效或删除"}
        if contains_any(text, ["提取码", "访问码", "请输入密码"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        if contains_any(text, ["文件", "分享", "drive.uc.cn", "夸克", "uc"]):
            return {"state": STATE_OK, "summary": "链接有效"}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认UC链接状态"}
