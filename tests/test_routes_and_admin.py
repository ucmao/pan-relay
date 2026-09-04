import unittest
from unittest.mock import MagicMock, Mock, patch
import requests

from app import app
from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin
from src.services.api_config_service import test_single_api
from src.services.plugin_manager import PluginManager
from src.services.system_config_service import (
    ALLOW_EXCEL_DOWNLOAD_KEY,
    get_allow_excel_download_config,
    get_plugin_settings,
    get_search_scheduler_config,
    is_excel_download_enabled,
    save_allow_excel_download_config,
    save_search_scheduler_config,
)
from src.services.telegram_channel_service import (
    add_tg_channel,
    delete_tg_channel,
    get_tg_channel_items,
    save_tg_channel_health,
    set_tg_channel_enabled,
)
from src.services.telegram_search_service import test_telegram_connection
from src.utils.auth_utils import create_jwt_token
from src.utils.test_keywords import build_test_keywords


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


class RoutesAndAdminTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.token = create_jwt_token()

    # --- Phase 1: 路由基础与 CRUD 分享操作测试 ---

    @patch("src.routes.search_routes.create_share")
    def test_create_share_route_success_and_failure(self, mock_create_share):
        resp = self.client.post("/create_share", json={})
        self.assertEqual(400, resp.status_code)

        mock_create_share.return_value = {"share_url": "https://pan.quark.cn/s/123", "file_id": "fid1"}
        resp = self.client.post("/create_share", json={"title": "测试资源", "share_url": "https://pan.quark.cn/s/test"})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

        mock_create_share.return_value = None
        resp = self.client.post("/create_share", json={"title": "测试失败资源", "share_url": "https://pan.quark.cn/s/fail"})
        self.assertEqual(500, resp.status_code)
        data = resp.get_json()
        self.assertFalse(data.get("success"))

    @patch("src.routes.search_routes.del_share")
    def test_del_share_route_success_and_failure(self, mock_del_share):
        resp = self.client.post("/del_share", json={})
        self.assertEqual(400, resp.status_code)

        mock_del_share.return_value = True
        resp = self.client.post("/del_share", json={"share_url": "https://pan.quark.cn/s/test", "file_id": "fid1"})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

        mock_del_share.return_value = False
        resp = self.client.post("/del_share", json={"share_url": "https://pan.quark.cn/s/fail", "file_id": "fid2"})
        self.assertEqual(500, resp.status_code)

    def test_token_required_auth_behavior(self):
        resp = self.client.get("/admin/api/resources")
        self.assertEqual(401, resp.status_code)

        resp_page = self.client.get("/admin/resources")
        self.assertEqual(302, resp_page.status_code)

        self.client.set_cookie("token", self.token)
        resp_authed = self.client.get("/admin/api/resources")
        self.assertNotEqual(401, resp_authed.status_code)

    def test_login_empty_form_handling(self):
        resp = self.client.post("/admin", data={})
        self.assertEqual(200, resp.status_code)
        self.assertIn("账号或密码不能为空", resp.get_data(as_text=True))

    def test_resources_page_renders_template(self):
        self.client.set_cookie("token", self.token)
        resp = self.client.get("/admin/resources")
        self.assertEqual(200, resp.status_code)
        html = resp.get_data(as_text=True)
        self.assertIn("我的资源管理", html)

    # --- 后台 TG、API 与插件配置控制台测试 ---

    def test_admin_sources_workspace_tab_switch(self):
        self.client.set_cookie("token", self.token)
        resp = self.client.get("/admin/sources?tab=plugins")
        self.assertEqual(200, resp.status_code)
        html = resp.get_data(as_text=True)
        self.assertIn('data-tab-target="plugins"', html)

        resp_tg = self.client.get("/admin/sources?tab=telegram")
        self.assertEqual(200, resp_tg.status_code)
        self.assertIn('data-tab-target="telegram"', resp_tg.get_data(as_text=True))

    @patch("src.routes.api_config_routes.set_api_enabled_in_db")
    def test_toggle_api_enabled_allows_enabling_abnormal_api(self, mock_set_enabled):
        self.client.set_cookie("token", self.token)
        mock_set_enabled.return_value = (True, "API 启用状态更新成功")

        response = self.client.put("/admin/api/configs/1/enabled", json={"is_enabled": True})
        self.assertEqual(200, response.status_code)
        mock_set_enabled.assert_called_once_with(1, True)


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

    def test_tg_search_config_get_and_save(self):
        cfg = get_search_scheduler_config()["tg"]
        self.assertIn("enabled", cfg)

        new_payload = {"enabled": False, "proxy": "socks5://127.0.0.1:1080", "timeout": 15, "max_workers": 2}
        self.assertTrue(save_search_scheduler_config({"api": {"timeout": 10, "max_workers": 8}, "tg": new_payload, "plugin": {"timeout": 10, "max_workers": 6}}))
        saved = get_search_scheduler_config()["tg"]
        self.assertFalse(saved["enabled"])
        save_search_scheduler_config({"api": {"timeout": 10, "max_workers": 8}, "tg": {"enabled": True, "proxy": "", "timeout": 10, "max_workers": 4}, "plugin": {"timeout": 10, "max_workers": 6}})

    def test_tg_channel_list_crud_and_health(self):
        channel = "codex_test_channel"
        delete_tg_channel(channel)
        try:
            success, _, item = add_tg_channel(f"https://t.me/{channel}", is_enabled=False)
            self.assertTrue(success)
            self.assertEqual(channel, item["channel"])

            self.assertTrue(save_tg_channel_health(channel, {
                "success": False, "message": "连接超时", "latency_ms": 1200, "count": 0,
            }))
        finally:
            delete_tg_channel(channel)

    def test_admin_plugins_api_endpoints(self):
        self.client.set_cookie("token", self.token)

        resp = self.client.get("/admin/api/plugins")
        self.assertEqual(200, resp.status_code)

        toggle_resp = self.client.post("/admin/api/plugins/test_mock_plugin/toggle", json={"is_enabled": False})
        self.assertEqual(200, toggle_resp.status_code)

        health_resp = self.client.get("/admin/api/plugins/test_mock_plugin/health")
        self.assertEqual(200, health_resp.status_code)


