# src/services/link_checker/detectors/wukong.py

import logging
import re
from typing import Any, Dict, Optional

import requests

from ..base import BaseDetector
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class WukongDetector(BaseDetector):
    platform_name = "悟空网盘"
    domain_patterns = ["pan.wkbrowser.com", "wkbrowser.com"]
    supported_keywords = ["wukong", "悟空", "悟空网盘", "悟空浏览器"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(
            r"(?:pan\.wkbrowser\.com|wkbrowser\.com)/(?:s/|share/)?([a-zA-Z0-9_-]+)",
            url,
            re.IGNORECASE,
        )
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析悟空网盘分享码"}

        share_id = match.group(1)
        pwd = password
        if not pwd:
            pwd_match = re.search(
                r"(?:[?&]pwd=|提取码[:：=\s]*|密码[:：=\s]*)([a-zA-Z0-9]{4,6})",
                url,
                re.IGNORECASE,
            )
            if pwd_match:
                pwd = pwd_match.group(1)

        sess = session or requests.Session()
        api = "https://pan.wkbrowser.com/api/v1/share/info"
        headers = self.get_headers({
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://pan.wkbrowser.com",
            "Referer": "https://pan.wkbrowser.com/",
        })

        try:
            resp = sess.get(
                api,
                params={"share_id": share_id, "pwd": pwd or ""},
                headers=headers,
                timeout=8,
            )
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"悟空网盘请求失败: {e}"}

        code = data.get("code")
        msg = str(data.get("message") or data.get("msg") or "")
        data_obj = data.get("data") or data

        if code in (0, 200, None) and isinstance(data_obj, dict):
            files = data_obj.get("files") or data_obj.get("file_list") or []
            file_count = len(files) if isinstance(files, list) else None
            share_title = data_obj.get("title") or data_obj.get("name")

            if file_count == 0 and not share_title:
                return {"state": STATE_BAD, "summary": "分享文件列表为空", "file_count": 0}

            return {
                "state": STATE_OK,
                "summary": "链接有效",
                "file_count": file_count,
            }

        # 错误与状态判断
        if any(k in msg for k in ["密码", "提取码", "口令", "access code", "passcode"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码或密码错误"}

        if any(k in msg for k in ["不存在", "失效", "违规", "删除", "过期", "取消"]):
            return {"state": STATE_BAD, "summary": msg or "悟空网盘分享已失效"}

        if msg:
            return {"state": STATE_BAD, "summary": msg}

        return {"state": STATE_BAD, "summary": "悟空网盘分享失效或不可用"}
