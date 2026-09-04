from typing import List

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, clean_text, normalize_link


class QuarksooPlugin(HttpPlugin):
    name = "quarksoo"
    display_name = "夸克搜"
    version = "1.0.0"
    author = "pan-relay"
    description = "夸克搜单页 HTML 搜索"
    priority = 120
    is_enabled = False
    publish_by_default = True
    timeout = 7.0
    endpoint = "https://quarksoo.cc/search.php"

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        response = self.request(
            "GET",
            self.endpoint,
            params={"q": keyword},
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://quarksoo.cc/",
            },
        )
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        terms = keyword.casefold().split()
        for row in soup.select("tr"):
            cells = row.select("td")
            if len(cells) < 2:
                continue
            title = clean_text(cells[0].get_text(" ", strip=True))
            anchor = cells[1].select_one("a[href]") or row.select_one("a[href]")
            if not title or not anchor or any(term not in title.casefold() for term in terms):
                continue
            link = normalize_link(anchor.get("href"))
            if "pan.quark.cn" not in link.casefold():
                continue
            items.append(self.make_item(title, link))
        return self.finalize(items)
