# src/services/link_checker/detectors/guangya.py

import logging
import re
from typing import Any, Dict, Optional

import requests

from ..base import BaseDetector
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class GuangyaDetector(BaseDetector):
    platform_name = "光鸭云盘"
    domain_patterns = ["guangyapan.com"]
    supported_keywords = ["guangya", "光鸭", "光鸭云盘"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(
            r"guangyapan\.com/s/([a-zA-Z0-9_-]+)",
            url,
            re.IGNORECASE,
        )
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析光鸭云盘分享码"}

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
        api = "https://api.guangyapan.com/drive/v1/share"
        headers = self.get_headers({
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.guangyapan.com",
            "Referer": "https://www.guangyapan.com/",
        })

        try:
            resp = sess.get(
                api,
                params={"share_id": share_id, "pass_code": pwd or ""},
                headers=headers,
                timeout=8,
            )
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"光鸭云盘请求失败: {e}"}

        code = data.get("code")
        error_code = data.get("error_code")
        msg = str(data.get("message") or data.get("msg") or data.get("error") or "")
        data_obj = data.get("data") or data

        if (code in (0, 200, None)) and not error_code and isinstance(data_obj, dict):
            files = data_obj.get("files") or []
            file_count = len(files) if isinstance(files, list) else None

            if file_count == 0:
                return {"state": STATE_BAD, "summary": "分享文件列表为空", "file_count": 0}

            return {
                "state": STATE_OK,
                "summary": "链接有效",
                "file_count": file_count,
            }

        # 错误与状态判断
        err_str = f"{error_code} {msg}".lower()
        if any(k in err_str for k in ["pass_code", "passcode", "password", "密码", "提取码"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码或密码错误"}

        if any(k in err_str for k in ["not_found", "expired", "deleted", "不存在", "失效", "违规", "删除", "过期"]):
            return {"state": STATE_BAD, "summary": msg or "光鸭云盘分享已失效"}

        if msg:
            return {"state": STATE_BAD, "summary": msg}

        return {"state": STATE_BAD, "summary": "光鸭云盘分享失效或不可用"}
