import threading
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, clean_text


class Ting77Plugin(HttpPlugin):
    name = "ting77"
    display_name = "77听资源"
    description = "搜索前置 token 与短期解析链接缓存"
    priority = 130
    is_enabled = False
    publish_by_default = True
    timeout = 9.0
    base_url = "https://sou.77ting.top"

    def __init__(self):
        super().__init__()
        self._links = {}
        self._lock = threading.Lock()

    def _resolve(self, resource_id, cloud_type, title, referer):
        key = (resource_id, cloud_type)
        with self._lock:
            cached = self._links.get(key)
            if cached and time.time() - cached[0] < 300:
                return self.make_item(title, cached[1])
        token_response = self.request(
            "GET", self.base_url + "/api/link/token",
            params={"id": resource_id, "type": cloud_type}, headers={"Referer": referer}, retries=0,
        )
        payload = token_response.json()
        data = payload.get("data") or {}
        if payload.get("code") != 0 or not data.get("token") or not data.get("ts"):
            return None
        response = self.request(
            "GET", self.base_url + "/go",
            params={"id": resource_id, "type": cloud_type, "token": data["token"], "ts": data["ts"]},
            headers={"Referer": referer}, allow_redirects=False, retries=0,
        )
        location = urljoin(self.base_url, response.headers.get("Location", ""))
        item = self.make_item(title, location)
        if item:
            with self._lock:
                self._links[key] = (time.time(), location)
        return item

    def search(self, keyword: str) -> list[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        response = self.request("GET", self.base_url + "/search", params={"q": keyword})
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        for row in soup.select("a.resource-row[href^='/resource/']")[:10]:
            resource_id = row.get("href", "").rstrip("/").rsplit("/", 1)[-1]
            title_node = row.select_one(".row-title")
            title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
            referer = urljoin(self.base_url, row.get("href"))
            cloud_types = []
            for badge in row.select(".cloud-badge"):
                cloud_types.extend(value for value in ("quark", "ali", "baidu") if value in badge.get("class", []))
            for cloud_type in dict.fromkeys(cloud_types):
                try:
                    items.append(self._resolve(resource_id, cloud_type, title, referer))
                except Exception:
                    continue
        return self.finalize(items)
