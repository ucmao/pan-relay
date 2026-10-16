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

    def parse_detail(
        self,
        title: str,
        url: str,
        datetime_value=None,
        cover_url=None,
        description=None,
        metadata=None,
    ) -> List[SearchResultItem]:
        response = self.request("GET", url, headers={"Referer": self.base_url + "/"})
        soup = BeautifulSoup(response.text, "html.parser")
        page_metadata = dict(metadata or {})
        for node in soup.select("meta[property], meta[name]"):
            key = clean_text(node.get("property") or node.get("name")).lower()
            value = clean_text(node.get("content"))
            if key and value and any(marker in key for marker in ("og:", "article:", "twitter:", "description", "published", "date", "author", "keywords")):
                page_metadata.setdefault(key.replace(":", "_"), value)
        if not datetime_value:
            datetime_value = page_metadata.get("article_published_time") or page_metadata.get("datepublished") or page_metadata.get("published_time")
        if not cover_url:
            img = soup.select_one("img.cover, .post-thumb img, .entry-content img, .detail-pic img, .video-cover img, .article-content img")
            if img:
                c = img.get("data-src") or img.get("src")
                if c:
                    cover_url = c if c.startswith("http") else urljoin(self.base_url, c)
            if not cover_url and page_metadata.get("og_image"):
                cover_url = page_metadata["og_image"]
        if not description:
            desc_node = soup.select_one(".entry-content p, .article-content p, .post-content p, .intro, .summary, .description")
            if desc_node:
                description = clean_text(desc_node.get_text(" ", strip=True))
            if not description:
                description = page_metadata.get("og_description") or page_metadata.get("description")
        values = [node.get("href") or node.get("data-clipboard-text") for node in soup.select(self.resource_selector)]
        return [
            self.make_item(title, link, datetime_value=datetime_value, cover_url=cover_url, description=description, metadata=page_metadata)
            for value in values
            for link in extract_links(value)
        ]

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

    def records_from_html(
        self,
        html: str,
        datetime_selector: str = "",
        cover_selector: str = "",
        desc_selector: str = "",
    ):
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
            img_node = node.select_one(cover_selector) if cover_selector else node.select_one("img")
            cover = None
            if img_node:
                c = img_node.get("data-src") or img_node.get("src")
                if c:
                    cover = c if c.startswith("http") else urljoin(self.base_url, c)
            desc_node = node.select_one(desc_selector) if desc_selector else None
            desc = clean_text(desc_node.get_text(" ", strip=True)) if desc_node else None
            metadata = {"search_card_text": clean_text(node.get_text(" ", strip=True))}
            for key, value in (node.attrs or {}).items():
                if key.startswith("data-") and value not in (None, ""):
                    metadata[key[5:].replace("-", "_")] = value
            if title and href:
                records.append((
                    title,
                    urljoin(self.base_url, href),
                    clean_text(date_node.get_text(" ", strip=True)) if date_node else None,
                    cover,
                    desc,
                    metadata,
                ))
        return records
