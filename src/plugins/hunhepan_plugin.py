import concurrent.futures
from typing import Any, Dict, List, Tuple

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text


class HunhepanPlugin(HttpPlugin):
    name = "hunhepan"
    display_name = "混合盘搜索"
    version = "1.0.0"
    author = "pan-relay"
    description = "并行聚合混合盘、轻快盘搜、夸克吧和米搜搜"
    priority = 140
    is_enabled = False
    publish_by_default = False
    timeout = 9.0
    health_keyword = "庆余年"

    endpoints: Tuple[Tuple[str, str], ...] = (
        ("https://hunhepan.com/open/search/disk", "https://hunhepan.com/search"),
        ("https://qkpanso.com/v1/search/disk", "https://qkpanso.com/search"),
        ("https://kuake8.com/v1/search/disk", "https://kuake8.com/search"),
        ("https://www.misoso.cc/v1/search/disk", "https://www.misoso.cc/search"),
    )

    def _search_endpoint(self, endpoint: str, referer: str, keyword: str) -> List[Dict[str, Any]]:
        body = {
            "page": 1,
            "q": keyword,
            "user": "",
            "exact": False,
            "format": [],
            "share_time": "",
            "size": 30,
            "type": "",
            "exclude_user": [],
            "adv_params": {"wechat_pwd": "", "platform": "pc"},
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": referer,
        }
        if "misoso.cc" in endpoint:
            headers["Origin"] = "https://www.misoso.cc"
        response = self.request("POST", endpoint, json=body, headers=headers)
        try:
            payload = response.json()
        except ValueError as error:
            raise PluginRequestError(f"[{self.name}] JSON 解析失败: {error}") from error
        if int(payload.get("code") or 0) != 200:
            raise PluginRequestError(f"[{self.name}] API 错误: {payload.get('msg', '未知错误')}")
        return ((payload.get("data") or {}).get("list") or [])

    def search(self, keyword: str) -> List[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []

        records: List[Dict[str, Any]] = []
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.endpoints)) as executor:
            futures = [
                executor.submit(self._search_endpoint, endpoint, referer, keyword)
                for endpoint, referer in self.endpoints
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    records.extend(future.result())
                except Exception as error:
                    errors.append(error)
        if not records and errors:
            raise PluginRequestError(f"[{self.name}] 所有镜像均失败: {errors[0]}")

        items = [
            self.make_item(
                record.get("disk_name"),
                record.get("link"),
                password=record.get("disk_pass"),
                datetime_value=record.get("shared_time"),
            )
            for record in records
        ]
        return self.finalize(items)
