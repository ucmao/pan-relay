from typing import List

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text


class IkanTVPlugin(HttpPlugin):
    name = "ikantv"
    display_name = "爱看网盘搜索"
    version = "1.0.0"
    author = "pan-relay"
    description = "爱看公开网盘聚合 API"
    priority = 160
    is_enabled = False
    publish_by_default = False
    timeout = 8.0
    endpoint = "https://api.naspt.vip/api/open/pansou/search"
    allowed_types = {
        "quark", "uc", "baidu", "aliyun", "guangya", "xunlei",
        "tianyi", "115", "123", "mobile", "pikpak", "magnet", "ed2k",
    }

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        response = self.request(
            "GET",
            self.endpoint,
            params={"kw": keyword, "limit": 50},
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://api.naspt.vip/",
            },
        )
        try:
            payload = response.json()
        except ValueError as error:
            raise PluginRequestError(f"[{self.name}] JSON 解析失败: {error}") from error
        if payload.get("code") != 0:
            raise PluginRequestError(f"[{self.name}] API 错误: {payload.get('message', '未知错误')}")

        items = []
        for record in payload.get("data") or []:
            title = record.get("title") or record.get("content")
            for link in record.get("links") or []:
                if clean_text(link.get("type")).lower() not in self.allowed_types:
                    continue
                items.append(
                    self.make_item(
                        link.get("work_title") or title,
                        link.get("url"),
                        password=link.get("password"),
                        datetime_value=link.get("datetime") or record.get("datetime"),
                    )
                )
        return self.finalize(items)
