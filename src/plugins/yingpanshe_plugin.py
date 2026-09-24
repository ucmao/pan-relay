from typing import List
from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text


class YingpanshePlugin(HttpPlugin):
    """影盘社网盘资源搜索插件"""

    name = "yingpanshe"
    display_name = "影盘社"
    description = "影盘社网盘资源检索"
    version = "1.0.0"
    author = "pan-relay"
    priority = 130
    is_enabled = True
    publish_by_default = True
    timeout = 6.0
    website = "https://www.yingpanshe.com"

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []

        url = f"{self.website}/search"
        try:
            response = self.request("GET", url, params={"q": keyword, "page": 1})
        except PluginRequestError:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        items = []

        for item in soup.find_all("article", class_="search-item"):
            title_el = item.find("a", class_="search-item-title")
            action_el = item.find("a", class_="search-item-action")
            meta_spans = item.find_all("span", class_="search-item-meta")

            title = clean_text(title_el.text) if title_el else ""
            link = title_el.get("href", "").strip() if title_el else ""
            date_str = clean_text(meta_spans[1].text) if len(meta_spans) > 1 else None

            # 如果标题没有拿到直链，尝试使用详情/操作按钮的链接
            if not link and action_el:
                href = action_el.get("href", "").strip()
                if href:
                    link = f"{self.website}{href}" if href.startswith("/") else href

            if not title or not link:
                continue

            search_item = self.make_item(
                title=title,
                share_link=link,
                datetime_value=date_str,
            )
            if search_item:
                items.append(search_item)

        return self.finalize(items)
