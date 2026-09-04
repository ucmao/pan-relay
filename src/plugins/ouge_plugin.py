from typing import List

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text


class OugePlugin(HttpPlugin):
    name = "ouge"
    display_name = "欧歌资源搜索"
    version = "1.0.0"
    author = "pan-relay"
    description = "欧歌影视资源 JSON API"
    priority = 130
    is_enabled = False
    publish_by_default = False
    timeout = 7.0
    endpoint = "https://woog.nxog.eu.org/api.php/provide/vod"

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        response = self.request(
            "GET",
            self.endpoint,
            params={"ac": "detail", "wd": keyword},
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://woog.nxog.eu.org/",
            },
        )
        try:
            payload = response.json()
        except ValueError as error:
            raise PluginRequestError(f"[{self.name}] JSON 解析失败: {error}") from error
        if int(payload.get("code") or 0) != 1:
            raise PluginRequestError(f"[{self.name}] API 错误: {payload.get('msg', '未知错误')}")

        items = []
        for record in payload.get("list") or []:
            title = record.get("vod_name")
            providers = str(record.get("vod_down_from") or "").split("$$$")
            links = str(record.get("vod_down_url") or "").split("$$$")
            for _provider, link in zip(providers, links):
                items.append(self.make_item(title, link))
        return self.finalize(items)
