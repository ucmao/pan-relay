import json
import unittest
from unittest.mock import patch, MagicMock

from app import app
from src.services.system_config_service import (
    get_dynamic_transfer_netdisk_config,
    save_dynamic_transfer_netdisk_config,
    get_allowed_dynamic_transfer_netdisks,
    get_frontend_link_mode,
    save_frontend_link_mode,
    DYNAMIC_TRANSFER_NETDISKS_KEY,
    FRONTEND_LINK_MODE_KEY,
    ENABLE_FRONTEND_GITHUB_KEY,
    get_frontend_github_config,
    save_frontend_github_config,
    is_frontend_github_enabled,
)
from src.utils.netdisk_utils import DYNAMIC_TRANSFER_NETDISK_OPTIONS
from src.db.system_configs import get_config_value, set_config_value
from src.utils.auth_utils import create_jwt_token
from src.services.temp_share_service import resolve_view_url


class DynamicTransferConfigTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.token = create_jwt_token()
        self.client.set_cookie("token", self.token)
        self.orig_dynamic_cfg = get_config_value(DYNAMIC_TRANSFER_NETDISKS_KEY)
        self.orig_link_mode = get_config_value(FRONTEND_LINK_MODE_KEY)
        self.orig_frontend_github = get_config_value(ENABLE_FRONTEND_GITHUB_KEY)
        save_frontend_github_config(True)

    def tearDown(self):
        if self.orig_dynamic_cfg is not None:
            try:
                parsed = json.loads(self.orig_dynamic_cfg)
                set_config_value(DYNAMIC_TRANSFER_NETDISKS_KEY, parsed)
            except Exception:
                pass
        else:
            save_dynamic_transfer_netdisk_config(DYNAMIC_TRANSFER_NETDISK_OPTIONS)

        if self.orig_link_mode is not None:
            try:
                parsed = json.loads(self.orig_link_mode)
                set_config_value(FRONTEND_LINK_MODE_KEY, parsed)
            except Exception:
                pass
        else:
            save_frontend_link_mode("view")

        if self.orig_frontend_github is not None:
            try:
                parsed = json.loads(self.orig_frontend_github)
                set_config_value(ENABLE_FRONTEND_GITHUB_KEY, parsed)
            except Exception:
                pass
        else:
            save_frontend_github_config(True)

    def test_service_get_and_save_config(self):
        # Save a subset of netdisks
        test_disks = ["夸克网盘", "UC网盘"]
        success = save_dynamic_transfer_netdisk_config(test_disks)
        self.assertTrue(success)

        cfg = get_dynamic_transfer_netdisk_config()
        self.assertEqual(cfg["enabled_netdisks"], test_disks)
        self.assertEqual(get_allowed_dynamic_transfer_netdisks(), set(test_disks))

        # Save with invalid items should filter them
        save_dynamic_transfer_netdisk_config(["夸克网盘", "不存在的网盘", "百度网盘"])
        cfg2 = get_dynamic_transfer_netdisk_config()
        self.assertEqual(cfg2["enabled_netdisks"], ["夸克网盘", "百度网盘"])

    def test_admin_api_get_and_put(self):
        # Unauthorized
        unauth_client = app.test_client()
        unauth_resp = unauth_client.get("/admin/api/dynamic-transfer-netdisks")
        self.assertEqual(401, unauth_resp.status_code)

        # Authorized GET
        get_resp = self.client.get("/admin/api/dynamic-transfer-netdisks")
        self.assertEqual(200, get_resp.status_code)
        data = get_resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("options"), DYNAMIC_TRANSFER_NETDISK_OPTIONS)
        self.assertIsInstance(data.get("enabled_netdisks"), list)

        # Authorized PUT
        put_resp = self.client.put(
            "/admin/api/dynamic-transfer-netdisks",
            json={"enabled_netdisks": ["夸克网盘", "迅雷网盘"]},
        )
        self.assertEqual(200, put_resp.status_code)
        put_data = put_resp.get_json()
        self.assertTrue(put_data.get("success"))
        self.assertEqual(put_data["data"]["enabled_netdisks"], ["夸克网盘", "迅雷网盘"])

        # Verify through GET
        verify_resp = self.client.get("/admin/api/dynamic-transfer-netdisks")
        v_data = verify_resp.get_json()
        self.assertEqual(v_data["enabled_netdisks"], ["夸克网盘", "迅雷网盘"])

    def test_resolve_view_url_respects_netdisk_whitelist(self):
        save_frontend_link_mode("view")
        # Only enable Quark, but NOT Baidu
        save_dynamic_transfer_netdisk_config(["夸克网盘"])

        # Test Baidu URL (not in dynamic transfer whitelist) -> should fallback to original
        baidu_url = "https://pan.baidu.com/s/123456"
        res_baidu = resolve_view_url("百度测试", baidu_url, "百度网盘")
        self.assertEqual(res_baidu["mode"], "original")
        self.assertEqual(res_baidu["url"], baidu_url)

        # Test Quark URL (in whitelist) with mock account pool and create_share
        quark_url = "https://pan.quark.cn/s/abcdef123"
        with patch("src.services.account_pool_manager.AccountPoolManager.get_instance") as mock_pool_mgr:
            mock_inst = MagicMock()
            mock_inst.get_candidate_accounts.return_value = [{"id": 1, "cloud_name": "夸克网盘"}]
            mock_pool_mgr.return_value = mock_inst

            with patch("src.services.temp_share_service.create_share") as mock_create_share:
                mock_create_share.return_value = {
                    "share_url": "https://pan.quark.cn/s/transferred_999",
                    "file_id": "file_123",
                    "account_id": 1,
                }
                res_quark = resolve_view_url("夸克测试", quark_url, "夸克网盘")
                self.assertEqual(res_quark["mode"], "temp_share")
                self.assertEqual(res_quark["url"], "https://pan.quark.cn/s/transferred_999")

    def test_resolve_view_url_fallback_when_global_link_mode_copy(self):
        save_frontend_link_mode("copy")
        save_dynamic_transfer_netdisk_config(["夸克网盘", "百度网盘"])

        quark_url = "https://pan.quark.cn/s/abcdef123"
        res = resolve_view_url("夸克测试", quark_url, "夸克网盘")
        self.assertEqual(res["mode"], "original")
        self.assertEqual(res["url"], quark_url)

    def test_index_and_admin_page_renders_dynamic_transfer_config(self):
        save_dynamic_transfer_netdisk_config(["夸克网盘", "UC网盘"])

        # Index page should inject ENABLED_DYNAMIC_TRANSFER_PANS
        resp_index = self.client.get("/")
        self.assertEqual(200, resp_index.status_code)
        self.assertIn("window.ENABLED_DYNAMIC_TRANSFER_PANS", resp_index.text)
        self.assertIn('"\\u5938\\u514b\\u7f51\\u76d8"', resp_index.text)  # "夸克网盘" JSON escaped

        # Admin frontend config page should render panel and cards
        resp_admin = self.client.get("/admin/frontend-config")
        self.assertEqual(200, resp_admin.status_code)
        self.assertIn("dynamicTransferNetdisksWrapper", resp_admin.text)
        self.assertIn("rawLinkSettingsWrapper", resp_admin.text)
        self.assertIn("excelDownloadSettingContainer", resp_admin.text)
        self.assertIn("frontendLinkStrategyContainer", resp_admin.text)
        self.assertIn("linkCheckPanel", resp_admin.text)
        self.assertIn("frontendDisplayNetdisksPanel", resp_admin.text)
        self.assertIn("dynamicTransferNetdisksGroup", resp_admin.text)
        self.assertIn("dynamic-transfer-netdisk-checkbox", resp_admin.text)
        self.assertIn("frontendGithubSettingContainer", resp_admin.text)
        self.assertIn("enableFrontendGithubToggle", resp_admin.text)
        self.assertIn("frontendBrandPanel", resp_admin.text)

    def test_frontend_github_config_service_and_api(self):
        # Default should be enabled
        self.assertTrue(is_frontend_github_enabled())
        self.assertEqual(get_frontend_github_config(), {"enabled": True})

        # Save disabled
        self.assertTrue(save_frontend_github_config(False))
        self.assertFalse(is_frontend_github_enabled())
        self.assertEqual(get_frontend_github_config(), {"enabled": False})

        # GET API
        resp_get = self.client.get("/admin/api/frontend-github-config")
        self.assertEqual(200, resp_get.status_code)
        data = resp_get.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["enabled"])

        # PUT API
        resp_put = self.client.put("/admin/api/frontend-github-config", json={"enabled": True})
        self.assertEqual(200, resp_put.status_code)
        data_put = resp_put.get_json()
        self.assertTrue(data_put["success"])
        self.assertTrue(is_frontend_github_enabled())

    def test_frontend_github_rendering(self):
        # 1. When enabled: index page should contain github pill, star count ID, and repo URL
        save_frontend_github_config(True)
        resp_enabled = self.client.get("/")
        self.assertEqual(200, resp_enabled.status_code)
        self.assertIn('id="githubStarCount"', resp_enabled.text)
        self.assertIn("https://github.com/ucmao/pan-relay", resp_enabled.text)
        self.assertIn('<div class="disclaimer-star-box">', resp_enabled.text)
        self.assertIn('class="fab fa-github', resp_enabled.text)

        # 2. When disabled: index page should NOT contain any github links, pill elements, or star count
        save_frontend_github_config(False)
        resp_disabled = self.client.get("/")
        self.assertEqual(200, resp_disabled.status_code)
        self.assertNotIn('id="githubStarCount"', resp_disabled.text)
        self.assertNotIn("https://github.com/ucmao/pan-relay", resp_disabled.text)
        self.assertNotIn('<div class="disclaimer-star-box">', resp_disabled.text)
        self.assertNotIn('class="fab fa-github', resp_disabled.text)


if __name__ == "__main__":
    unittest.main()


