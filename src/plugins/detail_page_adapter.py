import concurrent.futures
from typing import List, Sequence, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, clean_text, extract_links


class DetailPagePlugin(HttpPlugin):
    base_url = ""
    search_selector = ""
    title_selector = ""
    detail_link_selector = ""
    resource_selector = "a[href]"
    max_details = 12

    def search_records(self, keyword: str) -> Sequence[Tuple[str, str, object]]:
        raise NotImplementedError

    def parse_detail(self, title: str, url: str, datetime_value=None) -> List[SearchResultItem]:
        response = self.request("GET", url, headers={"Referer": self.base_url + "/"})
        soup = BeautifulSoup(response.text, "html.parser")
        values = [node.get("href") or node.get("data-clipboard-text") for node in soup.select(self.resource_selector)]
        return [self.make_item(title, link, datetime_value=datetime_value) for value in values for link in extract_links(value)]

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        records = list(self.search_records(keyword))[: self.max_details]
        items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(records) or 1)) as executor:
            futures = [executor.submit(self.parse_detail, *record) for record in records]
            for future in concurrent.futures.as_completed(futures):
                try:
                    items.extend(future.result())
                except Exception:
                    continue
        return self.finalize(items)

    def records_from_html(self, html: str, datetime_selector: str = ""):
        soup = BeautifulSoup(html, "html.parser")
        records = []
        for node in soup.select(self.search_selector):
            anchor = node.select_one(self.detail_link_selector)
            if not anchor:
                continue
            title_node = node.select_one(self.title_selector) if self.title_selector else anchor
            title = clean_text((title_node or anchor).get_text(" ", strip=True) or anchor.get("title"))
            href = anchor.get("href")
            date_node = node.select_one(datetime_selector) if datetime_selector else None
            if title and href:
                records.append((title, urljoin(self.base_url, href), clean_text(date_node.get_text(" ", strip=True)) if date_node else None))
        return records