class ApiConfigKeywordRotationTest(unittest.TestCase):
    def setUp(self):
        self.config = {
            "name": "测试源",
            "url": "https://example.com/search?name=[[keyword]]",
            "method": "GET",
            "request": "",
            "response": "data[*].[name, url]",
        }

    @staticmethod
    def _response(payload, status_code=200):
        res = Mock()
        res.status_code = status_code
        res.text = payload
        return res

    def test_default_keywords_deduplication(self):
        self.assertEqual(["自定义", "仙逆", "逆袭", "总裁"], build_test_keywords("自定义,仙逆"))

    @patch("src.services.api_config_service.requests.get")
    def test_detailed_result_reports_no_data(self, mock_get):
        mock_get.side_effect = [self._response('{"data":[]}')] * 3
        result = test_single_api("未知ID", self.config, return_details=True)
        self.assertEqual("no_data", result[5])
        self.assertEqual(0, result[6])


class ExcelDownloadConfigTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.token = create_jwt_token()

    @patch("src.services.system_config_service.get_config_value")
    def test_default_allow_excel_download(self, mock_get_config):
        mock_get_config.return_value = None
        config = get_allow_excel_download_config()
        self.assertTrue(config["enabled"])
        self.assertTrue(is_excel_download_enabled())

    @patch("src.routes.system_config_routes.save_allow_excel_download_config")
    def test_update_allow_excel_download_api(self, mock_save_config):
        mock_save_config.return_value = True
        self.client.set_cookie('token', self.token)
        response = self.client.put("/admin/api/allow-excel-download-config", json={"enabled": False})
        self.assertEqual(200, response.status_code)
        mock_save_config.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
