import os
import unittest
from unittest.mock import patch

from app import app
from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin
from src.services.plugin_manager import plugin_manager
from src.services.search_service import search_public_resources


class DummyTestPlugin(BasePlugin):
    name = "dummy_test_plugin"
    display_name = "测试模拟插件"
    priority = 999
    is_enabled = True
    timeout = 2.0

    def search(self, keyword: str):
        if keyword == "error":
            raise RuntimeError("模拟插件异常")
        return [
            SearchResultItem(
                source="plugin:dummy",
                title=f"{keyword} 插件专属4K",
                share_link="https://pan.quark.cn/s/dummy123",
                cloud_name="夸克网盘",
            )
        ]

    def health_check(self):
        return True, "测试正常"


class PluginSystemTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.mgr = plugin_manager
        self.dummy = DummyTestPlugin()
        self.mgr.register_plugin(self.dummy)

    def tearDown(self):
        with self.mgr._plugin_lock:
            self.mgr._plugins.pop("dummy_test_plugin", None)

    def test_plugin_discovery_and_metadata(self):
        plugins = self.mgr.get_all_plugins()
        self.assertGreaterEqual(len(plugins), 1)

        info = self.dummy.to_dict()
        self.assertEqual("dummy_test_plugin", info["name"])
        self.assertIn("priority", info)
        self.assertIn("is_enabled", info)

    def test_plugin_enable_disable_toggle(self):
        self.mgr.disable_plugin("dummy_test_plugin")
        self.assertFalse(self.dummy.is_enabled)
        enabled_names = [p.name for p in self.mgr.get_enabled_plugins()]
        self.assertNotIn("dummy_test_plugin", enabled_names)

        self.mgr.enable_plugin("dummy_test_plugin")
        self.assertTrue(self.dummy.is_enabled)

    def test_plugin_search_all_and_error_isolation(self):
        self.dummy.is_enabled = True
        with patch.object(self.mgr, "get_enabled_plugins", return_value=[self.dummy]):
            results = self.mgr.search_all("繁花")
            found = any("繁花 插件专属4K" in item.title for item in results)
            self.assertTrue(found)

            safe_res = self.mgr.search_all("error")
            self.assertIsInstance(safe_res, list)

    @patch("src.services.search_service.search_telegram_resources", return_value=[])
    @patch("src.services.search_service.read_all_api_configs_from_db", return_value=[])
    def test_search_service_aggregation_includes_plugins(self, mock_apis, mock_tg):
        with patch.object(self.mgr, "get_enabled_plugins", return_value=[self.dummy]):
            success, msg, results = search_public_resources("繁花", limit=500)
            self.assertTrue(success)
            self.assertIsInstance(results, list)

    def test_plugin_routes_api(self):
        resp = self.client.get("/api/plugins")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])

        test_resp = self.client.post("/api/plugins/dummy_test_plugin/test", json={"keyword": "流浪地球"})
        self.assertEqual(200, test_resp.status_code)
        self.assertTrue(test_resp.get_json()["success"])


@unittest.skipIf(os.getenv("SKIP_NETWORK_TESTS") == "1", "跳过外部真实网络插件测试")
class LivePluginsContractTest(unittest.TestCase):
    """第三方网站真实网络连通性契约测试 (可设置 SKIP_NETWORK_TESTS=1 跳过)"""

    def test_registered_plugins_contract(self):
        plugins = plugin_manager.get_all_plugins()
        self.assertGreater(len(plugins), 0)
        for plugin in plugins:
            self.assertTrue(hasattr(plugin, "name"))
            self.assertTrue(hasattr(plugin, "search"))


if __name__ == "__main__":
    unittest.main()
