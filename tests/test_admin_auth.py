import os
import unittest
from unittest.mock import patch

from app import app
from src.db.system_configs import delete_config_value
from src.services.admin_auth_service import (
    ADMIN_AUTH_CONFIG_KEY,
    change_admin_password,
    get_admin_auth_config,
    get_admin_username,
    init_admin_auth,
    is_using_default_password,
    reset_admin_password,
    verify_admin_credentials,
)
from src.utils.auth_utils import create_jwt_token


class AdminAuthServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # 每次测试前清空配置并重置为初始状态
        delete_config_value(ADMIN_AUTH_CONFIG_KEY)
        init_admin_auth()

    def tearDown(self):
        # 恢复默认初始状态
        delete_config_value(ADMIN_AUTH_CONFIG_KEY)
        init_admin_auth()

    def test_default_initialization(self):
        """测试初始默认配置生成与弱口令识别"""
        cfg = get_admin_auth_config()
        self.assertEqual("admin", cfg["username"])
        self.assertTrue(is_using_default_password())

        # 默认密码登录成功
        valid, msg = verify_admin_credentials("admin", "admin123")
        self.assertTrue(valid)

        # 错误密码登录失败
        invalid, _ = verify_admin_credentials("admin", "wrongpassword")
        self.assertFalse(invalid)

    def test_change_admin_password_flow(self):
        """测试修改密码校验逻辑"""
        # 1. 原密码错误
        ok, msg = change_admin_password("wrong_old", "newsecret123")
        self.assertFalse(ok)
        self.assertIn("原密码", msg)

        # 2. 新密码长度小于 6
        ok, msg = change_admin_password("admin123", "123")
        self.assertFalse(ok)
        self.assertIn("6", msg)

        # 3. 新密码与原密码相同
        ok, msg = change_admin_password("admin123", "admin123")
        self.assertFalse(ok)
        self.assertIn("相同", msg)

        # 4. 正常成功修改密码
        ok, msg = change_admin_password("admin123", "MyStrongPass#2026")
        self.assertTrue(ok)
        self.assertFalse(is_using_default_password())

        # 5. 旧密码失效，新密码生效
        old_valid, _ = verify_admin_credentials("admin", "admin123")
        self.assertFalse(old_valid)

        new_valid, _ = verify_admin_credentials("admin", "MyStrongPass#2026")
        self.assertTrue(new_valid)

    def test_reset_admin_password(self):
        """测试管理员密码直接重置"""
        ok, msg = reset_admin_password("EmergencyPass@888", new_username="superadmin")
        self.assertTrue(ok)
        self.assertEqual("superadmin", get_admin_username())
        self.assertFalse(is_using_default_password())

        valid, _ = verify_admin_credentials("superadmin", "EmergencyPass@888")
        self.assertTrue(valid)

    def test_env_force_reset_password(self):
        """测试环境变量 ADMIN_RESET_PASSWORD 强制重置机制"""
        with patch.dict(os.environ, {"ADMIN_RESET_PASSWORD": "EnvOverridePass@123"}):
            cfg = get_admin_auth_config()
            valid, _ = verify_admin_credentials("admin", "EnvOverridePass@123")
            self.assertTrue(valid)

    def test_api_change_password_and_status(self):
        """测试 HTTP API 接口"""
        token = create_jwt_token(username="admin")
        self.client.set_cookie("token", token)

        # 查询状态
        status_resp = self.client.get("/admin/api/password_status")
        self.assertEqual(200, status_resp.status_code)
        status_data = status_resp.get_json()
        self.assertTrue(status_data["success"])
        self.assertTrue(status_data["data"]["is_default_password"])

        # 两次密码不一致
        resp = self.client.post(
            "/admin/api/change_password",
            json={
                "old_password": "admin123",
                "new_password": "NewSecretPass#1",
                "confirm_password": "DifferentPass#2",
            },
        )
        self.assertEqual(400, resp.status_code)

        # 成功修改密码
        resp = self.client.post(
            "/admin/api/change_password",
            json={
                "old_password": "admin123",
                "new_password": "NewSecretPass#1",
                "confirm_password": "NewSecretPass#1",
            },
        )
        self.assertEqual(200, resp.status_code)
        resp_data = resp.get_json()
        self.assertTrue(resp_data["success"])

        # 再次查询状态，弱口令警告已消除
        status_resp2 = self.client.get("/admin/api/password_status")
        self.assertFalse(status_resp2.get_json()["data"]["is_default_password"])

    def test_unauthorized_api_access(self):
        """未登录调用修改密码接口应返回 401"""
        resp = self.client.post(
            "/admin/api/change_password",
            json={
                "old_password": "admin123",
                "new_password": "NewSecretPass#1",
                "confirm_password": "NewSecretPass#1",
            },
        )
        self.assertEqual(401, resp.status_code)


if __name__ == "__main__":
    unittest.main()
