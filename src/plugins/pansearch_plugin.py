import re
import threading
import time
from typing import List

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text, extract_links


class PansearchPlugin(HttpPlugin):
    name = "pansearch"
    display_name = "盘搜"
    description = "动态发现 Next.js buildId 的盘搜 API"
    priority = 145
    is_enabled = False
    publish_by_default = True
    timeout = 9.0
    website = "https://www.pansearch.me/search"

    def __init__(self):
        super().__init__()
        self._build_id = ""
        self._build_time = 0.0
        self._lock = threading.Lock()

    def _get_build_id(self, force=False):
        with self._lock:
            if not force and self._build_id and time.time() - self._build_time < 1800:
                return self._build_id
            response = self.request("GET", self.website, retries=0)
            match = re.search(r'"buildId":"([^"]+)"', response.text)
            if not match:
                soup = BeautifulSoup(response.text, "html.parser")
                script = soup.select_one("script#__NEXT_DATA__")
                match = re.search(r'"buildId"\s*:\s*"([^"]+)"', script.string or "") if script else None
            if not match:
                raise PluginRequestError("[pansearch] 页面缺少 Next.js buildId")
            self._build_id = match.group(1)
            self._build_time = time.time()
            return self._build_id

    def _fetch(self, keyword, offset, force=False):
        build_id = self._get_build_id(force)
        endpoint = f"https://www.pansearch.me/_next/data/{build_id}/search.json"
        response = self.request("GET", endpoint, params={"keyword": keyword, "offset": offset}, headers={"Referer": self.website}, retries=0)
        try:
            return (((response.json().get("pageProps") or {}).get("data") or {}).get("data") or [])
        except ValueError as error:
            raise PluginRequestError(f"[pansearch] JSON 解析失败: {error}") from error

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        records = []
        try:
            for offset in (0, 10, 20):
                records.extend(self._fetch(keyword, offset))
        except PluginRequestError:
            records = self._fetch(keyword, 0, force=True)
        items = []
        for record in records:
            content = record.get("content") or ""
            soup = BeautifulSoup(f"<div>{content}</div>", "html.parser")
            text = clean_text(soup.get_text("\n", strip=True))
            title_match = re.search(r"名称[:：]\s*([^\n]+)", soup.get_text("\n", strip=True))
            title = clean_text(title_match.group(1)) if title_match else keyword
            links = [anchor.get("href") for anchor in soup.select("a[href]")] or extract_links(content)
            password_match = re.search(r"(?:提取码|访问码|密码|pwd|code)\s*[:=：]?\s*([0-9a-z]{4,8})", text, re.I)
            for link in links:
                items.append(self.make_item(title, link, password=password_match.group(1) if password_match else None, datetime_value=record.get("time")))
        return self.finalize(items)
