from typing import List

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, clean_text


class NyaaPlugin(HttpPlugin):
    name = "nyaa"
    display_name = "Nyaa 磁力搜索"
    version = "1.0.0"
    author = "pan-relay"
    description = "Nyaa 单页种子与磁力搜索"
    priority = 90
    is_enabled = False
    publish_by_default = False
    timeout = 8.0
    endpoint = "https://nyaa.si/"

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        response = self.request(
            "GET",
            self.endpoint,
            params={"f": 0, "c": "0_0", "q": keyword},
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
                "Referer": self.endpoint,
            },
        )
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        terms = keyword.casefold().split()
        for row in soup.select("table.torrent-list tbody tr"):
            title_anchor = row.select_one("td[colspan='2'] a[href*='/view/']")
            magnet_anchor = row.select_one("a[href^='magnet:']")
            if not title_anchor or not magnet_anchor:
                continue
            title = clean_text(title_anchor.get_text(" ", strip=True) or title_anchor.get("title"))
            if any(term not in title.casefold() for term in terms):
                continue
            date_cell = row.select_one("td[data-timestamp]")
            timestamp = date_cell.get("data-timestamp") if date_cell else None
            try:
                timestamp = int(timestamp) if timestamp else None
            except (TypeError, ValueError):
                timestamp = None
            items.append(
                self.make_item(title, magnet_anchor.get("href"), datetime_value=timestamp)
            )
        return self.finalize(items)
