# src/services/link_checker/detectors/baidu.py

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from src.utils.netdisk_utils import extract_password_from_url
from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)


class BaiduDetector(BaseDetector):
    platform_name = "百度网盘"
    domain_patterns = ["pan.baidu.com", "bdpan.com", "baiduyun.com"]
    supported_keywords = ["baidu", "百度"]

    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        match = re.search(r"(?:pan\.baidu\.com|bdpan\.com|baiduyun\.com)/s/1?([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析百度网盘分享短链"}
        surl = match.group(1)
        pwd = password or extract_password_from_url(url) or ""

        sess = session or requests.Session()
        headers = self.get_headers({
            "Referer": url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "identity",
        })

        # 0. 先快速查验 HTML 页面 title 与关键错误，排除已删除/侵权/封禁死链
        try:
            page_resp = sess.get(f"https://pan.baidu.com/s/1{surl}", headers=headers, timeout=6, allow_redirects=True)
            page_text = page_resp.text
            if "链接不存在" in page_text or "涉及侵权" in page_text or "无法访问" in page_text or "已被取消" in page_text or "已失效" in page_text or "分享文件不存在" in page_text:
                if "涉及侵权" in page_text or "无法访问" in page_text:
                    return {"state": STATE_BAD, "summary": "资源因涉嫌侵权或低俗违规无法访问"}
                return {"state": STATE_BAD, "summary": "百度分享链接不存在或已失效"}
        except Exception as e:
            logger.debug(f"百度页面 HTML 预检异常: {e}")

        # 1. 若提供了提取码，先进行 verify 校验
        randsk = ""
        if pwd:
            verify_url = f"https://pan.baidu.com/share/verify?surl={quote(surl)}&pwd={quote(pwd)}"
            try:
                vresp = sess.post(
                    verify_url,
                    data={"pwd": pwd, "vcode": "", "vcode_str": ""},
                    headers=self.get_headers({"Referer": url, "Content-Type": "application/x-www-form-urlencoded"}),
                    timeout=8,
                )
                vdata = vresp.json()
                errno = vdata.get("errno", -1)
                if errno == 0:
                    randsk = vdata.get("randsk", "")
                elif errno in (2, -21, 105, 110, 115):
                    return {"state": STATE_BAD, "summary": "百度分享链接已被删除或取消"}
                elif errno in (-9, -12):
                    return {"state": STATE_LOCKED, "summary": "提取码错误或失效"}
                else:
                    return {"state": STATE_UNCERTAIN, "summary": vdata.get("errmsg", "提取码校验失败")}
            except Exception as e:
                logger.warning(f"百度提取码验证接口异常: {e}")

        # 2. 调用 share/list 接口探测
        list_url = (
            f"https://pan.baidu.com/share/list?web=1&page=1&num=20&order=time&desc=1"
            f"&showempty=0&shorturl={quote(surl)}&root=1&clienttype=0"
        )
        if randsk:
            headers["Cookie"] = f"BDCLND={randsk}"

        try:
            lresp = sess.get(list_url, headers=headers, timeout=8)
            ldata = lresp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"百度分享查询失败: {e}"}

        errno = ldata.get("errno", -1)
        errmsg = str(ldata.get("errmsg") or "")

        if errno == 0:
            file_list = ldata.get("list") or []
            if len(file_list) > 0:
                return {"state": STATE_OK, "summary": "链接有效", "file_count": len(file_list)}
            return {"state": STATE_BAD, "summary": "分享链接无文件或已失效", "file_count": 0}
        if errno in (-9, -12):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        return {"state": STATE_BAD, "summary": errmsg or f"百度分享链接已失效或受限({errno})"}
