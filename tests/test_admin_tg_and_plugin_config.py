import json
import unittest
from unittest.mock import MagicMock, patch

from app import app
from src.plugins.base_plugin import BasePlugin
from src.services.plugin_manager import PluginManager, plugin_manager
from src.services.system_config_service import (
    get_plugin_settings,
    get_tg_search_config,
    save_plugin_status,
    save_tg_search_config,
)
from src.services.telegram_search_service import (
    search_telegram_resources,
    test_telegram_connection,
)
from src.utils.auth_utils import create_jwt_token


class MockPlugin(BasePlugin):
    name = "test_mock_plugin"
    display_name = "单元测试Mock插件"
    version = "1.0.0"
    author = "tester"
    description = "用于测试插件持久化与管理接口"
    priority = 120
    timeout = 3.0
    is_enabled = True

    def search(self, keyword: str):
        return []

    def health_check(self):
        return True, "Mock正常"


class AdminTgAndPluginConfigTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.token = create_jwt_token()
        self.mgr = PluginManager()
        self.mock_plugin = MockPlugin()
        self.mgr.register_plugin(self.mock_plugin)

    def tearDown(self):
        with self.mgr._plugin_lock:
            self.mgr._plugins.pop("test_mock_plugin", None)

    # --- TG 搜索配置测试 ---

    def test_tg_search_config_get_and_save(self):
        # 1. 默认配置应包含基础字段
        cfg = get_tg_search_config()
        self.assertIn("enabled", cfg)
        self.assertIn("channels", cfg)
        self.assertIn("proxy", cfg)
        self.assertIn("timeout", cfg)

        # 2. 保存新配置并验证读取
        new_payload = {
            "enabled": False,
            "channels": "testchan1, @testchan2",
            "proxy": "socks5://127.0.0.1:1080",
            "timeout": 15,
            "max_workers": 2,
        }
        ok = save_tg_search_config(new_payload)
        self.assertTrue(ok)

        saved = get_tg_search_config()
        self.assertFalse(saved["enabled"])
        self.assertEqual(["testchan1", "testchan2"], saved["channels"])
        self.assertEqual("socks5://127.0.0.1:1080", saved["proxy"])
        self.assertEqual(15, saved["timeout"])
        self.assertEqual(2, saved["max_workers"])

        # 恢复默认启用状态
        save_tg_search_config({"enabled": True, "channels": ["tgsearchers7", "tgsearchers3"], "proxy": ""})

    def test_tg_search_disabled_returns_empty(self):
        save_tg_search_config({"enabled": False, "channels": ["tgsearchers7"], "proxy": ""})
        res = search_telegram_resources("流浪地球")
        self.assertEqual([], res)

        # 恢复
        save_tg_search_config({"enabled": True, "channels": ["tgsearchers7"], "proxy": ""})

    @patch("src.services.telegram_search_service.search_telegram_channel")
    def test_test_telegram_connection(self, mock_search):
        mock_search.return_value = [
            ("tg", "测试资源1", "https://pan.quark.cn/s/sample1", "夸克网盘")
        ]
        result = test_telegram_connection("tgsearchers7", keyword="测试", proxy="", timeout=5)
        self.assertTrue(result["success"])
        self.assertEqual("tgsearchers7", result["channel"])
        self.assertEqual(1, result["count"])
        self.assertGreaterEqual(result["latency_ms"], 0)
        self.assertEqual(1, len(result["results"]))

    def test_admin_tg_config_api_unauthorized(self):
        resp = self.client.get("/admin/api/tg-search-config")
        self.assertEqual(401, resp.status_code)

        resp = self.client.put("/admin/api/tg-search-config", json={"enabled": True})
        self.assertEqual(401, resp.status_code)

        resp = self.client.post("/admin/api/tg-search-config/test", json={"channel": "tgsearchers7"})
        self.assertEqual(401, resp.status_code)

    def test_admin_tg_config_api_authorized(self):
        self.client.set_cookie("token", self.token)

        # 1. GET
        get_resp = self.client.get("/admin/api/tg-search-config")
        self.assertEqual(200, get_resp.status_code)
        data = get_resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("config", data)

        # 2. PUT
        put_resp = self.client.put("/admin/api/tg-search-config", json={
            "enabled": True,
            "channels": "chanA, chanB",
            "proxy": "http://127.0.0.1:7890",
            "timeout": 12,
            "max_workers": 3
        })
        self.assertEqual(200, put_resp.status_code)
        put_data = put_resp.get_json()
        self.assertTrue(put_data["success"])
        self.assertEqual(["chanA", "chanB"], put_data["config"]["channels"])

    # --- 插件配置与持久化测试 ---

    def test_plugin_persistence_save_and_load(self):
        # 停用
        self.mgr.disable_plugin("test_mock_plugin")
        self.assertFalse(self.mock_plugin.is_enabled)

        # 验证数据库中持久化
        settings = get_plugin_settings()
        self.assertIn("test_mock_plugin", settings)
        self.assertFalse(settings["test_mock_plugin"]["is_enabled"])

        # 启用
        self.mgr.enable_plugin("test_mock_plugin")
        self.assertTrue(self.mock_plugin.is_enabled)
        settings = get_plugin_settings()
        self.assertTrue(settings["test_mock_plugin"]["is_enabled"])

    def test_admin_plugins_page_unauthorized(self):
        # 未登录访问应返回 302 重定向到登录页
        resp = self.client.get("/admin/plugins")
        self.assertEqual(302, resp.status_code)

    def test_admin_plugins_page_authorized(self):
        self.client.set_cookie("token", self.token)
        resp = self.client.get("/admin/plugins")
        self.assertEqual(200, resp.status_code)
        html = resp.get_data(as_text=True)
        self.assertIn("插件扩展管理", html)
        self.assertIn("plugin_config.js", html)

    def test_admin_plugins_api_endpoints(self):
        self.client.set_cookie("token", self.token)

        # 1. GET /admin/api/plugins
        resp = self.client.get("/admin/api/plugins")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        plugin_names = [p["name"] for p in data["plugins"]]
        self.assertIn("test_mock_plugin", plugin_names)

        # 2. POST toggle
        toggle_resp = self.client.post("/admin/api/plugins/test_mock_plugin/toggle", json={
            "is_enabled": False
        })
        self.assertEqual(200, toggle_resp.status_code)
        self.assertFalse(toggle_resp.get_json()["is_enabled"])
        self.assertFalse(self.mock_plugin.is_enabled)

        # 3. POST test
        test_resp = self.client.post("/admin/api/plugins/test_mock_plugin/test", json={
            "keyword": "测试词"
        })
        self.assertEqual(200, test_resp.status_code)
        self.assertTrue(test_resp.get_json()["success"])

        # 4. GET health
        health_resp = self.client.get("/admin/api/plugins/test_mock_plugin/health")
        self.assertEqual(200, health_resp.status_code)
        self.assertTrue(health_resp.get_json()["healthy"])

        # 5. POST reload
        reload_resp = self.client.post("/admin/api/plugins/reload")
        self.assertEqual(200, reload_resp.status_code)
        self.assertTrue(reload_resp.get_json()["success"])

        # 6. POST enable-all & disable-all
        enable_resp = self.client.post("/admin/api/plugins/enable-all")
        self.assertEqual(200, enable_resp.status_code)
        self.assertTrue(self.mock_plugin.is_enabled)

        disable_resp = self.client.post("/admin/api/plugins/disable-all")
        self.assertEqual(200, disable_resp.status_code)
        self.assertFalse(self.mock_plugin.is_enabled)

        # 恢复状态
        self.mgr.enable_plugin("test_mock_plugin")


if __name__ == "__main__":
    unittest.main()
