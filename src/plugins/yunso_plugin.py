import base64
import concurrent.futures
import html
import re
from typing import List
from urllib.parse import parse_qs, quote, urlparse

from bs4 import BeautifulSoup

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text


class YunsoPlugin(HttpPlugin):
    name = "yunso"
    display_name = "小云搜索"
    version = "1.0.0"
    author = "pan-relay"
    description = "小云搜索 HTML 片段 API"
    priority = 145
    is_enabled = False
    publish_by_default = False
    timeout = 9.0
    endpoint = "https://www.yunso.net/api/Core/search2"
    search_page = "https://www.yunso.net/index/user/s"
    decrypt_key = b"pWz1vnL1fTkOvTMW3f9M1jJWfneUIh50"

    def _decode_url(self, value: str) -> str:
        value = html.unescape(str(value or "")).strip()
        if value.casefold().startswith(("http://", "https://")):
            return value
        if not value:
            return ""
        padded = value + "=" * (-len(value) % 4)
        try:
            decoded = base64.b64decode(padded)
        except (ValueError, TypeError):
            return ""
        plain = decoded.decode("utf-8", errors="ignore").strip()
        if plain.casefold().startswith(("http://", "https://")):
            return plain
        decrypted = bytes(byte ^ self.decrypt_key[index % len(self.decrypt_key)] for index, byte in enumerate(decoded))
        return decrypted.decode("utf-8", errors="ignore").strip()

    def _search_page(self, keyword: str, page: int) -> List[SearchResultItem]:
        params = {
            "requestID": "",
            "mode": "90002",
            "scope_content": "0",
            "stype": "",
            "wd": keyword,
            "uk": "",
            "page": page,
            "limit": 20,
            "screen_filetype": "",
        }
        response = self.request(
            "POST",
            self.endpoint,
            params=params,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.yunso.net",
                "Referer": f"{self.search_page}?wd={quote(keyword)}",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        try:
            payload = response.json()
        except ValueError as error:
            raise PluginRequestError(f"[{self.name}] JSON 解析失败: {error}") from error
        if payload.get("code") != 0:
            raise PluginRequestError(f"[{self.name}] API 错误: {payload.get('msg', '未知错误')}")

        soup = BeautifulSoup(f"<div>{payload.get('data') or ''}</div>", "html.parser")
        items = []
        for card in soup.select("div.layui-card[data-qid]"):
            anchor = card.select_one("a[onclick*='open_sid']")
            if not anchor:
                continue
            link = self._decode_url(anchor.get("url"))
            password = clean_text(anchor.get("pa"))
            if not password and link:
                query = parse_qs(urlparse(link).query)
                password = next((clean_text(query.get(key, [""])[0]) for key in ("pwd", "pass", "password") if query.get(key)), "")
            header = clean_text((card.select_one(".layui-card-header") or card).get_text(" ", strip=True))
            date_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", header)
            items.append(
                self.make_item(
                    anchor.get_text(" ", strip=True),
                    link,
                    password=password,
                    datetime_value=date_match.group(0) if date_match else None,
                )
            )
        return self.finalize(items)

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        items = []
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self._search_page, keyword, page) for page in (1, 2, 3)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    items.extend(future.result())
                except Exception as error:
                    errors.append(error)
        if not items and errors:
            raise PluginRequestError(f"[{self.name}] 所有页面均失败: {errors[0]}")
        return self.finalize(items)
