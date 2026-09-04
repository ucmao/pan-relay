import unittest
from app import app
from src.services.dashboard_service import get_dashboard_summary
from src.utils.auth_utils import create_jwt_token


class TestDashboard(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.client = app.test_client()
        self.token = create_jwt_token()

    def test_get_dashboard_summary_structure(self):
        summary = get_dashboard_summary()
        self.assertIn("resources", summary)
        self.assertIn("sources", summary)
        self.assertIn("credentials", summary)
        self.assertIn("system", summary)

        self.assertIn("total_count", summary["resources"])
        self.assertIn("api", summary["sources"])
        self.assertIn("plugins", summary["sources"])
        self.assertIn("telegram", summary["sources"])
        self.assertIn("overall_health_rate", summary["sources"])

    def test_dashboard_page_requires_auth(self):
        # 未带 token 时访问应被拦截重定向或返回无权限
        response = self.client.get("/admin/dashboard")
        self.assertIn(response.status_code, (302, 401))

    def test_dashboard_page_authenticated(self):
        self.client.set_cookie('token', self.token)
        response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("仪表盘".encode("utf-8"), response.data)

    def test_dashboard_stats_api_authenticated(self):
        self.client.set_cookie('token', self.token)
        response = self.client.get("/admin/api/dashboard/stats")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("resources", data["data"])

    def test_admin_login_redirect_to_dashboard(self):
        self.client.set_cookie('token', self.token)
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
