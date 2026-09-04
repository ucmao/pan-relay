import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.configs.app_config import DEFAULT_PLUGIN_SETTINGS
from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin
from src.plugins.duoduo_plugin import DuoduoPlugin
from src.plugins.kkv_plugin import KkvPlugin
from src.plugins.pansearch_plugin import PansearchPlugin
from src.plugins.ting77_plugin import Ting77Plugin
from src.plugins.xiaokupan_plugin import XiaokupanPlugin
from src.services.plugin_manager import PluginManager


FIXTURES = Path(__file__).parent / "fixtures" / "plugins"
REMAINING = {
    "clxiong", "duoduo", "erxiao", "jutoushe", "kkv", "labi", "muou", "shandian",
    "xb6v", "xiaokupan", "zhizhen", "huban", "pansearch", "ting77", "u3c3", "javdb",
}


class FakeResponse:
    def __init__(self, *, text="", payload=None, headers=None, status_code=200):
        self.text = text
        self._payload = payload
        self.headers = headers or {}
        self.status_code = status_code

    def json(self):
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


class RemainingPluginsTest(unittest.TestCase):
    def test_discovery_uses_code_defaults_before_database_seed_is_readable(self):
        manager = object.__new__(PluginManager)
        manager._plugins = {}
        manager._plugin_lock = threading.Lock()
        with patch("src.services.system_config_service.get_plugin_settings", return_value={}):
            manager.discover_plugins()
        plugins = {plugin.name: plugin for plugin in manager.get_all_plugins()}
        for name, enabled in DEFAULT_PLUGIN_SETTINGS.items():
            self.assertEqual(enabled, plugins[name].is_enabled, name)

    def test_queued_plugin_timeout_starts_when_execution_starts(self):
        class TimedPlugin(BasePlugin):
            is_enabled = True
            timeout = 0.1
            def __init__(self, name, delay, returns=False):
                self.name, self.delay, self.returns = name, delay, returns
            def search(self, keyword):
                time.sleep(self.delay)
                return [SearchResultItem(source="plugin:fast", title="三体", share_link="https://pan.quark.cn/s/queued", cloud_name="夸克网盘")] if self.returns else []

        manager = object.__new__(PluginManager)
        manager._plugins = {"slow": TimedPlugin("slow", 0.2), "fast": TimedPlugin("fast", 0.01, True)}
        manager._plugin_lock = threading.Lock()
        results = manager.search_all("三体", max_workers=1)
        self.assertEqual(1, len(results))

    def test_every_source_has_a_sanitized_fixture_contract(self):
        contracts = json.loads((FIXTURES / "source_contracts.json").read_text())
        self.assertEqual(REMAINING, set(contracts))
        self.assertNotIn("cookie", json.dumps(contracts).casefold())

    def test_all_remaining_plugins_are_discovered_with_synced_defaults(self):
        manager = PluginManager()
        plugins = {plugin.name: plugin for plugin in manager.get_all_plugins()}
        self.assertTrue(REMAINING.issubset(plugins))
        for name in REMAINING:
            self.assertEqual(DEFAULT_PLUGIN_SETTINGS[name], plugins[name].publish_by_default, name)

    def test_all_remaining_plugins_accept_empty_keyword(self):
        manager = PluginManager()
        plugins = {plugin.name: plugin for plugin in manager.get_all_plugins()}
        for name in REMAINING:
            with self.subTest(plugin=name):
                self.assertEqual(plugins[name].search(""), [])

    def test_wordpress_detail_fixture(self):
        plugin = KkvPlugin()
        search_html = (FIXTURES / "detail_search.html").read_text()
        detail_html = (FIXTURES / "detail_page.html").read_text()
        plugin.request = lambda method, url, **kwargs: FakeResponse(text=detail_html if "/entry/" in url else search_html)
        results = plugin.search("三体")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].password, "a1b2")

    def test_maccms_search_and_detail_fixtures(self):
        plugin = DuoduoPlugin()
        search_html = (FIXTURES / "maccms_search.html").read_text()
        detail_html = (FIXTURES / "maccms_detail.html").read_text()
        plugin.request = lambda method, url, **kwargs: FakeResponse(text=detail_html if "/detail/" in url else search_html)
        results = plugin.search("三体")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].share_link, "https://pan.quark.cn/s/redacted42")

    def test_pansearch_json_fixture(self):
        plugin = PansearchPlugin()
        payload = json.loads((FIXTURES / "pansearch.json").read_text())
        plugin._get_build_id = lambda force=False: "redacted-build"
        plugin.request = lambda *args, **kwargs: FakeResponse(payload=payload)
        results = plugin.search("三体")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].share_link, "https://pan.quark.cn/s/redacted42")

    def test_ting77_token_redirect_fixture(self):
        plugin = Ting77Plugin()
        search_html = (FIXTURES / "ting77_search.html").read_text()
        def request(method, url, **kwargs):
            if url.endswith("/search"):
                return FakeResponse(text=search_html)
            if url.endswith("/api/link/token"):
                return FakeResponse(payload={"code": 0, "data": {"token": "redacted", "ts": "123"}})
            cloud_type = kwargs["params"]["type"]
            link = "https://pan.quark.cn/s/redacted42" if cloud_type == "quark" else "https://pan.baidu.com/s/redacted42?pwd=a1b2"
            return FakeResponse(headers={"Location": link}, status_code=302)
        plugin.request = request
        results = plugin.search("三体")
        self.assertEqual(len(results), 2)

    def test_xiaokupan_seroval_decoder(self):
        scalar = lambda value: {"t": 1, "s": value}
        obj = lambda keys, values: {"t": 10, "p": {"k": keys, "v": values}}
        item = obj(["url", "note", "password", "datetime"], [scalar("https://pan.quark.cn/s/redacted42"), scalar("三体 4K"), scalar(""), scalar("2026-01-02T03:04:05Z")])
        merged = obj(["quark"], [{"t": 9, "a": [item]}])
        root = obj(["result"], [obj(["searchResults"], [obj(["merged_by_type"], [merged])])])
        plugin = XiaokupanPlugin()
        plugin._request_search = lambda keyword, function_id: root
        results = plugin.search("三体")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "三体 4K")


if __name__ == "__main__":
    unittest.main()
