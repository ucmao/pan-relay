import unittest
from unittest.mock import patch, MagicMock
from app import app
from src.utils.auth_utils import create_jwt_token


class PluginTestAllEndpointTest(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    @patch("src.routes.plugin_routes.plugin_manager")
    def test_plugin_test_all_endpoint(self, mock_plugin_manager):
        mock_plugin = MagicMock()
        mock_plugin.name = "test_plugin"
        mock_plugin.health_check.return_value = (True, "OK")
        mock_plugin_manager.get_all_plugins.return_value = [mock_plugin]

        token = create_jwt_token()
        self.client.set_cookie("token", token)

        with patch("src.routes.plugin_routes.save_plugin_health") as mock_save:
            response = self.client.post("/admin/api/plugins/test-all")
            self.assertEqual(200, response.status_code)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(1, data["total"])
            self.assertEqual(1, data["healthy_count"])
            mock_save.assert_called_once_with("test_plugin", {
                "status": "healthy",
                "latency_ms": 0,
                "count": 0,
                "message": "OK",
            })


if __name__ == "__main__":
    unittest.main()
