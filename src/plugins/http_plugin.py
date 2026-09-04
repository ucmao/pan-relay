import html
import logging
import random
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import requests

from src.configs.app_config import user_agents
from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin
from src.utils.netdisk_utils import (
    extract_canonical_resource_key,
    extract_password_from_url,
    match_netdisk_link,
)

logger = logging.getLogger(__name__)

RETRIABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
URL_PATTERN = re.compile(
    r"(?:https?://[^\s<>'\"，。；、]+|magnet:\?xt=urn:btih:[^\s<>'\"]+|ed2k://[^\s<>'\"]+)",
    re.IGNORECASE,
)


class PluginRequestError(RuntimeError):
    """目标数据源请求或响应异常。"""


class HttpPlugin(BasePlugin):
    """所有 HTTP 搜索插件共用的请求、重试和结果规范。"""

    retries = 1
    retry_backoff = 0.15
    health_keyword = "三体"

    def __init__(self):
        self._thread_state = threading.local()

    @property
    def session(self) -> requests.Session:
        session = getattr(self._thread_state, "session", None)
        if session is None:
            session = requests.Session()
            self._thread_state.session = session
        return session

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        retries: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        request_headers = {
            "User-Agent": random.choice(user_agents),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        request_headers.update(headers or {})
        kwargs.setdefault("timeout", (min(float(self.timeout), 3.0), float(self.timeout)))
        attempts = max((self.retries if retries is None else retries) + 1, 1)
        last_error: Optional[BaseException] = None

        for attempt in range(attempts):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=request_headers,
                    **kwargs,
                )
                if response.status_code < 400:
                    return response
                last_error = PluginRequestError(f"HTTP {response.status_code}")
                response.close()
                if response.status_code not in RETRIABLE_STATUS_CODES:
                    break
            except requests.RequestException as error:
                last_error = error

            if attempt + 1 < attempts:
                time.sleep(self.retry_backoff * (2**attempt))

        raise PluginRequestError(f"[{self.name}] 请求失败: {last_error or '未知错误'}")

    def make_item(
        self,
        title: Any,
        share_link: Any,
        *,
        password: Any = None,
        datetime_value: Any = None,
    ) -> Optional[SearchResultItem]:
        clean_title = clean_text(title)
        clean_link = normalize_link(share_link)
        cloud_name = match_netdisk_link(clean_link)
        if not clean_title or not clean_link or cloud_name == "其他":
            return None
        return SearchResultItem(
            source=f"plugin:{self.name}",
            title=clean_title,
            share_link=clean_link,
            cloud_name=cloud_name,
            password=clean_text(password) or extract_password_from_url(clean_link),
            datetime=parse_datetime(datetime_value),
        )

    def finalize(self, items: Iterable[Optional[SearchResultItem]]) -> List[SearchResultItem]:
        unique: Dict[str, SearchResultItem] = {}
        for item in items:
            if item is None:
                continue
            key = extract_canonical_resource_key(item.share_link)
            if not key:
                continue
            existing = unique.get(key)
            if existing is None or result_score(item) > result_score(existing):
                unique[key] = item
        return list(unique.values())

    def health_check(self):
        try:
            results = self.search(self.health_keyword)
            return True, f"搜索协议正常，返回 {len(results)} 条"
        except Exception as error:
            return False, str(error)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(html.unescape(str(value)).split()).strip()


def normalize_link(value: Any) -> str:
    return html.unescape(str(value or "")).strip().rstrip(".,;，。；、)")


def parse_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).isoformat(sep=" ", timespec="seconds")
        except (ValueError, OSError, OverflowError):
            return None
    text = clean_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).isoformat(sep=" ", timespec="seconds")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).isoformat(sep=" ", timespec="seconds")
        except ValueError:
            continue
    return None


def extract_links(text: Any) -> List[str]:
    return [normalize_link(match.group(0)) for match in URL_PATTERN.finditer(html.unescape(str(text or "")))]


def result_score(item: SearchResultItem) -> int:
    return len(item.title) + (20 if item.password else 0) + (5 if item.datetime else 0)
