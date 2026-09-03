import json
import unittest
from unittest.mock import MagicMock, patch

from app import app
from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin
from src.services.plugin_manager import PluginManager, plugin_manager
from src.services.search_service import search_public_resources


class DummyTestPlugin(BasePlugin):
    name = "dummy_test_plugin"
    display_name = "测试模拟插件"
    priority = 110
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
        # 注册模拟插件
        self.dummy = DummyTestPlugin()
        self.mgr.register_plugin(self.dummy)

    def tearDown(self):
        with self.mgr._plugin_lock:
            self.mgr._plugins.pop("dummy_test_plugin", None)

    def test_plugin_discovery_and_metadata(self):
        # 验证自动发现了内置的 sample_scraper 插件
        scraper = self.mgr.get_plugin("sample_scraper")
        self.assertIsNotNone(scraper)
        self.assertEqual("sample_scraper", scraper.name)
        self.assertEqual("参考爬虫插件", scraper.display_name)

        # 验证元数据字典
        info = scraper.to_dict()
        self.assertEqual("sample_scraper", info["name"])
        self.assertTrue("priority" in info)
        self.assertTrue("is_enabled" in info)

    def test_plugin_enable_disable_toggle(self):
        # 1. 停用
        self.mgr.disable_plugin("dummy_test_plugin")
        self.assertFalse(self.dummy.is_enabled)
        enabled_names = [p.name for p in self.mgr.get_enabled_plugins()]
        self.assertNotIn("dummy_test_plugin", enabled_names)

        # 2. 启用
        self.mgr.enable_plugin("dummy_test_plugin")
        self.assertTrue(self.dummy.is_enabled)
        enabled_names = [p.name for p in self.mgr.get_enabled_plugins()]
        self.assertIn("dummy_test_plugin", enabled_names)

    def test_plugin_search_all_and_error_isolation(self):
        self.dummy.is_enabled = True

        # 1. 正常搜索
        results = self.mgr.search_all("繁花")
        found = any("繁花 插件专属4K" in item.title for item in results)
        self.assertTrue(found)

        # 2. 插件异常隔离（触发 error 不抛出异常，优雅返回空）
        safe_res = self.mgr.search_all("error")
        self.assertIsInstance(safe_res, list)

    def test_search_service_aggregation_includes_plugins(self):
        # 验证 search_public_resources 能够顺利并行收集插件结果
        success, msg, results = search_public_resources("繁花", limit=50)
        self.assertTrue(success)
        self.assertIsInstance(results, list)
        # 检查是否包含插件产生的数据源
        has_plugin_source = any("plugin:" in r.get("source", "") for r in results)
        self.assertTrue(has_plugin_source)

    def test_plugin_routes_api(self):
        # 1. GET /api/plugins
        resp = self.client.get("/api/plugins")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["total"], 1)

        # 2. POST /api/plugins/<name>/toggle
        toggle_resp = self.client.post("/api/plugins/dummy_test_plugin/toggle", json={
            "is_enabled": False
        })
        self.assertEqual(200, toggle_resp.status_code)
        toggle_data = toggle_resp.get_json()
        self.assertFalse(toggle_data["is_enabled"])

        # 恢复状态
        self.client.post("/api/plugins/dummy_test_plugin/toggle", json={"is_enabled": True})

        # 3. POST /api/plugins/<name>/test
        test_resp = self.client.post("/api/plugins/dummy_test_plugin/test", json={
            "keyword": "流浪地球"
        })
        self.assertEqual(200, test_resp.status_code)
        test_data = test_resp.get_json()
        self.assertTrue(test_data["success"])
        self.assertEqual(1, test_data["count"])

        # 4. GET /api/plugins/<name>/health
        health_resp = self.client.get("/api/plugins/dummy_test_plugin/health")
        self.assertEqual(200, health_resp.status_code)
        health_data = health_resp.get_json()
        self.assertTrue(health_data["healthy"])


if __name__ == "__main__":
    unittest.main()
