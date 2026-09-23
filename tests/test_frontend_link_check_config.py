import json
import unittest
from unittest.mock import patch

from app import app
from src.services.system_config_service import (
    get_frontend_link_check_config,
    save_frontend_link_check_config,
    is_frontend_link_check_enabled,
    FRONTEND_LINK_CHECK_CONFIG_KEY,
)
from src.db.system_configs import get_config_value, set_config_value
from src.utils.auth_utils import create_jwt_token


class FrontendLinkCheckConfigTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.token = create_jwt_token()
        self.client.set_cookie("token", self.token)
        # Backup original config
        self.original_config_raw = get_config_value(FRONTEND_LINK_CHECK_CONFIG_KEY)

    def tearDown(self):
        # Restore original config safely
        if self.original_config_raw is not None:
            try:
                parsed = json.loads(self.original_config_raw)
                while isinstance(parsed, str):
                    parsed = json.loads(parsed)
                set_config_value(FRONTEND_LINK_CHECK_CONFIG_KEY, parsed)
            except Exception:
                save_frontend_link_check_config(enable_link_check=True)
        else:
            save_frontend_link_check_config(enable_link_check=True)

    def test_service_get_and_save_config(self):
        # 1. Save custom config
        success = save_frontend_link_check_config(enable_link_check=False)
        self.assertTrue(success)

        # 2. Get config
        cfg = get_frontend_link_check_config()
        self.assertFalse(cfg["enable_link_check"])
        self.assertFalse(is_frontend_link_check_enabled())

        # 3. Toggle back
        save_frontend_link_check_config(enable_link_check=True)
        cfg2 = get_frontend_link_check_config()
        self.assertTrue(cfg2["enable_link_check"])

    def test_admin_api_get_and_put(self):
        # Unauthorized without token
        unauth_client = app.test_client()
        unauth_resp = unauth_client.get("/admin/api/frontend-link-check-config")
        self.assertEqual(401, unauth_resp.status_code)

        # Authorized GET
        get_resp = self.client.get("/admin/api/frontend-link-check-config")
        self.assertEqual(200, get_resp.status_code)
        data = get_resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("enable_link_check", data)

        # Authorized PUT
        put_resp = self.client.put(
            "/admin/api/frontend-link-check-config",
            json={"enable_link_check": False},
        )
        self.assertEqual(200, put_resp.status_code)
        put_data = put_resp.get_json()
        self.assertTrue(put_data.get("success"))
        self.assertFalse(put_data["data"]["enable_link_check"])

        # Verify through GET
        verify_resp = self.client.get("/admin/api/frontend-link-check-config")
        v_data = verify_resp.get_json()
        self.assertFalse(v_data["enable_link_check"])

    def test_index_page_context_injection(self):
        # 1. Enabled link check
        save_frontend_link_check_config(enable_link_check=True)
        resp1 = self.client.get("/")
        self.assertEqual(200, resp1.status_code)
        self.assertIn("window.ENABLE_LINK_CHECK = true", resp1.text)
        self.assertIn('id="hideDeadLinksToggle"', resp1.text)

        # 2. Disabled link check
        save_frontend_link_check_config(enable_link_check=False)
        resp2 = self.client.get("/")
        self.assertEqual(200, resp2.status_code)
        self.assertIn("window.ENABLE_LINK_CHECK = false", resp2.text)
        self.assertNotIn('id="hideDeadLinksToggle"', resp2.text)

    def test_frontend_config_page_renders_new_toggles(self):
        resp = self.client.get("/admin/frontend-config")
        self.assertEqual(200, resp.status_code)
        self.assertIn("enableFrontendLinkCheckToggle", resp.text)
        self.assertIn("测活生效网盘范围", resp.text)
        self.assertIn("linkCheckNetdisksGroup", resp.text)

    def test_enabled_check_pans_saving(self):
        save_frontend_link_check_config(
            enable_link_check=True,
            enabled_check_pans=["百度网盘", "夸克网盘"]
        )
        cfg = get_frontend_link_check_config()
        self.assertEqual(cfg["enabled_check_pans"], ["百度网盘", "夸克网盘"])

        put_resp = self.client.put(
            "/admin/api/frontend-link-check-config",
            json={
                "enable_link_check": True,
                "enabled_check_pans": ["百度网盘", "夸克网盘", "阿里云盘"]
            },
        )
        self.assertEqual(200, put_resp.status_code)
        put_data = put_resp.get_json()
        self.assertEqual(put_data["data"]["enabled_check_pans"], ["百度网盘", "夸克网盘", "阿里云盘"])


if __name__ == "__main__":
    unittest.main()
