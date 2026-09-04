import unittest
from unittest.mock import patch
from app import app
from src.utils.auth_utils import create_jwt_token


class ApiConfigToggleTest(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.token = create_jwt_token()
        self.client.set_cookie("token", self.token)

    @patch("src.routes.api_config_routes.set_api_enabled_in_db")
    def test_toggle_api_enabled_allows_enabling_abnormal_api(self, mock_set_enabled):
        mock_set_enabled.return_value = (True, "API 启用状态更新成功")

        response = self.client.put("/admin/api/configs/1/enabled", json={"is_enabled": True})
        self.assertEqual(200, response.status_code)
        data = response.get_json()
        self.assertEqual("API 启用状态更新成功", data["message"])
        mock_set_enabled.assert_called_once_with(1, True)


if __name__ == "__main__":
    unittest.main()
