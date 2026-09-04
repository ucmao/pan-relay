import unittest
from unittest.mock import patch
from app import app
from src.services.system_config_service import (
    get_allow_excel_download_config,
    is_excel_download_enabled,
    save_allow_excel_download_config,
    ALLOW_EXCEL_DOWNLOAD_KEY,
)
from src.utils.auth_utils import create_jwt_token


class TestExcelDownloadConfig(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.client = app.test_client()
        self.token = create_jwt_token()

    @patch("src.services.system_config_service.get_config_value")
    def test_default_allow_excel_download(self, mock_get_config):
        mock_get_config.return_value = None
        config = get_allow_excel_download_config()
        self.assertTrue(config["enabled"])
        self.assertTrue(is_excel_download_enabled())

    @patch("src.services.system_config_service.get_config_value")
    def test_allow_excel_download_disabled(self, mock_get_config):
        mock_get_config.return_value = '{"enabled": false}'
        config = get_allow_excel_download_config()
        self.assertFalse(config["enabled"])
        self.assertFalse(is_excel_download_enabled())

    @patch("src.services.system_config_service.set_config_value")
    def test_save_allow_excel_download(self, mock_set_config):
        mock_set_config.return_value = True
        result = save_allow_excel_download_config(False)
        self.assertTrue(result)
        mock_set_config.assert_called_once_with(
            ALLOW_EXCEL_DOWNLOAD_KEY, {"enabled": False}
        )

    @patch("src.routes.system_config_routes.get_allow_excel_download_config")
    def test_get_allow_excel_download_api(self, mock_get_config):
        mock_get_config.return_value = {"enabled": True}
        self.client.set_cookie('token', self.token)

        response = self.client.get("/admin/api/allow-excel-download-config")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["enabled"])

    @patch("src.routes.system_config_routes.save_allow_excel_download_config")
    def test_update_allow_excel_download_api(self, mock_save_config):
        mock_save_config.return_value = True
        self.client.set_cookie('token', self.token)

        response = self.client.put(
            "/admin/api/allow-excel-download-config",
            json={"enabled": False},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        mock_save_config.assert_called_once_with(False)

    @patch("src.services.system_config_service.get_config_value")
    def test_homepage_render_excel_button_enabled(self, mock_get_config):
        mock_get_config.return_value = '{"enabled": true}'
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="exportExcelBtn"', response.data)

    @patch("src.services.system_config_service.get_config_value")
    def test_homepage_render_excel_button_disabled(self, mock_get_config):
        mock_get_config.return_value = '{"enabled": false}'
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'id="exportExcelBtn"', response.data)


if __name__ == "__main__":
    unittest.main()
