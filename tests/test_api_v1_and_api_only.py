import os
import unittest
from unittest.mock import patch, MagicMock

from app import app
from src.services.system_config_service import (
    get_api_mode_config,
    save_api_mode_config,
    save_search_api_scope,
    save_transfer_api_key,
    is_api_only_enabled,
    is_frontend_enabled,
    is_admin_ui_enabled,
)
from src.utils.auth_utils import create_jwt_token


class ApiV1AndApiOnlyTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.token = create_jwt_token()

    def tearDown(self):
        # 恢复默认系统配置
        save_api_mode_config(api_only=False, enable_frontend=True, enable_admin_ui=True, search_scope="own", transfer_api_key="")
        os.environ.pop("API_ONLY", None)
        os.environ.pop("PAN_RELAY_API_ONLY", None)
        os.environ.pop("ENABLE_FRONTEND", None)
        os.environ.pop("ENABLE_ADMIN_UI", None)
        os.environ.pop("SEARCH_API_SCOPE", None)
        os.environ.pop("TRANSFER_API_KEY", None)

    # --- 1. 系统配置与环境变量测试 ---

    def test_api_mode_config_defaults_and_saving(self):
        save_api_mode_config(api_only=False, enable_frontend=True, enable_admin_ui=True, search_scope="own", transfer_api_key="secret123")
        config = get_api_mode_config()
        self.assertFalse(config["api_only"])
        self.assertTrue(config["enable_frontend"])
        self.assertTrue(config["enable_admin_ui"])
        self.assertEqual("own", config["search_scope"])
        self.assertEqual("secret123", config["transfer_api_key"])

        save_api_mode_config(api_only=True, enable_frontend=True, enable_admin_ui=False, search_scope="all", transfer_api_key="")
        config = get_api_mode_config()
        self.assertTrue(config["api_only"])
        self.assertFalse(config["enable_frontend"])  # api_only=True 自动覆盖 enable_frontend 为 False
        self.assertFalse(config["enable_admin_ui"])
        self.assertEqual("all", config["search_scope"])

    def test_api_mode_config_environment_variables(self):
        os.environ["API_ONLY"] = "1"
        self.assertTrue(is_api_only_enabled())
        self.assertFalse(is_frontend_enabled())

        os.environ.pop("API_ONLY")
        os.environ["ENABLE_FRONTEND"] = "false"
        self.assertFalse(is_frontend_enabled())

        os.environ["ENABLE_ADMIN_UI"] = "0"
        self.assertFalse(is_admin_ui_enabled())

    # --- 2. REST API v1 节点与作用域/密钥测试 ---

    def test_api_v1_status(self):
        resp = self.client.get("/api/v1/status")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual("pan-relay", data["service"])
        self.assertIn("endpoints", data)

    @patch("src.routes.api_v1_routes.search_in_database")
    @patch("src.routes.api_v1_routes.search_public_resources")
    def test_api_v1_search_scope(self, mock_public_search, mock_db_search):
        mock_db_search.return_value = [{"title": "站长私有资源", "share_link": "https://pan.quark.cn/s/own1", "cloud_name": "夸克网盘"}]
        mock_public_search.return_value = (True, "成功", [{"title": "全网资源", "share_link": "https://pan.quark.cn/s/all1"}])

        # 1. 明确指定 scope=own 纯站长收益库查询
        resp = self.client.get("/api/v1/search?keyword=黑神话&scope=own")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual("own", data["scope"])
        self.assertEqual(1, data["total"])
        mock_db_search.assert_called_once()
        mock_public_search.assert_not_called()

        mock_db_search.reset_mock()
        mock_public_search.reset_mock()

        # 2. 明确指定 scope=all 全网聚合查询
        resp = self.client.get("/api/v1/search?keyword=黑神话&scope=all")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual("all", data["scope"])
        mock_public_search.assert_called_once()

    @patch("src.routes.api_v1_routes.resolve_view_url")
    def test_api_v1_transfer_with_api_key_protection(self, mock_resolve):
        mock_resolve.return_value = {
            "url": "https://pan.quark.cn/s/new123",
            "mode": "temp_share",
            "netdisk_name": "夸克网盘",
        }
        # 设置转存 Key
        save_transfer_api_key("my_secret_key")

        # 1. 未传 Header/Key -> 401 拦截
        payload = {"url": "https://pan.quark.cn/s/raw123", "title": "电影标题"}
        resp = self.client.post("/api/v1/transfer", json=payload)
        self.assertEqual(401, resp.status_code)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("API Key 校验失败", data["message"])

        # 2. 传入错误 Header -> 401 拦截
        resp = self.client.post("/api/v1/transfer", json=payload, headers={"X-API-Key": "wrong_key"})
        self.assertEqual(401, resp.status_code)

        # 3. 传入正确 Header -> 200 成功
        resp = self.client.post("/api/v1/transfer", json=payload, headers={"X-API-Key": "my_secret_key"})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual("https://pan.quark.cn/s/new123", data["data"]["url"])

    @patch("src.routes.api_v1_routes.check_link")
    def test_api_v1_link_check(self, mock_check):
        mock_check.return_value = {"state": 1, "summary": "链接有效"}
        resp = self.client.post("/api/v1/link/check", json={"url": "https://pan.quark.cn/s/123"})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])

    def test_api_v1_resources(self):
        resp = self.client.get("/api/v1/resources?page=1&page_size=5")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])

    def test_api_v1_docs(self):
        # 浏览器访问 GET /api/v1/docs -> 返回 HTML 网页
        resp = self.client.get("/api/v1/docs", headers={"Accept": "text/html"})
        self.assertEqual(200, resp.status_code)
        self.assertIn("Pan-Relay 开发者 API", resp.get_data(as_text=True))

        # 独立路径 GET /docs -> 返回 HTML 网页
        resp_docs = self.client.get("/docs")
        self.assertEqual(200, resp_docs.status_code)
        self.assertIn("Pan-Relay 开发者 API", resp_docs.get_data(as_text=True))

        # API 客户端请求 format=json -> 返回 JSON
        resp_json = self.client.get("/api/v1/docs?format=json")
        self.assertEqual(200, resp_json.status_code)
        data = resp_json.get_json()
        self.assertIn("endpoints", data)


    # --- 3. UI 屏蔽与 API_ONLY 模式中间件拦截测试 ---

    def test_frontend_disabled_interception(self):
        # 开启 API_ONLY 屏蔽前台
        os.environ["API_ONLY"] = "1"
        resp = self.client.get("/")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn("前台 Web UI 当前已禁用", data["message"])

    def test_admin_ui_disabled_interception(self):
        # 关闭后台 UI
        os.environ["ENABLE_ADMIN_UI"] = "0"
        resp = self.client.get("/admin/resources", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(403, resp.status_code)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("后台管理 UI 当前已被禁用", data["message"])

    # --- 4. 管理后台 API 模式配置 CRUD 接口测试 ---

    def test_admin_api_mode_config_endpoints(self):
        self.client.set_cookie("token", self.token)
        resp = self.client.get("/admin/api/api-mode-config")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])

        # 保存更新
        payload = {
            "api_only": True,
            "enable_frontend": False,
            "enable_admin_ui": True,
            "search_scope": "own",
            "transfer_api_key": "newkey123",
        }
        resp = self.client.post("/admin/api/api-mode-config", json=payload)
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["config"]["api_only"])
        self.assertEqual("own", data["config"]["search_scope"])
        self.assertEqual("newkey123", data["config"]["transfer_api_key"])


if __name__ == "__main__":
    unittest.main()
