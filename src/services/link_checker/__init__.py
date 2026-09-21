# src/services/link_checker/__init__.py

"""
网盘链接健康与有效性检测服务包 (Python 原生模块化实现)
支持夸克、百度、阿里、UC、迅雷、123、天翼、115、移动云盘等免登录深度测活。
"""

from typing import Any, Dict, List, Optional
import requests

from .constants import (
    CACHE_TTL_BAD,
    CACHE_TTL_OK,
    CACHE_TTL_OTHER,
    STATE_BAD,
    STATE_LOCKED,
    STATE_OK,
    STATE_UNCERTAIN,
    STATE_UNSUPPORTED,
)
from .models import CheckResult
from .base import BaseDetector
from .engine import LinkCheckEngine

# 全局单例引擎
_global_engine = LinkCheckEngine()

# 向后兼容别名
LinkChecker = LinkCheckEngine


def check_link(
    url: str,
    password: Optional[str] = None,
    disk_type: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """单条网盘链接检测"""
    return _global_engine.check_link(
        url,
        password=password,
        disk_type=disk_type,
        force_refresh=force_refresh,
    )


def check_links_batch(
    items: List[Dict[str, Any]],
    max_workers: int = 6,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """批量并发检测网盘链接"""
    return _global_engine.check_links_batch(
        items,
        max_workers=max_workers,
        force_refresh=force_refresh,
    )


__all__ = [
    "STATE_OK",
    "STATE_BAD",
    "STATE_LOCKED",
    "STATE_UNCERTAIN",
    "STATE_UNSUPPORTED",
    "CACHE_TTL_OK",
    "CACHE_TTL_BAD",
    "CACHE_TTL_OTHER",
    "CheckResult",
    "BaseDetector",
    "LinkCheckEngine",
    "LinkChecker",
    "check_link",
    "check_links_batch",
]
