import unittest
from unittest.mock import patch

from app import app
from src.services.system_config_service import (
    get_frontend_link_check_config,
    save_frontend_link_check_config,
    is_frontend_link_check_enabled,
    is_default_hide_dead_links_enabled,
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
                save_frontend_link_check_config(enable_link_check=True, default_hide_dead_links=False)
        else:
            save_frontend_link_check_config(enable_link_check=True, default_hide_dead_links=False)

    def test_service_get_and_save_config(self):
        # 1. Save custom config
        success = save_frontend_link_check_config(enable_link_check=False, default_hide_dead_links=True)
        self.assertTrue(success)

        # 2. Get config
        cfg = get_frontend_link_check_config()
        self.assertFalse(cfg["enable_link_check"])
        self.assertTrue(cfg["default_hide_dead_links"])

        self.assertFalse(is_frontend_link_check_enabled())
        self.assertTrue(is_default_hide_dead_links_enabled())

        # 3. Toggle back
        save_frontend_link_check_config(enable_link_check=True, default_hide_dead_links=False)
        cfg2 = get_frontend_link_check_config()
        self.assertTrue(cfg2["enable_link_check"])
        self.assertFalse(cfg2["default_hide_dead_links"])

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
        self.assertIn("default_hide_dead_links", data)

        # Authorized PUT
        put_resp = self.client.put(
            "/admin/api/frontend-link-check-config",
            json={"enable_link_check": False, "default_hide_dead_links": True},
        )
        self.assertEqual(200, put_resp.status_code)
        put_data = put_resp.get_json()
        self.assertTrue(put_data.get("success"))
        self.assertFalse(put_data["data"]["enable_link_check"])
        self.assertTrue(put_data["data"]["default_hide_dead_links"])

        # Verify through GET
        verify_resp = self.client.get("/admin/api/frontend-link-check-config")
        v_data = verify_resp.get_json()
        self.assertFalse(v_data["enable_link_check"])
        self.assertTrue(v_data["default_hide_dead_links"])

    def test_index_page_context_injection(self):
        # 1. Enabled link check
        save_frontend_link_check_config(enable_link_check=True, default_hide_dead_links=True)
        resp1 = self.client.get("/")
        self.assertEqual(200, resp1.status_code)
        self.assertIn("window.ENABLE_LINK_CHECK = true", resp1.text)
        self.assertIn("window.DEFAULT_HIDE_DEAD_LINKS = true", resp1.text)
        self.assertIn('id="hideDeadLinksToggle"', resp1.text)

        # 2. Disabled link check
        save_frontend_link_check_config(enable_link_check=False, default_hide_dead_links=False)
        resp2 = self.client.get("/")
        self.assertEqual(200, resp2.status_code)
        self.assertIn("window.ENABLE_LINK_CHECK = false", resp2.text)
        self.assertIn("window.DEFAULT_HIDE_DEAD_LINKS = false", resp2.text)
        self.assertNotIn('id="hideDeadLinksToggle"', resp2.text)

    def test_frontend_config_page_renders_new_toggles(self):
        resp = self.client.get("/admin/frontend-config")
        self.assertEqual(200, resp.status_code)
        self.assertIn("enableFrontendLinkCheckToggle", resp.text)
        self.assertIn("defaultHideDeadLinksToggle", resp.text)
        self.assertIn("前台链接实时测活", resp.text)
        self.assertIn("前台默认过滤失效资源", resp.text)


if __name__ == "__main__":
    unittest.main()
