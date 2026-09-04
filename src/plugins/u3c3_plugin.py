import re
import threading
import time

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text


class U3c3Plugin(HttpPlugin):
    name = "u3c3"
    display_name = "U3C3 磁力"
    description = "成人内容动态参数磁力源；独立标记并默认关闭"
    priority = 60
    is_enabled = False
    publish_by_default = True
    timeout = 8.0
    base_url = "https://u3c3u3c3.u3c3u3c3u3c3.com"

    def __init__(self):
        super().__init__()
        self._parameter = ""
        self._parameter_time = 0.0
        self._lock = threading.Lock()

    def _search_parameter(self):
        with self._lock:
            if self._parameter and time.time() - self._parameter_time < 3600:
                return self._parameter
            response = self.request("GET", self.base_url)
            patterns = (r"search2\s*[:=]\s*['\"]([^'\"]+)", r"name=['\"]search2['\"][^>]*value=['\"]([^'\"]+)")
            for pattern in patterns:
                match = re.search(pattern, response.text)
                if match:
                    self._parameter = match.group(1)
                    self._parameter_time = time.time()
                    return self._parameter
            raise PluginRequestError("[u3c3] 首页缺少 search2 参数")

    def search(self, keyword: str) -> list[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        response = self.request("GET", self.base_url + "/", params={"search2": self._search_parameter(), "search": keyword}, headers={"Referer": self.base_url + "/"})
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        for row in soup.select("tbody tr.default"):
            cells = row.select("td")
            if len(cells) < 3:
                continue
            title = clean_text(cells[1].get_text(" ", strip=True))
            if any(term not in title.casefold() for term in keyword.casefold().split()):
                continue
            date = clean_text(cells[4].get_text(" ", strip=True)) if len(cells) > 4 else None
            for anchor in cells[2].select("a[href^='magnet:']"):
                items.append(self.make_item(title, anchor.get("href"), datetime_value=date))
        return self.finalize(items)
