# src/services/link_checker/detectors/guangya.py
"""光鸭云盘免登录测活探测器（按 2026-11 现行接口重写）。

原实现走的是旧的 GET /drive/v1/share（query 传 share_id / pass_code），
该接口已下线，统一返回 410 {"code":128,"msg":"路径不允许访问"}。
探测器把 410 的 msg 原样当成"失效原因"，于是所有光鸭链接在
「转存前检测」阶段就被判成失效，转存流程根本走不到客户端——后台日志表现为
"【光鸭云盘】转存前检测到链接已失效/违规，终止转存"。

现行只需要一个免登录（不带 Authorization）就能调的接口：

    POST https://api.guangyapan.com/userres/v1/get_share_summary
    body: {"shareId": "<数字id>_<userId>"}

返回判定要点（已逐个实测）：
    正常      -> {"msg":"success","data":{...,"totalFileNum":13,"title":"...",...}}
    已失效    -> {"code":201,"msg":"分享已失效"}
    分享码错  -> {"code":200,"msg":"分享链接错误"}   ← 注意这里 code=200 是"错误"
    分享码缺  -> {"code":112,"msg":"参数错误"}

因为 code=200 既可能是成功也可能是"分享链接错误"，判定必须以 msg 为准。
另外：无法识别的响应一律返回"不确定"，不要判死——判死会直接掐断转存，
宁可让后面的客户端去撞一次真实错误。
"""

import logging
import re
from typing import Any, Dict, Optional

import requests

from ..base import BaseDetector, contains_any
from ..constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN

logger = logging.getLogger(__name__)

SUMMARY_API = "https://api.guangyapan.com/userres/v1/get_share_summary"

# 判定"已失效"的关键词
_BAD_WORDS = [
    "分享已失效", "失效", "链接错误", "不存在", "已删除", "违规", "过期",
    "not_found", "expired", "deleted",
]
# 判定"需要提取码"的关键词
_LOCKED_WORDS = ["提取码", "密码", "需要验证", "passcode", "password", "sharecode"]


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
        match = re.search(r"guangyapan\.com/s/([a-zA-Z0-9_-]+)", url or "", re.IGNORECASE)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析光鸭云盘分享码"}

        share_id = match.group(1)
        # 光鸭的 shareId 形如 "1943272397459599427_aoSIUadVYn9fXzbj"，
        # 缺了下划线后的 userId 段，接口只会回"参数错误"，判死没有意义。
        if "_" not in share_id:
            return {"state": STATE_UNCERTAIN, "summary": "分享码不完整，缺少用户标识段"}

        pwd = password
        if not pwd:
            pwd_match = re.search(
                r"(?:[?&](?:pwd|code|shareCode)=|提取码[:：=\s]*|密码[:：=\s]*)([a-zA-Z0-9]{4,8})",
                url or "",
                re.IGNORECASE,
            )
            if pwd_match:
                pwd = pwd_match.group(1)

        payload: Dict[str, Any] = {"shareId": share_id}
        if pwd:
            payload["code"] = pwd

        headers = self.get_headers({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://www.guangyapan.com",
            "Referer": "https://www.guangyapan.com/",
        })

        sess = session or requests.Session()
        try:
            resp = sess.post(SUMMARY_API, json=payload, headers=headers, timeout=10)
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"光鸭云盘请求失败: {e}"}

        if resp.status_code != 200:
            # 接口若再次迁移（例如又变 410），也只当"不确定"，绝不判死
            logger.warning(f"光鸭云盘测活接口异常 [{resp.status_code}]: {resp.text[:200]}")
            return {
                "state": STATE_UNCERTAIN,
                "summary": f"光鸭云盘测活接口返回 HTTP {resp.status_code}",
            }

        try:
            data = resp.json()
        except Exception:
            return {"state": STATE_UNCERTAIN, "summary": "光鸭云盘测活返回非 JSON"}

        msg = str(data.get("msg") or data.get("message") or "").strip()
        body = data.get("data") if isinstance(data.get("data"), dict) else {}

        # 成功：以 msg == success 且带 data 为准（code 字段不可靠）
        if msg == "success" or (body and not msg):
            total = body.get("totalFileNum")
            try:
                total_int = int(total) if total is not None else None
            except (TypeError, ValueError):
                total_int = None
            if total_int is not None and total_int <= 0:
                return {"state": STATE_BAD, "summary": "分享文件列表为空", "file_count": 0}
            return {
                "state": STATE_OK,
                "summary": "链接有效",
                "file_count": total_int,
                "title": body.get("title"),
            }

        if contains_any(msg, _LOCKED_WORDS):
            return {"state": STATE_LOCKED, "summary": msg or "需要提取码"}

        if contains_any(msg, _BAD_WORDS):
            return {"state": STATE_BAD, "summary": msg}

        # 参数错误/限流/未知错误：不判死，交给客户端去撞真实错误
        return {"state": STATE_UNCERTAIN, "summary": msg or "光鸭云盘分享无法确认"}
