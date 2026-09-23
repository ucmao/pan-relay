# src/services/link_checker/detectors/unicom.py

import logging
import re
from typing import Any, Dict, Optional

import requests

from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class UnicomDetector(BaseDetector):
    platform_name = "联通云盘"
    domain_patterns = ["pan.wo.cn", "wo.cn"]
    supported_keywords = ["unicom", "联通", "联通云盘", "沃云盘", "wo"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(
            r"pan\.wo\.cn/(?:s/|fb/|web/share/)?([a-zA-Z0-9_-]+)",
            url,
        )
        if not match and not ("pan.wo.cn" in url or "wo.cn" in url):
            return {"state": STATE_UNCERTAIN, "summary": "无法解析联通云盘链接特征"}

        sess = session or requests.Session()
        headers = self.get_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": url,
        })

        try:
            resp = sess.get(url, headers=headers, timeout=8, allow_redirects=True)
            text = resp.text
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"联通云盘请求失败: {e}"}

        if resp.status_code == 404:
            return {"state": STATE_BAD, "summary": "链接不存在(404)"}

        if contains_any(text, ["失效", "不存在", "违规", "已取消", "已被删除", "已过期", "分享已结束", "链接不存在", "已被清理"]):
            return {"state": STATE_BAD, "summary": "联通云盘链接已失效或删除"}
        if contains_any(text, ["提取码", "访问密码", "提取密码", "请输入密码", "请输入提取码"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        if contains_any(text, ["文件", "联通云盘", "沃云盘", "pan.wo.cn", "下载", "转存"]):
            return {"state": STATE_OK, "summary": "链接有效"}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认联通云盘链接状态"}
