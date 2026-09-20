import json
import time
import unittest
from unittest.mock import MagicMock, patch

from src.clients.aliyun_client import AliyunPanClient, _ALIYUN_ACCESS_TOKEN_CACHE
from src.clients.baidu_client import BaiduPanClient, get_baidu_errno_message, BAIDU_ERRNO_MAP
from src.clients.quark_client import QuarkPanClient
from src.clients.uc_client import UcPanClient
from src.clients.xunlei_client import (
    XunleiPanClient,
    _XUNLEI_ACCESS_TOKEN_CACHE,
    _XUNLEI_CAPTCHA_TOKEN_CACHE,
)
from src.db.credentials import (
    delete_cookie,
    get_cookie_by_cloud_name,
    save_cookie,
    update_xunlei_refresh_token,
)


class TestP0StabilityAndDiagnostics(unittest.TestCase):
    def setUp(self):
        # 清空全局缓存与测试残留，防止测试间干扰
        _XUNLEI_ACCESS_TOKEN_CACHE.clear()
        _XUNLEI_CAPTCHA_TOKEN_CACHE.clear()
        _ALIYUN_ACCESS_TOKEN_CACHE.clear()
        delete_cookie("迅雷网盘")

    def tearDown(self):
        # 清理测试写入的凭证，防止污染实际生产数据库
        delete_cookie("迅雷网盘")

    def test_update_xunlei_refresh_token_db(self):
        """测试迅雷 refresh_token 在数据库层面的轮换持久化"""
        original_cred = {
            "refresh_token": "old_token_123",
            "captcha_sign": "test_sign",
            "user_id": "test_uid",
        }
        save_cookie("迅雷网盘", json.dumps(original_cred, ensure_ascii=False))

        # 执行更新
        success = update_xunlei_refresh_token("new_token_456")
        self.assertTrue(success)

        # 读取数据库验证
        updated_raw = get_cookie_by_cloud_name("迅雷网盘")
        self.assertIsNotNone(updated_raw)
        updated_dict = json.loads(updated_raw)
        self.assertEqual(updated_dict.get("refresh_token"), "new_token_456")
        self.assertEqual(updated_dict.get("captcha_sign"), "test_sign")
        self.assertEqual(updated_dict.get("user_id"), "test_uid")

    @patch("requests.post")
    def test_xunlei_token_caching_and_rotation(self, mock_post):
        """测试迅雷 Token 缓存与轮换回写机制"""
        cred = {
            "refresh_token": "init_token",
            "captcha_sign": "sign_1",
            "user_id": "uid_1",
        }
        save_cookie("迅雷网盘", json.dumps(cred, ensure_ascii=False))

        # 模拟认证接口返回包含新的 refresh_token
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "code": 0,
            "data": {
                "access_token": "acc_token_999",
                "refresh_token": "rotated_token_888",
                "expires_in": 7200,
            },
        }
        mock_post.return_value = mock_resp

        client = XunleiPanClient(cred)
        token1 = client._get_access_token()
        self.assertEqual(token1, "acc_token_999")
        self.assertEqual(mock_post.call_count, 1)

        # 第二次获取应该命中缓存，不发起第二次 HTTP 请求
        token2 = client._get_access_token()
        self.assertEqual(token2, "acc_token_999")
        self.assertEqual(mock_post.call_count, 1)

        # 验证数据库中已经更新为 rotated_token_888
        updated_raw = get_cookie_by_cloud_name("迅雷网盘")
        updated_dict = json.loads(updated_raw)
        self.assertEqual(updated_dict.get("refresh_token"), "rotated_token_888")

    @patch("src.clients.xunlei_client.XunleiPanClient._request_pan")
    @patch("src.clients.xunlei_client.XunleiPanClient._get_access_token")
    def test_xunlei_sensitive_resource_diagnostics(self, mock_get_token, mock_request_pan):
        """测试迅雷网盘敏感违规资源的精准拦截诊断"""
        mock_get_token.return_value = "fake_access_token"
        mock_request_pan.return_value = {
            "share_status": "SENSITIVE_RESOURCE",
            "share_status_text": "该资源涉及侵权违规",
        }

        client = XunleiPanClient({"refresh_token": "t", "captcha_sign": "s", "user_id": "u"})
        file_id, file_name, share_url = client.store("https://pan.xunlei.com/s/VNsense")
        self.assertIsNone(file_id)
        self.assertIsNone(share_url)

    @patch("requests.post")
    def test_aliyun_token_caching(self, mock_post):
        """测试阿里云盘 Token 缓存机制"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "ali_access_token_123",
            "default_drive_id": "drive_999",
            "expires_in": 7200,
        }
        mock_post.return_value = mock_resp

        # 第一次实例化
        client1 = AliyunPanClient("ali_refresh_token_abc")
        self.assertEqual(client1.access_token, "ali_access_token_123")
        self.assertEqual(mock_post.call_count, 1)

        # 第二次实例化同个 refresh_token，应直接命中缓存
        client2 = AliyunPanClient("ali_refresh_token_abc")
        self.assertEqual(client2.access_token, "ali_access_token_123")
        self.assertEqual(client2.drive_id, "drive_999")
        self.assertEqual(mock_post.call_count, 1)

    def test_baidu_errno_map_completeness(self):
        """测试百度网盘错误码字典与诊断函数"""
        self.assertIn("风控", get_baidu_errno_message(-1))
        self.assertIn("Cookie已失效", get_baidu_errno_message(-6))
        self.assertIn("容量不足", get_baidu_errno_message(-10))
        self.assertIn("敏感违规", get_baidu_errno_message(115))
        self.assertIn("操作成功", get_baidu_errno_message(0))
        self.assertIn("未知错误", get_baidu_errno_message(99999))

    @patch("src.clients.baidu_client.BaiduPanClient._request")
    def test_baidu_diagnostics_on_verify_fail(self, mock_request):
        """测试百度网盘提取码验证失败诊断"""
        mock_request.return_value = {"errno": -12}
        client = BaiduPanClient("BDUSS=fake_cookie")
        verified = client._verify_pwd("test_surl", "wrong_pwd")
        self.assertFalse(verified)

    @patch("src.clients.quark_client.QuarkPanClient._request")
    def test_quark_diagnostics_on_login_fail(self, mock_request):
        """测试夸克网盘未登录状态诊断"""
        mock_request.return_value = {"status": 401, "message": "require login [guest]"}
        client = QuarkPanClient("fake_cookie")
        stoken = client.get_stoken("fake_pwd_id")
        self.assertEqual(stoken, "")

    @patch("src.clients.uc_client.UcPanClient._request")
    def test_uc_diagnostics_on_capacity_limit(self, mock_request):
        """测试 UC 网盘容量不足诊断"""
        mock_request.return_value = {"status": 200, "message": "capacity limit[{0}]"}
        client = UcPanClient("fake_cookie")
        res = client._wait_task("task_123", retries=2)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
