import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.plugins.detail_page_adapter import DetailPagePlugin
from src.plugins.http_plugin import PluginRequestError, clean_text


class Xb6vPlugin(DetailPagePlugin):
    name = "xb6v"
    display_name = "6V 电影"
    description = "6V 电影搜索与详情页磁力资源"
    priority = 115
    is_enabled = False
    publish_by_default = True
    timeout = 9.0
    base_urls = ("https://www.66ss.org", "https://www.xb6v.com")
    resource_selector = "a[href^='magnet:']"

    def search_records(self, keyword):
        errors = []
        for base in self.base_urls:
            self.base_url = base
            try:
                response = self.request(
                    "POST", base + "/e/search/11index.php",
                    data={"show": "title", "tempid": "1", "tbname": "article", "mid": "1", "dopost": "search", "submit": "", "keyboard": keyword},
                    headers={"Referer": base, "Content-Type": "application/x-www-form-urlencoded"},
                    allow_redirects=False,
                )
                location = response.headers.get("Location", "")
                if not location:
                    match = re.search(r"(?:location\.href\s*=\s*['\"]([^'\"]+)|result/\?searchid=\d+)", response.text)
                    location = match.group(1) or match.group(0) if match else ""
                if not location:
                    raise PluginRequestError("搜索响应缺少跳转地址")
                page = self.request("GET", urljoin(base, location), headers={"Referer": base})
                soup = BeautifulSoup(page.text, "html.parser")
                records = []
                for row in soup.select("ul#post_container li.post"):
                    anchor = row.select_one("a[href*='.html']")
                    if not anchor:
                        continue
                    title = clean_text(anchor.get("title") or anchor.get_text(" ", strip=True))
                    date = row.select_one(".info .info_date")
                    if title:
                        records.append((title, urljoin(base, anchor.get("href")), clean_text(date.get_text(" ", strip=True)) if date else None))
                return records
            except Exception as error:
                errors.append(error)
        raise PluginRequestError(f"[xb6v] 所有备用网址均失败: {errors[0] if errors else '未知错误'}")
