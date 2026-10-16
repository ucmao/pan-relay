import concurrent.futures
import re
from typing import List, Optional, Sequence, Tuple
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text, extract_links


class MacCmsPlugin(HttpPlugin):
    """MacCMS 搜索页 + 详情页型数据源的共用实现。"""

    base_urls: Sequence[str] = ()
    max_details = 12

    def _search_base(self, base_url: str, keyword: str) -> List[Tuple[str, str, Optional[str], Optional[str], Optional[str]]]:
        url = f"{base_url.rstrip('/')}/index.php/vod/search/wd/{quote(keyword, safe='')}.html"
        response = self.request("GET", url, headers={"Referer": f"{base_url.rstrip('/')}/"}, retries=0)
        soup = BeautifulSoup(response.text, "html.parser")
        records = []
        for card in soup.select(".module-search-item"):
            anchor = card.select_one(".video-info-header h3 a[href]") or card.select_one("a[href*='/vod/detail/id/']")
            if not anchor:
                continue
            title = clean_text(anchor.get("title") or anchor.get_text(" ", strip=True))
            href = anchor.get("href") or ""
            img_node = card.select_one(".module-item-pic img, .video-cover img, img")
            cover = (img_node.get("data-src") or img_node.get("src")) if img_node else None
            if cover and not cover.startswith("http"):
                cover = urljoin(base_url, cover)
            desc_node = card.select_one(".video-info-main, .module-info-item-content, .desc")
            desc = clean_text(desc_node.get_text(" ", strip=True)) if desc_node else None
            date_node = card.select_one(".video-info-header .tag-link, .video-serial, .date")
            dt = clean_text(date_node.get_text(" ", strip=True)) if date_node else None
            if title and href:
                records.append((title, urljoin(base_url, href), cover, desc, dt))
        return records[: self.max_details]

    def _detail(
        self,
        base_url: str,
        title: str,
        detail_url: str,
        cover: Optional[str] = None,
        desc: Optional[str] = None,
        dt: Optional[str] = None,
    ) -> List[SearchResultItem]:
        response = self.request("GET", detail_url, headers={"Referer": base_url}, retries=0)
        soup = BeautifulSoup(response.text, "html.parser")
        if not cover:
            img = soup.select_one(".module-item-pic img, .video-cover img, .detail-pic img")
            c = (img.get("data-src") or img.get("src")) if img else None
            if c:
                cover = c if c.startswith("http") else urljoin(base_url, c)
        if not desc:
            d_node = soup.select_one(".video-info-content, .module-info-introduction-content, .vod-content")
            if d_node:
                desc = clean_text(d_node.get_text(" ", strip=True))

        values = []
        for node in soup.select("#download-list [data-clipboard-text], #download-list a[href]"):
            values.append(node.get("data-clipboard-text") or node.get("href"))
        if not values:
            values = extract_links(response.text)
        return [
            self.make_item(title, link, datetime_value=dt, description=desc, cover_url=cover)
            for value in values
            for link in extract_links(value)
        ]

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        records = []
        errors = []
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(self.base_urls) or 1))
        futures = {executor.submit(self._search_base, base_url, keyword): base_url for base_url in self.base_urls}
        try:
            for future in concurrent.futures.as_completed(futures, timeout=self.timeout):
                try:
                    found = future.result()
                    if found:
                        base_url = futures[future]
                        records = [(base_url, *record) for record in found]
                        break
                except Exception as error:
                    errors.append(error)
        except concurrent.futures.TimeoutError:
            errors.append(PluginRequestError("备用网址探测超时"))
        finally:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
        if not records and errors:
            raise PluginRequestError(f"[{self.name}] 所有备用网址均失败: {errors[0]}")

        items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(records) or 1)) as executor:
            futures = [executor.submit(self._detail, *record) for record in records]
            for future in concurrent.futures.as_completed(futures):
                try:
                    items.extend(future.result())
                except Exception:
                    continue
        return self.finalize(items)
