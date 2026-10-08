# src/services/security_service.py

import logging
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Dict, Set, Tuple

from flask import current_app, has_app_context

from src.services.log_service import get_current_client_ip
from src.services.system_config_service import get_security_config


logger = logging.getLogger(__name__)

# 单 IP 滑动窗口请求历史: ip -> deque([timestamp, ...])
_request_records: Dict[str, deque] = defaultdict(deque)

# 单 IP 正在进行的并发搜索计数: ip -> int
_active_searches: Dict[str, int] = defaultdict(int)
_lock = Lock()


class IPConcurrencyGuard:
    """
    单 IP 并发搜索上下文管理器，自动增加和释放 active 计数。
    """
    def __init__(self, ip: str):
        self.ip = ip

    def __enter__(self):
        with _lock:
            _active_searches[self.ip] += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        with _lock:
            _active_searches[self.ip] = max(0, _active_searches[self.ip] - 1)


def check_request_security() -> Tuple[bool, str, int]:
    """
    针对客户端 IP 进行多层安全校验：
    1. IP 黑名单拦截
    2. 单 IP 最大并发数限制 (防止并发挂死服务器)
    3. 单 IP 滑动窗口频率限制

    :return: (is_allowed, error_message, http_status_code)
    """
    client_ip = get_current_client_ip()
    config = get_security_config()

    # 1. IP 黑名单校验 (单元测试模式下也必须保持校验)
    ip_blacklist: Set[str] = set(config.get("ip_blacklist", []))
    if client_ip in ip_blacklist:
        logger.warning(f"[安全拦截] 黑名单 IP 访问拒绝: {client_ip}")
        return False, "您的 IP 地址已被系统封禁，无法使用搜索服务", 403

    # 在单元测试模式下，避免频繁的 API 测试触发 429 导致不相干单元测试失败
    if has_app_context() and current_app.config.get("TESTING") and not current_app.config.get("ENABLE_SECURITY_RATE_LIMIT_IN_TESTS"):
        return True, "", 200

    # 2. 单 IP 并发数限制
    max_concurrent = config.get("max_concurrent_searches", 1)
    with _lock:
        current_active = _active_searches.get(client_ip, 0)
        if current_active >= max_concurrent:
            logger.warning(f"[并发拦截] IP {client_ip} 已存在 {current_active} 个并发搜索任务")
            return False, "您上一次搜索尚未完成，请勿并发提交！", 429

    # 3. 滑动窗口频率限制
    rate_limit_per_min = config.get("rate_limit_per_minute", 5)
    now = time.time()
    records = _request_records[client_ip]

    with _lock:
        # 清理 60 秒窗口之外的历史记录
        while records and records[0] <= now - 60:
            records.popleft()

        if len(records) >= rate_limit_per_min:
            logger.warning(f"[频控拦截] IP {client_ip} 触发频率限制 ({len(records)}/min >= {rate_limit_per_min})")
            return False, f"请求过于频繁，单 IP 每分钟限 {rate_limit_per_min} 次搜索", 429

        records.append(now)

    return True, "", 200

