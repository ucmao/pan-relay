import concurrent.futures
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text, extract_links


class Quark4KPlugin(HttpPlugin):
    name = "quark4k"
    display_name = "Quark4K"
    version = "1.0.0"
    author = "pan-relay"
    description = "Quark4K 论坛公开讨论 API"
    priority = 135
    is_enabled = False
    publish_by_default = True
    timeout = 9.0
    endpoint = "https://quark4k.com/api/discussions"
    page_size = 50

    def _fetch_page(self, keyword: str, offset: int) -> Dict[str, Any]:
        params = {
            "include": "user,lastPostedUser,mostRelevantPost,mostRelevantPost.user,tags,tags.parent,firstPost",
            "filter[q]": keyword,
            "sort": "",
            "page[offset]": offset,
            "page[limit]": self.page_size,
        }
        response = self.request(
            "GET",
            self.endpoint,
            params=params,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://quark4k.com/",
            },
        )
        try:
            return response.json()
        except ValueError as error:
            raise PluginRequestError(f"[{self.name}] JSON 解析失败: {error}") from error

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        payloads = []
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._fetch_page, keyword, offset) for offset in (0, self.page_size)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    payloads.append(future.result())
                except Exception as error:
                    errors.append(error)
        if not payloads and errors:
            raise PluginRequestError(f"[{self.name}] 页面请求失败: {errors[0]}")

        items = []
        terms = keyword.casefold().split()
        for payload in payloads:
            posts = {
                str(item.get("id")): item
                for item in payload.get("included") or []
                if item.get("type") == "posts"
            }
            for discussion in payload.get("data") or []:
                attributes = discussion.get("attributes") or {}
                title = clean_text(attributes.get("title"))
                if not title or any(term not in title.casefold() for term in terms):
                    continue
                relationships = discussion.get("relationships") or {}
                post_ref = ((relationships.get("mostRelevantPost") or {}).get("data") or {})
                post = posts.get(str(post_ref.get("id"))) or {}
                post_attrs = post.get("attributes") or {}
                content_html = str(post_attrs.get("contentHtml") or "")
                soup = BeautifulSoup(content_html, "html.parser")
                links = [anchor.get("href") for anchor in soup.select("a[href]")]
                links.extend(extract_links(soup.get_text("\n", strip=True)))
                for link in links:
                    items.append(
                        self.make_item(
                            title,
                            link,
                            datetime_value=attributes.get("createdAt"),
                        )
                    )
        return self.finalize(items)
