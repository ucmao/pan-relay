import concurrent.futures
import json
import logging
import random
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

import requests

from src.configs.app_config import user_agents
from src.utils.netdisk_utils import (
    extract_canonical_resource_key,
    extract_password_from_url,
    match_netdisk_link,
)

logger = logging.getLogger(__name__)

# --- 状态常量 ---
STATE_OK = "ok"                      # 链接正常有效
STATE_BAD = "bad"                    # 链接失效、过期、违规、已删除
STATE_LOCKED = "locked"              # 链接需要提取码/访问码且未提供或错误
STATE_UNCERTAIN = "uncertain"        # 网络波动、触发风控验证码、状态无法断定
STATE_UNSUPPORTED = "unsupported"    # 暂不支持免登录检测的平台

# 缓存 TTL（秒）
CACHE_TTL_OK = 1800      # 有效链接缓存 30 分钟
CACHE_TTL_BAD = 600      # 失效链接缓存 10 分钟
CACHE_TTL_OTHER = 300    # 其他状态缓存 5 分钟


def _contains_any(text: str, targets: List[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(t.lower() in lower for t in targets)


class LinkChecker:
    """
    网盘免登录健康检测服务（单例模式，具备 SingleFlight 并发防击穿与内存缓存）
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._cache_lock = threading.Lock()
        self._inflight: Dict[str, threading.Event] = {}
        self._inflight_results: Dict[str, Dict[str, Any]] = {}
        self._inflight_lock = threading.Lock()
        self._session = requests.Session()

    def _get_headers(self, custom: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        ua = random.choice(user_agents) if user_agents else (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        headers = {"User-Agent": ua}
        if custom:
            headers.update(custom)
        return headers

    # --- 各网盘免登录探测实现 ---

    def _check_quark(self, url: str, password: Optional[str]) -> Dict[str, Any]:
        match = re.search(r"pan\.quark\.cn/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法提取夸克分享ID"}
        pwd_id = match.group(1)
        pwd = password or extract_password_from_url(url) or ""

        # 1. 获取 sharepage token
        token_api = "https://drive-h.quark.cn/1/clouddrive/share/sharepage/token"
        headers = self._get_headers({
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
            resp = self._session.post(token_api, json=payload, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"夸克Token请求失败: {e}"}

        code = data.get("code", -1)
        msg = str(data.get("message") or "")

        if code == 41008 or _contains_any(msg, ["提取码", "密码", "passcode"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        if code in (41004, 41010, 41011) or _contains_any(msg, ["不存在", "失效", "违规", "过期", "取消"]):
            return {"state": STATE_BAD, "summary": msg or "分享链接已失效或不存在"}
        if code != 0:
            return {"state": STATE_UNCERTAIN, "summary": msg or f"夸克返回异常代码 {code}"}

        stoken = (data.get("data") or {}).get("stoken")
        if not stoken:
            return {"state": STATE_UNCERTAIN, "summary": "未返回夸克访问令牌"}

        # 2. 查询分享详情确认文件列表与违规状态
        detail_api = f"https://drive-pc.quark.cn/1/clouddrive/share/sharepage/detail?pwd_id={quote(pwd_id)}&stoken={quote(stoken)}&ver=2&pr=ucpro"
        try:
            resp_detail = self._session.get(detail_api, headers=headers, timeout=8)
            data_detail = resp_detail.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"夸克详情请求失败: {e}"}

        detail_code = data_detail.get("code", -1)
        if detail_code != 0:
            dmsg = str(data_detail.get("message") or "无法确认链接状态")
            if _contains_any(dmsg, ["不存在", "失效", "违规", "过期", "取消"]):
                return {"state": STATE_BAD, "summary": dmsg}
            if _contains_any(dmsg, ["提取码", "密码"]):
                return {"state": STATE_LOCKED, "summary": dmsg}
            return {"state": STATE_UNCERTAIN, "summary": dmsg}

        share_info = (data_detail.get("data") or {}).get("share") or {}
        file_list = (data_detail.get("data") or {}).get("list") or []
        share_status = share_info.get("status", 0)
        partial_violation = bool(share_info.get("partial_violation", False))
        is_expire = bool((data_detail.get("data") or {}).get("is_expire", False))

        if not file_list:
            if is_expire:
                return {"state": STATE_BAD, "summary": "分享链接已过期"}
            if share_status > 1 or partial_violation:
                return {"state": STATE_BAD, "summary": "分享链接违规已失效"}
            return {"state": STATE_BAD, "summary": "分享链接无效：文件列表为空"}

        if share_status == 3 and partial_violation:
            return {"state": STATE_BAD, "summary": "分享链接因违规已失效"}
        if share_status > 1:
            return {"state": STATE_BAD, "summary": f"分享链接已失效(status={share_status})"}

        return {"state": STATE_OK, "summary": "链接有效"}

    def _check_aliyun(self, url: str, password: Optional[str]) -> Dict[str, Any]:
        match = re.search(r"(?:alipan\.com|aliyundrive\.com|drive\.aliyun\.com)/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析阿里云盘分享ID"}
        share_id = match.group(1)

        api = f"https://api.aliyundrive.com/adrive/v3/share_link/get_share_by_anonymous?share_id={quote(share_id)}"
        headers = self._get_headers({
            "Content-Type": "application/json",
            "Origin": "https://www.alipan.com",
            "Referer": "https://www.alipan.com/",
            "x-canary": "client=web,app=share,version=v2.3.1",
        })
        payload = {"share_id": share_id}

        try:
            resp = self._session.post(api, json=payload, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"阿里云盘请求失败: {e}"}

        code = str(data.get("code") or "").lower()
        msg = str(data.get("message") or "")
        file_count = data.get("file_count")
        share_name = data.get("share_name") or data.get("share_title")
        share_status = str(data.get("share_status") or "").lower()

        if code:
            if _contains_any(code, ["notfound", "cancelled", "canceled", "forbidden", "expired", "sharelink"]):
                return {"state": STATE_BAD, "summary": msg or "分享链接已失效或取消"}
            if _contains_any(code, ["exceed", "frequency", "limit"]):
                return {"state": STATE_UNCERTAIN, "summary": "触发阿里云盘访问频次限制"}
            return {"state": STATE_UNCERTAIN, "summary": msg or code}

        if file_count == 0 and not share_name:
            return {"state": STATE_BAD, "summary": "分享内容为空(file_count=0)"}

        if share_status and share_status not in ("enabled", "normal"):
            if _contains_any(share_status, ["forbidden", "cancel", "expired", "illegal", "invalid", "disabled"]):
                return {"state": STATE_BAD, "summary": msg or "分享状态异常/已失效"}

        if resp.status_code == 200 and (share_name or (file_count is not None and file_count > 0)):
            return {"state": STATE_OK, "summary": "链接有效"}

        return {"state": STATE_UNCERTAIN, "summary": msg or "无法断定链接状态"}

    def _check_baidu(self, url: str, password: Optional[str]) -> Dict[str, Any]:
        match = re.search(r"(?:pan\.baidu\.com|bdpan\.com|baiduyun\.com)/s/1?([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析百度网盘分享短链"}
        surl = match.group(1)
        pwd = password or extract_password_from_url(url) or ""

        headers = self._get_headers({
            "Referer": url,
            "Accept": "application/json, text/plain, */*",
        })

        # 1. 若提供了提取码，先进行 verify 校验
        randsk = ""
        if pwd:
            verify_url = f"https://pan.baidu.com/share/verify?surl={quote(surl)}&pwd={quote(pwd)}"
            try:
                vresp = self._session.post(
                    verify_url,
                    data={"pwd": pwd, "vcode": "", "vcode_str": ""},
                    headers=self._get_headers({"Referer": url, "Content-Type": "application/x-www-form-urlencoded"}),
                    timeout=8,
                )
                vdata = vresp.json()
                errno = vdata.get("errno", -1)
                if errno == 0:
                    randsk = vdata.get("randsk", "")
                elif errno in (-9, -12):
                    return {"state": STATE_LOCKED, "summary": "提取码错误或失效"}
                else:
                    return {"state": STATE_UNCERTAIN, "summary": vdata.get("errmsg", "提取码校验失败")}
            except Exception as e:
                logger.warning(f"百度提取码验证接口异常: {e}")

        # 2. 调用 share/list 接口探测
        list_url = f"https://pan.baidu.com/share/list?web=1&page=1&num=20&order=time&desc=1&showempty=0&shorturl={quote(surl)}&root=1&clienttype=0"
        if randsk:
            headers["Cookie"] = f"BDCLND={randsk}"

        try:
            lresp = self._session.get(list_url, headers=headers, timeout=8)
            ldata = lresp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"百度分享查询失败: {e}"}

        errno = ldata.get("errno", -1)
        errmsg = str(ldata.get("errmsg") or "")

        if errno == 0:
            file_list = ldata.get("list") or []
            if len(file_list) > 0:
                return {"state": STATE_OK, "summary": "链接有效"}
            return {"state": STATE_BAD, "summary": "分享链接无文件或已失效"}
        elif errno in (-9, -12):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        elif errno in (-7, 105, 115, 117, 145):
            return {"state": STATE_BAD, "summary": errmsg or "分享链接已失效或违规已删除"}
        else:
            return {"state": STATE_UNCERTAIN, "summary": errmsg or f"百度错误代码 {errno}"}

    def _check_uc(self, url: str, password: Optional[str]) -> Dict[str, Any]:
        match = re.search(r"(?:drive\.uc\.cn|pan\.uc\.cn)/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析UC网盘分享码"}

        headers = self._get_headers({
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
        })
        try:
            resp = self._session.get(url, headers=headers, timeout=8, allow_redirects=True)
            text = resp.text
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"UC请求失败: {e}"}

        if resp.status_code == 404:
            return {"state": STATE_BAD, "summary": "链接不存在(404)"}

        if _contains_any(text, ["失效", "不存在", "违规", "删除", "已过期", "被取消"]):
            return {"state": STATE_BAD, "summary": "链接已失效或删除"}
        if _contains_any(text, ["提取码", "访问码", "请输入密码"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        if _contains_any(text, ["文件", "分享", "drive.uc.cn", "夸克", "uc"]):
            return {"state": STATE_OK, "summary": "链接有效"}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认UC链接状态"}

    def _check_123(self, url: str, password: Optional[str]) -> Dict[str, Any]:
        match = re.search(r"(?:123pan\.com|123\d{3}\.(?:com|cn))/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析123云盘分享码"}
        share_key = match.group(1)

        api = f"https://www.123pan.com/api/share/info?shareKey={quote(share_key)}"
        headers = self._get_headers()

        try:
            resp = self._session.get(api, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"123云盘请求失败: {e}"}

        code = data.get("code", -1)
        has_pwd = bool((data.get("data") or {}).get("HasPwd", False))
        msg = str(data.get("message") or "")

        if code == 0:
            return {"state": STATE_OK, "summary": "链接有效"}
        if has_pwd:
            return {"state": STATE_LOCKED, "summary": "需要提取码"}
        if msg:
            return {"state": STATE_BAD, "summary": msg}
        return {"state": STATE_BAD, "summary": "链接已失效"}

    def _check_xunlei(self, url: str, password: Optional[str]) -> Dict[str, Any]:
        match = re.search(r"pan\.xunlei\.com/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析迅雷网盘分享ID"}
        share_id = match.group(1)
        pwd = password or extract_password_from_url(url) or ""

        api = f"https://api-pan.xunlei.com/drive/v1/share?share_id={quote(share_id)}&pass_code={quote(pwd)}&limit=20"
        headers = self._get_headers({
            "Content-Type": "application/json",
            "Origin": "https://pan.xunlei.com",
            "Referer": "https://pan.xunlei.com/",
            "x-client-id": "ZUBzD9J_XPXfn7f7",
            "x-device-id": "5505bd0cab8c9469b98e5891d9fb3e0d",
        })

        try:
            resp = self._session.get(api, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"迅雷网盘请求失败: {e}"}

        if resp.status_code in (404, 403):
            return {"state": STATE_BAD, "summary": "链接失效或不存在"}

        share_status = str(data.get("share_status") or "")
        err_code = data.get("error_code")
        err_msg = str(data.get("error_description") or data.get("error") or "")

        if share_status == "OK" or data.get("file_count", 0) > 0 or data.get("share_name"):
            return {"state": STATE_OK, "summary": "链接有效"}

        if _contains_any(err_msg, ["pass_code", "提取码", "密码"]):
            return {"state": STATE_LOCKED, "summary": "需要提取码"}

        if share_status:
            return {"state": STATE_BAD, "summary": f"分享状态异常: {share_status}"}

        if err_msg:
            return {"state": STATE_BAD, "summary": err_msg}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认迅雷分享状态"}

    def _check_tianyi(self, url: str, password: Optional[str]) -> Dict[str, Any]:
        match = re.search(r"cloud\.189\.cn/(?:t/|web/share\?code=)([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析天翼云盘分享码"}
        share_code = match.group(1)
        pwd = password or extract_password_from_url(url) or ""

        share_param = share_code if not pwd else f"{share_code}（访问码：{pwd}）"
        api = f"https://cloud.189.cn/api/open/share/getShareInfoByCodeV2.action?shareCode={quote(share_param)}&noCache={time.time()}"
        headers = self._get_headers({
            "Referer": url,
            "sign-type": "1",
        })

        try:
            resp = self._session.get(api, headers=headers, timeout=8)
            text = resp.text
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"天翼云盘请求失败: {e}"}

        if "<shareVO>" in text or "<shareId>" in text or "<fileName>" in text:
            return {"state": STATE_OK, "summary": "链接有效"}
        if _contains_any(text, ["needaccesscode", "erroraccesscode", "访问码", "提取码", "密码"]):
            return {"state": STATE_LOCKED, "summary": "需要访问码/提取码"}
        if _contains_any(text, ["sharenotfound", "filenotfound", "shareexpirederror", "不存在", "失效", "取消", "过期"]):
            return {"state": STATE_BAD, "summary": "天翼链接已失效或不存在"}

        return {"state": STATE_UNCERTAIN, "summary": "无法确认天翼云盘状态"}

    def _check_115(self, url: str, password: Optional[str]) -> Dict[str, Any]:
        match = re.search(r"(?:115\.com|115pan\.com|115cdn\.com|anxia\.com)/s/([a-zA-Z0-9_-]+)", url)
        if not match:
            return {"state": STATE_UNCERTAIN, "summary": "无法解析115网盘分享码"}
        share_code = match.group(1)
        pwd = password or extract_password_from_url(url)

        if not pwd:
            return {"state": STATE_LOCKED, "summary": "115网盘需要提取码"}

        api = f"https://115cdn.com/webapi/share/snap?share_code={quote(share_code)}&receive_code={quote(pwd)}&offset=0&limit=20"
        headers = self._get_headers({
            "Referer": f"https://115cdn.com/s/{share_code}?password={pwd}",
            "X-Requested-With": "XMLHttpRequest",
        })

        try:
            resp = self._session.get(api, headers=headers, timeout=8)
            data = resp.json()
        except Exception as e:
            return {"state": STATE_UNCERTAIN, "summary": f"115网盘请求失败: {e}"}

        state = bool(data.get("state", False))
        error_msg = str(data.get("error") or "")
        count = (data.get("data") or {}).get("count", 0)

        if state and count > 0:
            return {"state": STATE_OK, "summary": "链接有效"}
        if error_msg:
            return {"state": STATE_BAD, "summary": error_msg}

        return {"state": STATE_BAD, "summary": "115分享链接已失效"}

    # --- 统一入口与缓存分发 ---

    def check_link(
        self,
        url: str,
        password: Optional[str] = None,
        disk_type: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        单条网盘链接检测。支持缓存复用与 SingleFlight 并发防击穿。
        """
        url = str(url or "").strip()
        if not url:
            return {"state": STATE_BAD, "summary": "链接为空", "url": url, "cache_hit": False}

        canonical_key = extract_canonical_resource_key(url) or url
        now = time.time()

        # 1. 检查缓存
        if not force_refresh:
            with self._cache_lock:
                cached_entry = self._cache.get(canonical_key)
                if cached_entry:
                    res, expire_time = cached_entry
                    if now < expire_time:
                        copy_res = dict(res)
                        copy_res["cache_hit"] = True
                        return copy_res

        # 2. SingleFlight 防击穿：如果相同 canonical_key 正在检测中，等待其完成
        is_leader = False
        event = None
        with self._inflight_lock:
            if canonical_key in self._inflight:
                event = self._inflight[canonical_key]
            else:
                event = threading.Event()
                self._inflight[canonical_key] = event
                is_leader = True

        if not is_leader:
            # 伴随者等待领头请求完成
            event.wait(timeout=15)
            with self._inflight_lock:
                result = self._inflight_results.get(canonical_key)
            if result:
                copy_res = dict(result)
                copy_res["cache_hit"] = True
                return copy_res

        # 3. 领头者执行真实网络探测
        try:
            detected_type = disk_type or match_netdisk_link(url)
            norm_type = detected_type.replace("网盘", "").replace("云盘", "").strip().lower()

            if "quark" in norm_type or "夸克" in norm_type:
                res = self._check_quark(url, password)
            elif "aliyun" in norm_type or "阿里" in norm_type:
                res = self._check_aliyun(url, password)
            elif "baidu" in norm_type or "百度" in norm_type:
                res = self._check_baidu(url, password)
            elif "uc" in norm_type:
                res = self._check_uc(url, password)
            elif "123" in norm_type:
                res = self._check_123(url, password)
            elif "xunlei" in norm_type or "迅雷" in norm_type:
                res = self._check_xunlei(url, password)
            elif "tianyi" in norm_type or "天翼" in norm_type:
                res = self._check_tianyi(url, password)
            elif "115" in norm_type:
                res = self._check_115(url, password)
            else:
                res = {"state": STATE_UNSUPPORTED, "summary": f"暂不支持检测 {detected_type}"}

            res["url"] = url
            res["disk_type"] = detected_type
            res["canonical_key"] = canonical_key
            res["checked_at"] = int(now)
            res["cache_hit"] = False

            # 计算缓存 TTL
            ttl = CACHE_TTL_OK if res["state"] == STATE_OK else (
                CACHE_TTL_BAD if res["state"] == STATE_BAD else CACHE_TTL_OTHER
            )
            with self._cache_lock:
                self._cache[canonical_key] = (res, now + ttl)

            with self._inflight_lock:
                self._inflight_results[canonical_key] = res

            return res

        finally:
            with self._inflight_lock:
                self._inflight.pop(canonical_key, None)
                self._inflight_results.pop(canonical_key, None)
            event.set()

    def check_links_batch(
        self,
        items: List[Dict[str, Any]],
        max_workers: int = 6,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        批量并发检测网盘链接。
        """
        if not items:
            return []

        results = [None] * len(items)

        def _do_one(index: int, item: Dict[str, Any]):
            url = item.get("url") or item.get("share_link") or ""
            pwd = item.get("password") or item.get("pwd")
            dtype = item.get("disk_type") or item.get("cloud_name")
            return index, self.check_link(url, password=pwd, disk_type=dtype, force_refresh=force_refresh)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_do_one, i, item) for i, item in enumerate(items)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, res = future.result()
                    results[idx] = res
                except Exception as e:
                    logger.error(f"批量检测异常: {e}")

        return [r for r in results if r is not None]


# 全局单例便捷访问
_global_checker = LinkChecker()


def check_link(
    url: str,
    password: Optional[str] = None,
    disk_type: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    return _global_checker.check_link(url, password=password, disk_type=disk_type, force_refresh=force_refresh)


def check_links_batch(
    items: List[Dict[str, Any]],
    max_workers: int = 6,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    return _global_checker.check_links_batch(items, max_workers=max_workers, force_refresh=force_refresh)
