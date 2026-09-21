# src/services/link_checker/base.py

import logging
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from src.configs.app_config import user_agents
from .constants import STATE_OK, STATE_BAD, STATE_LOCKED, STATE_UNCERTAIN, STATE_UNSUPPORTED
from .models import CheckResult

logger = logging.getLogger(__name__)


def contains_any(text: Optional[str], targets: List[str]) -> bool:
    """检查文本是否包含 targets 列表中的任意一个子串 (忽略大小写)"""
    if not text:
        return False
    lower = str(text).lower()
    return any(t.lower() in lower for t in targets)


class BaseDetector(ABC):
    """
    网盘免登录探测器基类
    """
    platform_name: str = "unknown"
    domain_patterns: List[str] = []
    supported_keywords: List[str] = []

    def get_headers(self, custom: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        ua = random.choice(user_agents) if user_agents else (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        headers = {"User-Agent": ua}
        if custom:
            headers.update(custom)
        return headers

    def can_handle(self, url: str, disk_type: Optional[str] = None) -> bool:
        """
        判断当前探测器是否支持该链接或指定网盘类型
        """
        # 1. 优先按 disk_type 精确分类
        if disk_type:
            dtype_norm = disk_type.replace("网盘", "").replace("云盘", "").strip().lower()
            if any(k.lower() in dtype_norm for k in self.supported_keywords):
                return True

        # 2. 按 URL 域名/特征匹配 (严格区分域名，避免因URL带数字或无关字样误判)
        url_lower = (url or "").lower()
        if any(p.lower() in url_lower for p in self.domain_patterns):
            return True

        return False

    @abstractmethod
    def check(
        self,
        url: str,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> Dict[str, Any]:
        """
        执行具体探测逻辑，返回状态字典 (包含 state, summary, 可选 file_count 等)
        """
        pass
