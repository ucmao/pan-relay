import re
import threading
from urllib.parse import quote

from src.models.search_item import SearchResultItem
from src.plugins.http_plugin import HttpPlugin, PluginRequestError, clean_text


class XiaokupanPlugin(HttpPlugin):
    name = "xiaokupan"
    display_name = "小酷盘"
    description = "动态发现 TanStack server function 的聚合资源"
    priority = 155
    is_enabled = False
    publish_by_default = True
    timeout = 10.0
    base_url = "https://xiaokupan.com"
    initial_function_id = "ffb7ba806a267ced7478dc27716e79ea729a98a801af2ac9c3647bdaca91af78"

    def __init__(self):
        super().__init__()
        self._function_id = self.initial_function_id
        self._lock = threading.Lock()

    def _discover(self):
        with self._lock:
            home = self.request("GET", self.base_url + "/", retries=0)
            asset = re.search(r"/assets/index-[A-Za-z0-9_-]+\.js", home.text)
            if not asset:
                raise PluginRequestError("[xiaokupan] 首页缺少入口脚本")
            script = self.request("GET", self.base_url + asset.group(0), headers={"Referer": self.base_url + "/"}, retries=0).text
            route_index = script.find("/s/$query")
            hashes = re.findall(r"[a-f0-9]{64}", script[max(0, route_index - 2048):route_index]) if route_index >= 0 else []
            if not hashes:
                raise PluginRequestError("[xiaokupan] 搜索接口标识发现失败")
            self._function_id = hashes[-1]
            return self._function_id

    @staticmethod
    def _payload(keyword):
        return {"t": {"t": 10, "i": 0, "p": {"k": ["data"], "v": [{"t": 10, "i": 1, "p": {"k": ["query"], "v": [{"t": 1, "s": keyword}]}, "o": 0}]}, "o": 0}, "f": 63, "m": []}

    def _request_search(self, keyword, function_id):
        response = self.request(
            "GET", f"{self.base_url}/_serverFn/{function_id}", params={"payload": __import__("json").dumps(self._payload(keyword), separators=(",", ":"))},
            headers={"Accept": "application/x-tss-framed, application/x-ndjson, application/json", "Origin": self.base_url, "Referer": f"{self.base_url}/s/{quote(keyword, safe='')}", "x-tsr-serverFn": "true"}, retries=0,
        )
        return response.json()

    @staticmethod
    def _decode(root):
        references = {}
        def collect(node):
            if not isinstance(node, dict):
                return
            if "i" in node:
                references[node["i"]] = node
            for child in ((node.get("p") or {}).get("v") or []):
                collect(child)
            for child in node.get("a") or []:
                collect(child)
        collect(root)
        def resolve(node):
            for _ in range(16):
                if not isinstance(node, dict) or node.get("t") != 4:
                    break
                node = references.get(node.get("s"))
            return node
        def value(node, key):
            node = resolve(node)
            props = (node or {}).get("p") or {}
            try:
                return resolve(props.get("v", [])[props.get("k", []).index(key)])
            except (ValueError, IndexError):
                return None
        merged = value(value(value(root, "result"), "searchResults"), "merged_by_type")
        return resolve(merged), resolve, value

    def search(self, keyword: str) -> list[SearchResultItem]:
        keyword = clean_text(keyword)
        if not keyword:
            return []
        try:
            root = self._request_search(keyword, self._function_id)
        except Exception:
            root = self._request_search(keyword, self._discover())
        merged, resolve, value = self._decode(root)
        props = (merged or {}).get("p") or {}
        if not props:
            raise PluginRequestError("[xiaokupan] 响应缺少 merged_by_type")
        items = []
        for array in props.get("v") or []:
            for node in (resolve(array) or {}).get("a") or []:
                link_node = value(node, "url") or {}
                note_node = value(node, "note") or {}
                password_node = value(node, "password") or {}
                datetime_node = value(node, "datetime") or {}
                items.append(self.make_item(note_node.get("s"), link_node.get("s"), password=password_node.get("s"), datetime_value=datetime_node.get("s")))
        return self.finalize(items)
