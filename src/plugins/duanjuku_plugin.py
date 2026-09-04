from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.plugins.detail_page_adapter import DetailPagePlugin
from src.plugins.http_plugin import clean_text


class DuanjukuPlugin(DetailPagePlugin):
    """短剧库网页搜索源：搜索页返回详情页，网盘链接位于详情页。"""

    name = "duanjuku"
    display_name = "短剧库"
    description = "短剧库网页搜索与详情页网盘链接"
    priority = 120
    is_enabled = True
    publish_by_default = True
    timeout = 8.0
    base_url = "https://so.duanjuku.top"
    max_details = 10

    def search_records(self, keyword):
        response = self.request(
            "GET",
            self.base_url + "/search.php",
            params={"q": keyword},
        )
        soup = BeautifulSoup(response.text, "html.parser")
        records = []
        seen_urls = set()

        # 站内详情页使用数字 ID，例如 /77553.html；分页和静态页面不会匹配。
        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "")
            if not href.lstrip("/").split("?", 1)[0].removesuffix(".html").isdigit():
                continue
            url = urljoin(self.base_url, href)
            if url in seen_urls:
                continue
            title = clean_text(anchor.get_text(" ", strip=True) or anchor.get("title"))
            if title:
                seen_urls.add(url)
                records.append((title, url, None))
        return records
