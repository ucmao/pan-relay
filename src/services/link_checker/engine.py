# src/services/link_checker/engine.py

import concurrent.futures
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.utils.proxy_utils import mask_proxy_url, new_proxy_session, normalize_proxy_url
from src.utils.netdisk_utils import (
    extract_canonical_resource_key,
    extract_password_from_url,
    match_netdisk_link,
)
from .constants import (
    CACHE_TTL_BAD,
    CACHE_TTL_OK,
    CACHE_TTL_OTHER,
    STATE_BAD,
    STATE_OK,
    STATE_UNCERTAIN,
    STATE_UNSUPPORTED,
)
from .detectors import ALL_DETECTORS
from .models import CheckResult

logger = logging.getLogger(__name__)


def _get_link_check_proxy() -> str:
    """读取测活代理配置（后台优先，其次 LINK_CHECK_PROXY 环境变量）。"""
    try:
        from src.services.system_config_service import get_link_check_proxy

        return get_link_check_proxy()
    except Exception as exc:
        logger.error(f"读取测活代理配置失败，本次按直连处理: {exc}")
        return ""


class LinkCheckEngine:
    """
    网盘健康检测统一调度引擎
    具备单例模式、SingleFlight 并发防击穿、三级 TTL 内存缓存与批量线程池并发。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        self._detectors = list(ALL_DETECTORS)
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._cache_lock = threading.Lock()
        self._inflight: Dict[str, threading.Event] = {}
        self._inflight_results: Dict[str, Dict[str, Any]] = {}
        self._inflight_lock = threading.Lock()
        self._session = requests.Session()

    def _run_detector(self, detector, url: str, pwd: Optional[str]) -> Dict[str, Any]:
        """
        执行探测器。配置了测活代理时，每次检测新建一个经代理的 Session：
        新连接让住宅代理网关分配新的出口 IP，同一次检测内的多步请求共用该连接。
        代理不可用时不回退直连，探测器会把请求异常归为"不确定"，不会误判为失效。
        """
        raw_proxy = _get_link_check_proxy()
        if not raw_proxy:
            return detector.check(url, password=pwd, session=self._session)

        try:
            proxy_url = normalize_proxy_url(raw_proxy)
        except ValueError as exc:
            logger.error(f"测活代理地址无效（{mask_proxy_url(raw_proxy)}）：{exc}")
            return {"state": STATE_UNCERTAIN, "summary": f"测活代理地址无效：{exc}"}

        with new_proxy_session(proxy_url) as session:
            return detector.check(url, password=pwd, session=session)

    def clear_cache(self):
        """清空内存缓存（便于测试与热重载）"""
        with self._cache_lock:
            self._cache.clear()

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
            res = CheckResult(
                state=STATE_BAD,
                summary="链接为空",
                url=url,
                disk_type="",
                canonical_key="",
                file_count=0,
                checked_at=int(time.time()),
                cache_hit=False,
            )
            return res.to_dict()

        canonical_key = extract_canonical_resource_key(url) or url
        now = time.time()

        # 1. 检查缓存
        if not force_refresh:
            with self._cache_lock:
                cached_entry = self._cache.get(canonical_key)
                if cached_entry:
                    res_dict, expire_time = cached_entry
                    if now < expire_time:
                        copy_res = dict(res_dict)
                        copy_res["cache_hit"] = True
                        return copy_res

        # 2. SingleFlight 防击穿：如果相同 canonical_key 正在检测中，等待其完成并复用
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
            with self._cache_lock:
                cached_entry = self._cache.get(canonical_key)
                if cached_entry:
                    res_dict, _ = cached_entry
                    copy_res = dict(res_dict)
                    copy_res["cache_hit"] = True
                    return copy_res
            return {
                "state": STATE_UNCERTAIN,
                "summary": "并发等待检测超时",
                "url": url,
                "disk_type": disk_type or match_netdisk_link(url),
                "canonical_key": canonical_key,
                "cache_hit": False,
            }

        # 3. 领头者执行真实网络探测
        try:
            detected_type = disk_type or match_netdisk_link(url)
            pwd = password or extract_password_from_url(url)

            # 路由匹配合适的探测器
            matched_detector = None
            for detector in self._detectors:
                if detector.can_handle(url, detected_type):
                    matched_detector = detector
                    break

            if matched_detector:
                raw_res = self._run_detector(matched_detector, url, pwd)
            else:
                raw_res = {
                    "state": STATE_UNSUPPORTED,
                    "summary": f"暂不支持检测 {detected_type}",
                }

            result_obj = CheckResult(
                state=raw_res.get("state", STATE_UNSUPPORTED),
                summary=raw_res.get("summary", ""),
                url=url,
                disk_type=detected_type,
                canonical_key=canonical_key,
                file_count=raw_res.get("file_count"),
                checked_at=int(now),
                cache_hit=False,
            )
            res_dict = result_obj.to_dict()

            # 计算缓存 TTL
            ttl = CACHE_TTL_OK if res_dict["state"] == STATE_OK else (
                CACHE_TTL_BAD if res_dict["state"] == STATE_BAD else CACHE_TTL_OTHER
            )
            with self._cache_lock:
                self._cache[canonical_key] = (res_dict, now + ttl)

            return res_dict

        finally:
            event.set()
            with self._inflight_lock:
                self._inflight.pop(canonical_key, None)

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
