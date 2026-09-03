import json
import unittest
from unittest.mock import MagicMock, patch

from app import app
from src.pan_operator import create_share
from src.services.link_checker import (
    STATE_BAD,
    STATE_LOCKED,
    STATE_OK,
    STATE_UNSUPPORTED,
    LinkChecker,
    check_link,
    check_links_batch,
)


class LinkCheckerTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.checker = LinkChecker()
        # 清理缓存以避免用例间干扰
        with self.checker._cache_lock:
            self.checker._cache.clear()

    @patch("src.services.link_checker.requests.Session.post")
    @patch("src.services.link_checker.requests.Session.get")
    def test_check_quark_valid_and_invalid(self, mock_get, mock_post):
        # 1. 测试有效链接
        token_resp = MagicMock()
        token_resp.json.return_value = {"code": 0, "data": {"stoken": "mock_token"}}
        mock_post.return_value = token_resp

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "code": 0,
            "data": {
                "list": [{"file_name": "test.mp4"}],
                "share": {"status": 1, "partial_violation": False},
                "is_expire": False,
            },
        }
        mock_get.return_value = detail_resp

        res = self.checker.check_link("https://pan.quark.cn/s/validquark123")
        self.assertEqual(STATE_OK, res["state"])
        self.assertEqual("链接有效", res["summary"])

        # 2. 测试需提取码
        token_resp.json.return_value = {"code": 41008, "message": "需要提取码"}
        res = self.checker.check_link("https://pan.quark.cn/s/lockedquark123", force_refresh=True)
        self.assertEqual(STATE_LOCKED, res["state"])

        # 3. 测试失效链接
        token_resp.json.return_value = {"code": 41004, "message": "链接失效"}
        res = self.checker.check_link("https://pan.quark.cn/s/deadquark123", force_refresh=True)
        self.assertEqual(STATE_BAD, res["state"])

    @patch("src.services.link_checker.requests.Session.post")
    def test_check_aliyun(self, mock_post):
        # 1. 有效链接
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"share_name": "流浪地球", "file_count": 2, "share_status": "enabled"}
        mock_post.return_value = ok_resp

        res = self.checker.check_link("https://www.alipan.com/s/alivalid123")
        self.assertEqual(STATE_OK, res["state"])

        # 2. 失效链接
        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.json.return_value = {"code": "ShareLinkCancelled", "message": "分享已被取消"}
        mock_post.return_value = bad_resp

        res = self.checker.check_link("https://www.alipan.com/s/alibad123", force_refresh=True)
        self.assertEqual(STATE_BAD, res["state"])

    @patch("src.services.link_checker.requests.Session.get")
    def test_check_baidu(self, mock_get):
        # 1. 有效链接
        ok_resp = MagicMock()
        ok_resp.json.return_value = {"errno": 0, "list": [{"server_filename": "video.mkv"}]}
        mock_get.return_value = ok_resp

        res = self.checker.check_link("https://pan.baidu.com/s/1baidugood")
        self.assertEqual(STATE_OK, res["state"])

        # 2. 需提取码
        lock_resp = MagicMock()
        lock_resp.json.return_value = {"errno": -9, "errmsg": "验证码错误"}
        mock_get.return_value = lock_resp

        res = self.checker.check_link("https://pan.baidu.com/s/1baidulocked", force_refresh=True)
        self.assertEqual(STATE_LOCKED, res["state"])

        # 3. 链接失效
        dead_resp = MagicMock()
        dead_resp.json.return_value = {"errno": 115, "errmsg": "该文件已违规"}
        mock_get.return_value = dead_resp

        res = self.checker.check_link("https://pan.baidu.com/s/1baidudead", force_refresh=True)
        self.assertEqual(STATE_BAD, res["state"])

    @patch("src.services.link_checker.requests.Session.get")
    def test_check_123pan(self, mock_get):
        # 1. 有效
        ok_resp = MagicMock()
        ok_resp.json.return_value = {"code": 0, "message": "ok"}
        mock_get.return_value = ok_resp

        res = self.checker.check_link("https://www.123pan.com/s/pan123ok")
        self.assertEqual(STATE_OK, res["state"])

        # 2. 需提取码
        locked_resp = MagicMock()
        locked_resp.json.return_value = {"code": 10, "data": {"HasPwd": True}}
        mock_get.return_value = locked_resp

        res = self.checker.check_link("https://www.123pan.com/s/pan123locked", force_refresh=True)
        self.assertEqual(STATE_LOCKED, res["state"])

    @patch("src.services.link_checker.requests.Session.post")
    @patch("src.services.link_checker.requests.Session.get")
    def test_single_flight_and_caching(self, mock_get, mock_post):
        token_resp = MagicMock()
        token_resp.json.return_value = {"code": 0, "data": {"stoken": "tok1"}}
        mock_post.return_value = token_resp

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "code": 0,
            "data": {"list": [{"file_name": "f1"}], "share": {"status": 1}},
        }
        mock_get.return_value = detail_resp

        # 第一次请求
        res1 = self.checker.check_link("https://pan.quark.cn/s/cachetest1")
        self.assertFalse(res1["cache_hit"])
        self.assertEqual(STATE_OK, res1["state"])

        # 第二次请求同一 URL -> 命中缓存
        res2 = self.checker.check_link("https://pan.quark.cn/s/cachetest1")
        self.assertTrue(res2["cache_hit"])
        self.assertEqual(STATE_OK, res2["state"])

    def test_check_links_api_endpoints(self):
        # 测试 POST /api/check/links 参数校验
        resp = self.client.post("/api/check/links", json={})
        self.assertEqual(400, resp.status_code)

        # 测试 POST /api/check/links 批量检测
        with patch.object(self.checker, "check_link") as mock_check:
            mock_check.return_value = {"url": "https://pan.quark.cn/s/test", "state": STATE_OK, "summary": "链接有效"}
            resp = self.client.post("/api/check/links", json={
                "items": [{"url": "https://pan.quark.cn/s/test"}]
            })
            self.assertEqual(200, resp.status_code)
            data = resp.get_json()
            self.assertTrue(data.get("success"))
            self.assertEqual(1, len(data.get("results", [])))

        # 测试 GET /api/check/link
        with patch.object(self.checker, "check_link") as mock_check:
            mock_check.return_value = {"url": "https://pan.quark.cn/s/test", "state": STATE_OK}
            resp = self.client.get("/api/check/link?url=https://pan.quark.cn/s/test")
            self.assertEqual(200, resp.status_code)
            data = resp.get_json()
            self.assertTrue(data.get("success"))
            self.assertEqual(STATE_OK, data["data"]["state"])

    @patch("src.pan_operator.check_link")
    @patch("src.pan_operator.get_and_validate_credential")
    @patch("src.pan_operator._handle_netdisk_operation")
    def test_pan_operator_precheck_interception(self, mock_handle, mock_cred, mock_check):
        mock_cred.return_value = "mock_cookie_that_is_long_enough_to_pass_validation_12345678901234567890"
        
        # 1. 链接状态为 BAD 时，拦截转存并不调用底层 _handle_netdisk_operation
        mock_check.return_value = {"state": STATE_BAD, "summary": "链接已失效"}
        res = create_share({
            "share_url": "https://pan.quark.cn/s/deadlink",
            "save_to_netdisk": {"quark": True}
        })
        self.assertIsNone(res)
        mock_handle.assert_not_called()

        # 2. 链接状态为 LOCKED 且无密码时，拦截转存
        mock_check.return_value = {"state": STATE_LOCKED, "summary": "需要提取码"}
        res = create_share({
            "share_url": "https://pan.quark.cn/s/lockedlink",
            "save_to_netdisk": {"quark": True}
        })
        self.assertIsNone(res)
        mock_handle.assert_not_called()

        # 3. 链接状态为 OK 时，正常向下执行转存
        mock_check.return_value = {"state": STATE_OK, "summary": "链接有效"}
        mock_handle.return_value = ("file_123", "流浪地球", "https://pan.quark.cn/s/my_new_share")
        res = create_share({
            "share_url": "https://pan.quark.cn/s/goodlink",
            "save_to_netdisk": {"quark": True}
        })
        self.assertIsNotNone(res)
        mock_handle.assert_called_once()


if __name__ == "__main__":
    unittest.main()
