import json
import os
import unittest
from unittest.mock import patch, MagicMock

from app import app
from src.services.system_config_service import (
    get_api_mode_config,
    save_api_mode_config,
    save_public_search_api_config,
    save_search_api_scope,
    save_transfer_api_key,
    is_api_only_enabled,
    is_frontend_enabled,
)
from src.utils.auth_utils import create_jwt_token


class ApiV1AndApiOnlyTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.token = create_jwt_token()
        save_public_search_api_config(True)

    def tearDown(self):
        # 恢复默认系统配置
        save_api_mode_config(api_only=False, enable_frontend=True, search_scope="own", transfer_api_key="")
        save_public_search_api_config(True)
        os.environ.pop("API_ONLY", None)
        os.environ.pop("PAN_RELAY_API_ONLY", None)
        os.environ.pop("ENABLE_FRONTEND", None)
        os.environ.pop("SEARCH_API_SCOPE", None)
        os.environ.pop("TRANSFER_API_KEY", None)

    # --- 1. 系统配置与环境变量测试 ---

    def test_api_mode_config_defaults_and_saving(self):
        save_api_mode_config(api_only=False, enable_frontend=True, search_scope="own", transfer_api_key="secret123")
        config = get_api_mode_config()
        self.assertFalse(config["api_only"])
        self.assertTrue(config["enable_frontend"])
        self.assertEqual("own", config["search_scope"])
        self.assertEqual("secret123", config["transfer_api_key"])

        save_api_mode_config(api_only=False, enable_frontend=False, search_scope="all", transfer_api_key="")
        config = get_api_mode_config()
        self.assertFalse(config["enable_frontend"])
        self.assertEqual("all", config["search_scope"])

    def test_api_mode_config_flags(self):
        save_api_mode_config(api_only=True, enable_frontend=True)
        self.assertTrue(is_api_only_enabled())
        self.assertFalse(is_frontend_enabled())

        save_api_mode_config(api_only=False, enable_frontend=False)
        self.assertFalse(is_api_only_enabled())
        self.assertFalse(is_frontend_enabled())

        save_api_mode_config(api_only=False, enable_frontend=True)
        self.assertFalse(is_api_only_enabled())
        self.assertTrue(is_frontend_enabled())

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

    @patch("src.routes.api_v1_routes.check_link")
    @patch("src.routes.api_v1_routes.resolve_view_url")
    def test_api_v1_transfer_with_api_key_protection(self, mock_resolve, mock_check):
        mock_check.return_value = {"state": "ok", "summary": "链接有效"}
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


    # --- 3. UI 屏蔽与重定向测试 ---

    def test_frontend_disabled_interception(self):
        # 关闭前台时，访问根路径 / 自动重定向到后台管理登录页
        save_api_mode_config(enable_frontend=False)
        resp = self.client.get("/")
        self.assertEqual(302, resp.status_code)
        self.assertIn(resp.headers.get("Location", ""), ["/admin", "/login"])

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
            "search_scope": "own",
            "transfer_api_key": "newkey123",
        }
        resp = self.client.post("/admin/api/api-mode-config", json=payload)
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["config"]["api_only"])
        self.assertEqual("own", data["config"]["search_scope"])
    # --- 5. Web 前端网盘显示过滤与 API 开放性解耦测试 ---

    @patch("src.services.search_service.search_in_database")
    @patch("src.services.search_service.iter_upstream_search_results")
    def test_web_vs_api_netdisk_filtering_decoupling(self, mock_upstreams, mock_db):
        from src.services.system_config_service import save_frontend_display_netdisk_config
        from src.services.search_service import generate_search_stream_events, search_public_resources, clear_search_cache

        clear_search_cache()
        # 后台 Web 前端配置仅启用 夸克网盘（禁用 百度网盘、阿里云盘 等）
        save_frontend_display_netdisk_config(["夸克网盘"])

        items = [
            ["hot", "繁花 夸克", "https://pan.quark.cn/s/quark1", "夸克网盘"],
            ["tg", "繁花 百度", "https://pan.baidu.com/s/baidu1", "百度网盘"],
            ["other", "繁花 阿里", "https://www.alipan.com/s/ali1", "阿里云盘"],
        ]
        mock_db.return_value = [items[0]]
        mock_upstreams.return_value = iter([[items[1], items[2]]])

        # 1. Web 流式搜索 (action="search.web") -> 严格执行 Web 过滤，只保留 夸克网盘
        web_events = list(generate_search_stream_events("繁花", action="search.web"))
        web_final_event = json.loads(web_events[-1])
        web_results = web_final_event["results"]
        self.assertEqual(1, len(web_results))
        self.assertEqual("夸克网盘", web_results[0][3])

        clear_search_cache()
        mock_db.return_value = [items[0]]
        mock_upstreams.return_value = iter([[items[1], items[2]]])

        # 2. API 流式搜索 (action="search.api.v1") -> 不受 Web 过滤限制，保留全部 3 个网盘
        api_events = list(generate_search_stream_events("繁花", action="search.api.v1"))
        api_final_event = json.loads(api_events[-1])
        api_results = api_final_event["results"]
        self.assertEqual(3, len(api_results))
        api_clouds = {r[3] for r in api_results}
        self.assertEqual({"夸克网盘", "百度网盘", "阿里云盘"}, api_clouds)

        clear_search_cache()
        mock_db.return_value = [items[0]]
        mock_upstreams.return_value = iter([[items[1], items[2]]])

        # 3. API 聚合搜索 search_public_resources -> 不受 Web 过滤限制
        success, _, public_results = search_public_resources("繁花")
        self.assertTrue(success)
        self.assertEqual(3, len(public_results))
        public_clouds = {r["cloud_name"] for r in public_results}
        self.assertEqual({"夸克网盘", "百度网盘", "阿里云盘"}, public_clouds)

        # 4. API 客户端主动指定 cloud_name 参数 -> 仅按参数过滤
        success, _, filtered_results = search_public_resources("繁花", cloud_name="百度网盘")
        self.assertTrue(success)
        self.assertEqual(1, len(filtered_results))
        self.assertEqual("百度网盘", filtered_results[0]["cloud_name"])

    # --- 6. 多网盘组合过滤参数 (cloud_name=夸克,百度 或 多值参数) 测试 ---

    def test_parse_netdisk_names_utility(self):
        from src.utils.netdisk_utils import parse_netdisk_names

        self.assertEqual(set(), parse_netdisk_names(""))
        self.assertEqual(set(), parse_netdisk_names(None))
        self.assertEqual({"夸克网盘"}, parse_netdisk_names("夸克网盘"))
        self.assertEqual({"夸克网盘", "百度网盘"}, parse_netdisk_names("夸克网盘, 百度网盘"))
        self.assertEqual({"夸克网盘", "百度网盘", "阿里云盘"}, parse_netdisk_names(["夸克网盘", "百度网盘,阿里云盘"]))
        self.assertEqual({"123云盘", "迅雷网盘"}, parse_netdisk_names("123云盘;迅雷网盘|123云盘"))

    @patch("src.routes.api_v1_routes.search_public_resources")
    def test_api_v1_search_multi_cloud_filtering(self, mock_public_search):
        mock_public_search.return_value = (True, "成功", [
            {"title": "资源1", "share_link": "https://pan.quark.cn/s/1", "cloud_name": "夸克网盘"},
            {"title": "资源2", "share_link": "https://pan.baidu.com/s/2", "cloud_name": "百度网盘"},
        ])

        # 1. 逗号分隔传递多个网盘 ?cloud_name=夸克网盘,百度网盘
        resp = self.client.get("/api/v1/search?keyword=繁花&cloud_name=夸克网盘,百度网盘&scope=all")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        mock_public_search.assert_called_once()
        called_clouds = mock_public_search.call_args[1].get("cloud_name")
        self.assertEqual({"夸克网盘", "百度网盘"}, called_clouds)

        mock_public_search.reset_mock()

        # 2. 多值 Query 参数 ?cloud_name=夸克网盘&cloud_name=阿里云盘
        resp = self.client.get("/api/v1/search?keyword=繁花&cloud_name=夸克网盘&cloud_name=阿里云盘&scope=all")
        self.assertEqual(200, resp.status_code)
        called_clouds = mock_public_search.call_args[1].get("cloud_name")
        self.assertEqual({"夸克网盘", "阿里云盘"}, called_clouds)

        # 3. 传入不支持的非法网盘名称 -> 400 校验拦截
        resp_invalid = self.client.get("/api/v1/search?keyword=繁花&cloud_name=夸克网盘,未知神秘网盘")
        self.assertEqual(400, resp_invalid.status_code)
        self.assertIn("不支持的网盘类型", resp_invalid.get_json()["message"])

    @patch("src.routes.search_routes.search_public_resources")
    def test_legacy_api_multi_cloud_filtering(self, mock_public_search):
        mock_public_search.return_value = (True, "成功", [
            {"title": "资源1", "share_link": "https://pan.quark.cn/s/1", "cloud_name": "夸克网盘"},
        ])

        resp = self.client.get("/api?keyword=繁花&cloud_name=夸克网盘,123云盘")
        self.assertEqual(200, resp.status_code)
        mock_public_search.assert_called_once()
        called_clouds = mock_public_search.call_args[1].get("cloud_name")
        self.assertEqual({"夸克网盘", "123云盘"}, called_clouds)


if __name__ == "__main__":
    unittest.main()

