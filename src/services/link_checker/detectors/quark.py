# src/services/link_checker/detectors/quark.py

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from src.utils.netdisk_utils import extract_password_from_url
from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class QuarkDetector(BaseDetector):
    platform_name = "夸克网盘"
    domain_patterns = ["pan.quark.cn", "quark.cn"]
    supported_keywords = ["quark", "夸克"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(r"pan\.quark\.cn/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法提取夸克分享ID"}
        pwd_id = match.group(1)
        pwd = password or extract_password_from_url(url) or ""

        sess = session or requests.Session()

        # 1. 获取 sharepage token
        token_api = "https://drive-h.quark.cn/1/clouddrive/share/sharepage/token"
        headers = self.get_headers({
            "Content-Type": "application/json",
            "Origin": "https://pan.quark.cn",
            "Referer": "https://pan.quark.cn/",
        })
        payload = {
            "pwd_id": pwd_id,
            "passcode": pwd,
            "support_visit_limit_private_share": True,
        }
        try:
            resp = sess.post(token_api, json=payload, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"夸克Token请求失败: {e}"}

        code = data.get("code", -1)
        msg = str(data.get("message") or "")

        if code == 41008 or contains_any(msg, ["提取码", "密码", "passcode"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        if code in (41004, 41010, 41011) or contains_any(msg, ["不存在", "失效", "违规", "过期", "取消"]):
            return {"state": STATE_BAD, "summary": msg or "分享链接已失效或不存在"}
        if code != 0:
            return {"state": STATE_UNCERTAIN, "summary": msg or f"夸克返回异常代码 {code}"}

        stoken = (data.get("data") or {}).get("stoken")
        if not stoken:
            return {"state": STATE_UNCERTAIN, "summary": "未返回夸克访问令牌"}

        # 2. 查询分享详情确认文件列表与违规状态
        detail_api = f"https://drive-pc.quark.cn/1/clouddrive/share/sharepage/detail?pwd_id={quote(pwd_id)}&stoken={quote(stoken)}&ver=2&pr=ucpro"
        try:
            resp_detail = sess.get(detail_api, headers=headers, timeout=8)
            data_detail = resp_detail.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"夸克详情请求失败: {e}"}

        detail_code = data_detail.get("code", -1)
        if detail_code != 0:
            dmsg = str(data_detail.get("message") or "无法确认链接状态")
            if contains_any(dmsg, ["不存在", "失效", "违规", "过期", "取消"]):
                return {"state": STATE_BAD, "summary": dmsg}
            if contains_any(dmsg, ["提取码", "密码"]):
                return {"state": STATE_LOCKED, "summary": dmsg}
            return {"state": STATE_UNCERTAIN, "summary": dmsg}

        detail_data = data_detail.get("data") or {}
        share_info = detail_data.get("share") or {}
        file_list = detail_data.get("list") or []
        share_status = share_info.get("status", 0)
        partial_violation = bool(share_info.get("partial_violation", False))
        is_expire = bool(detail_data.get("is_expire", False))

        # 深入判空：无文件列表或被清空
        if not file_list:
            if is_expire:
                return {"state": STATE_BAD, "summary": "分享链接已过期", "file_count": 0}
            if share_status > 1 or partial_violation:
                return {"state": STATE_BAD, "summary": "分享链接违规已失效", "file_count": 0}
            return {"state": STATE_BAD, "summary": "分享链接无效：文件列表为空", "file_count": 0}

        if share_status == 3 and partial_violation:
            return {"state": STATE_BAD, "summary": "分享链接因违规已失效", "file_count": len(file_list)}
        if share_status > 1:
            return {"state": STATE_BAD, "summary": f"分享链接已失效(status={share_status})", "file_count": len(file_list)}

        return {"state": STATE_OK, "summary": "链接有效", "file_count": len(file_list)}
