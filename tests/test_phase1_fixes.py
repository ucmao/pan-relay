import json
import unittest
from unittest.mock import patch

from app import app
from src.utils.auth_utils import create_jwt_token


class Phase1FixesTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("src.routes.search_routes.create_share")
    def test_create_share_route_success_and_failure(self, mock_create_share):
        # 1. 验证缺少参数返回 400
        resp = self.client.post("/create_share", json={})
        self.assertEqual(400, resp.status_code)

        # 2. 验证成功分支返回 200 及 success=True
        mock_create_share.return_value = {"share_url": "https://pan.quark.cn/s/123", "file_id": "fid1"}
        resp = self.client.post("/create_share", json={"title": "测试资源", "share_url": "https://pan.quark.cn/s/test"})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

        # 3. 验证失败分支（原先 unreachable 的分支）现在正常返回 500 及 success=False
        mock_create_share.return_value = None
        resp = self.client.post("/create_share", json={"title": "测试失败资源", "share_url": "https://pan.quark.cn/s/fail"})
        self.assertEqual(500, resp.status_code)
        data = resp.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("分享创建失败", data.get("error"))

    @patch("src.routes.search_routes.del_share")
    def test_del_share_route_success_and_failure(self, mock_del_share):
        # 1. 验证缺少参数返回 400
        resp = self.client.post("/del_share", json={})
        self.assertEqual(400, resp.status_code)

        # 2. 验证成功分支返回 200 及 success=True
        mock_del_share.return_value = True
        resp = self.client.post("/del_share", json={"share_url": "https://pan.quark.cn/s/test", "file_id": "fid1"})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

        # 3. 验证失败分支（原先 unreachable 的分支）现在正常返回 500 及 success=False
        mock_del_share.return_value = False
        resp = self.client.post("/del_share", json={"share_url": "https://pan.quark.cn/s/fail", "file_id": "fid2"})
        self.assertEqual(500, resp.status_code)
        data = resp.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("分享删除失败", data.get("error"))

    def test_token_required_returns_401_json_for_api(self):
        # 针对 /admin/api/ 路由，未携带 token 应返回 401 JSON，而非 302 重定向
        resp = self.client.get("/admin/api/resources")
        self.assertEqual(401, resp.status_code)
        data = resp.get_json()
        self.assertIsNotNone(data)
        self.assertFalse(data.get("success"))
        self.assertIn("未登录", data.get("message"))

    def test_token_required_returns_302_for_page(self):
        # 针对 HTML 页面请求，未携带 token 应返回 302 重定向到登录页
        resp = self.client.get("/admin/resources")
        self.assertEqual(302, resp.status_code)
        self.assertIn("/admin", resp.headers.get("Location", ""))

    def test_jwt_token_generation_and_verification(self):
        # 验证生成的 token 可以被正常校验
        token = create_jwt_token()
        self.assertIsInstance(token, str)

        # 使用该 token 访问受保护的 API 接口应通过鉴权（不会得到 401）
        self.client.set_cookie("token", token)
        resp = self.client.get("/admin/api/resources")
        self.assertNotEqual(401, resp.status_code)

    def test_login_empty_form_handling(self):
        # 验证表单缺少 username/password 时安全处理，不报 400 KeyError
        resp = self.client.post("/admin", data={})
        self.assertEqual(200, resp.status_code)
        self.assertIn("账号或密码不能为空", resp.get_data(as_text=True))

    @patch("src.routes.api_config_routes.test_single_api")
    def test_api_test_response_contains_status_text(self, mock_test_single):
        # mock test_single_api 返回 (url, new_status, status_code, response_rule_status, response_time_ms)
        mock_test_single.return_value = ("https://test.api", True, 200, True, 120)
        token = create_jwt_token()
        self.client.set_cookie("token", token)

        resp = self.client.post(
            "/admin/api/test",
            json={"id": 1, "name": "测试API", "url": "https://test.api", "method": "GET"}
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual("正常", data.get("status_text"))
        self.assertEqual(True, data.get("status"))
        self.assertEqual("success", data.get("test_outcome"))
        self.assertEqual(120, data.get("response_time_ms"))

    @patch("src.routes.api_config_routes.test_single_api")
    def test_api_test_distinguishes_no_data_from_error(self, mock_test_single):
        mock_test_single.return_value = (
            "https://test.api",
            True,
            200,
            True,
            150,
            "no_data",
            0,
            None,
        )
        token = create_jwt_token()
        self.client.set_cookie("token", token)

        resp = self.client.post(
            "/admin/api/test",
            json={"id": 1, "name": "测试API", "url": "https://test.api", "method": "GET"},
        )

        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual("无结果", data["status_text"])
        self.assertEqual("no_data", data["test_outcome"])
        self.assertTrue(data["status"])

    def test_resources_page_renders_resource_template(self):
        token = create_jwt_token()
        self.client.set_cookie("token", token)
        resp = self.client.get("/admin/resources")
        self.assertEqual(200, resp.status_code)
        html = resp.get_data(as_text=True)
        self.assertIn("我的资源管理", html)
        self.assertIn("resource.css", html)
        self.assertIn("resource.js", html)


if __name__ == "__main__":
    unittest.main()
