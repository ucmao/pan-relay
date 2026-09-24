import logging
import time
from typing import List

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, clean_text

logger = logging.getLogger(__name__)

# 动态软依赖引入，保证缺失依赖时安全降级
try:
    from curl_cffi import requests as cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    cffi_requests = None


class SougsPlugin(HttpPlugin):
    """搜网盘 (sou.gs) API 搜索插件，支持 TLS 指纹绕过与并发受控轮询。"""

    name = "sougs"
    display_name = "搜网盘"
    description = "搜网盘 (sou.gs) API 检索"
    version = "1.0.0"
    author = "pan-relay"
    priority = 140
    is_enabled = CURL_CFFI_AVAILABLE
    publish_by_default = True
    timeout = 6.0
    website = "https://sou.gs"

    def search(self, keyword: str) -> List[SearchResultItem]:
        if not CURL_CFFI_AVAILABLE:
            logger.warning("[sougs] 未安装 curl_cffi 依赖，跳过此数据源")
            return []

        keyword = clean_text(keyword)
        if not keyword:
            return []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": f"{self.website}/search",
        }

        try:
            session = cffi_requests.Session(impersonate="chrome124")

            # 1. 初始搜索请求
            init_url = f"{self.website}/api/frontend/search"
            resp = session.get(init_url, params={"q": keyword}, headers=headers, timeout=4.0)
            res_json = resp.json()
            data = res_json.get("data", {})
            search_id = data.get("search_id")
            raw_items = data.get("items", []) or []

            # 2. 受控的快速轮询机制
            start_time = time.monotonic()
            max_polling_seconds = 2.5  # 轮询耗时控制在 2.5s 内
            empty_count = 0

            while search_id and not data.get("complete"):
                if time.monotonic() - start_time > max_polling_seconds:
                    logger.info("[sougs] 已达轮询时间预算上限 (2.5s)，中断轮询交付结果")
                    break

                time.sleep(0.3)

                poll_url = f"{self.website}/api/frontend/search/poll"
                poll_resp = session.get(poll_url, params={"id": search_id}, headers=headers, timeout=2.0)
                poll_json = poll_resp.json()
                data = poll_json.get("data", {})
                new_items = data.get("items", []) or []
                raw_items.extend(new_items)

                if not new_items:
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0

            # 3. 构造标准 SearchResultItem 列表
            items = []
            for item in raw_items:
                title = clean_text(item.get("title"))
                link = clean_text(item.get("share_link") or item.get("link"))
                if not title or not link:
                    continue

                search_item = self.make_item(
                    title=title,
                    share_link=link,
                    datetime_value=item.get("created_at") or item.get("time"),
                )
                if search_item:
                    items.append(search_item)

            return self.finalize(items)

        except Exception as error:
            logger.error(f"[sougs] 搜索或轮询抛出异常: {error}")
            return []

    def health_check(self):
        if not CURL_CFFI_AVAILABLE:
            return False, "缺少 curl_cffi 依赖，请运行 pip install curl_cffi"
        return super().health_check()
