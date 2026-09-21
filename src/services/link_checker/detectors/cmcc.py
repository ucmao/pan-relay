# src/services/link_checker/detectors/cmcc.py

import logging
import re
from typing import Any, Dict, Optional

import requests

from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class CMCCDetector(BaseDetector):
    platform_name = "中国移动云盘"
    domain_patterns = ["139.com", "10086.cn"]
    supported_keywords = ["cmcc", "移动云盘", "和彩云"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(
            r"(?:yun\.139\.com/shareweb/#/w/i/|caiyun\.139\.com/w/i/|caiyun\.139\.com/m/i\?|pan\.10086\.cn/s/)([a-zA-Z0-9_-]+)",
            url,
        )
        if not match:
            # 宽泛匹配 139/10086 域名
            if not ("139.com" in url or "10086.cn" in url):
                return {"state": STATE_UNCERTAIN, "summary": "无法解析中国移动云盘分享码"}

        sess = session or requests.Session()
        headers = self.get_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": url,
        })

        try:
            resp = sess.get(url, headers=headers, timeout=8, allow_redirects=True)
            text = resp.text
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"移动云盘请求失败: {e}"}

        if resp.status_code == 404:
            return {"state": STATE_BAD, "summary": "链接不存在(404)"}

        if contains_any(text, ["失效", "不存在", "违规", "已取消", "已被删除", "已过期", "链接不存在"]):
            return {"state": STATE_BAD, "summary": "移动云盘链接已失效或删除"}
        if contains_any(text, ["提取码", "访问密码", "提取密码", "请输入密码"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        if contains_any(text, ["文件", "移动云盘", "139.com", "caiyun", "个人云"]):
            return {"state": STATE_OK, "summary": "链接有效"}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认移动云盘链接状态"}
