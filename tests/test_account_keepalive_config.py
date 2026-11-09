import unittest
from unittest.mock import MagicMock, patch

from app import app
from src.services.system_config_service import (
    ACCOUNT_KEEPALIVE_CONFIG_KEY,
    DEFAULT_ACCOUNT_KEEPALIVE_CONFIG,
    get_account_keepalive_config,
    save_account_keepalive_config,
)
from src.services.scheduler_service import reload_account_keepalive_job
from src.utils.auth_utils import create_jwt_token


class AccountKeepaliveConfigTest(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.token = create_jwt_token("admin")

    def test_default_config(self):
        with patch("src.services.system_config_service.get_config_value", return_value=None):
            cfg = get_account_keepalive_config()
            self.assertEqual(cfg, DEFAULT_ACCOUNT_KEEPALIVE_CONFIG)
            self.assertTrue(cfg["enabled"])
            self.assertEqual(cfg["interval_hours"], 24)

    def test_save_and_boundary_checks(self):
        with patch("src.services.system_config_service.set_config_value", return_value=True) as mock_set, \
             patch("src.services.scheduler_service.reload_account_keepalive_job") as mock_reload:
            
            # 正常保存
            ok = save_account_keepalive_config({"enabled": True, "interval_hours": 12})
            self.assertTrue(ok)
            mock_set.assert_called_with(
                ACCOUNT_KEEPALIVE_CONFIG_KEY,
                {"enabled": True, "interval_hours": 12}
            )
            mock_reload.assert_called_once()

            # 边界检查：小于 1 的周期自动修正为 1
            save_account_keepalive_config({"enabled": False, "interval_hours": -5})
            mock_set.assert_called_with(
                ACCOUNT_KEEPALIVE_CONFIG_KEY,
                {"enabled": False, "interval_hours": 1}
            )

            # 边界检查：大于 720 的周期自动修正为 720
            save_account_keepalive_config({"enabled": True, "interval_hours": 9999})
            mock_set.assert_called_with(
                ACCOUNT_KEEPALIVE_CONFIG_KEY,
                {"enabled": True, "interval_hours": 720}
            )

            # 非法数据类型返回 False
            ok_invalid = save_account_keepalive_config("invalid_str")
            self.assertFalse(ok_invalid)

    def test_scheduler_reload(self):
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_scheduler.get_job.return_value = mock_job

        with patch("src.services.scheduler_service._scheduler", mock_scheduler):
            # 1. 停用任务
            with patch("src.services.system_config_service.get_account_keepalive_config", return_value={"enabled": False, "interval_hours": 24}):
                reload_account_keepalive_job()
                mock_scheduler.remove_job.assert_called_with("keepalive_cloud_accounts")

            # 2. 启用任务，每 6 小时
            with patch("src.services.system_config_service.get_account_keepalive_config", return_value={"enabled": True, "interval_hours": 6}):
                reload_account_keepalive_job()
                mock_scheduler.add_job.assert_called_with(
                    unittest.mock.ANY,
                    trigger="interval",
                    hours=6,
                    id="keepalive_cloud_accounts",
                    max_instances=1,
                    replace_existing=True,
                )

    def test_keepalive_config_api_routes(self):
        # 1. 未鉴权请求
        resp = self.client.get("/admin/api/accounts/keepalive-config")
        self.assertEqual(resp.status_code, 401)

        resp = self.client.post("/admin/api/accounts/keepalive-config", json={"enabled": True})
        self.assertEqual(resp.status_code, 401)

        # 2. 鉴权 GET 请求
        self.client.set_cookie("token", self.token)
        with patch("src.services.system_config_service.get_account_keepalive_config", return_value={"enabled": True, "interval_hours": 12}):
            resp = self.client.get("/admin/api/accounts/keepalive-config")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("config", {}).get("interval_hours"), 12)

        # 3. 鉴权 POST 请求
        with patch("src.services.system_config_service.save_account_keepalive_config", return_value=True):
            resp = self.client.post(
                "/admin/api/accounts/keepalive-config",
                json={"enabled": True, "interval_hours": 12}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get("success"))


if __name__ == "__main__":
    unittest.main()
