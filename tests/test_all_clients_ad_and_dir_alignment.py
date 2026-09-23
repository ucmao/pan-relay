import json
import unittest
from unittest.mock import patch, MagicMock

from src.services.system_config_service import (
    get_custom_ad_injection_config,
    save_custom_ad_injection_config,
    get_ad_share_url_for_disk,
)
from src.clients.base_client import BasePanClient
from src.clients.quark_client import QuarkPanClient
from src.clients.uc_client import UcPanClient
from src.clients.baidu_client import BaiduPanClient
from src.clients.aliyun_client import AliyunPanClient
from src.clients.xunlei_client import XunleiPanClient
from src.clients.caiyun_client import CaiyunPanClient
from src.clients.guangya_client import GuangyaPanClient
from src.clients.wukong_client import WukongPanClient


class TestAllClientsAdAndDirAlignment(unittest.TestCase):
    """测试 8 大网盘客户端在目录管理、广告过滤与引流植入上的全面能力对齐"""

    def setUp(self):
        # 初始化自定义引流配置
        save_custom_ad_injection_config({
            "enabled": True,
            "ad_share_url": "https://pan.quark.cn/s/legacy_common",
            "ad_share_urls": {
                "quark": "https://pan.quark.cn/s/quark_ad_123",
                "uc": "https://drive.uc.cn/s/uc_ad_456",
                "baidu": "https://pan.baidu.com/s/baidu_ad_789?pwd=abcd",
                "aliyun": "https://www.alipan.com/s/ali_ad_999",
                "xunlei": "https://pan.xunlei.com/s/xl_ad_888?pwd=1234",
                "caiyun": "https://caiyun.139.com/w/i/cm_ad_777",
                "guangya": "https://www.guangyapan.com/s/gy_ad_666",
                "wukong": "https://pan.wkbrowser.com/s/wk_ad_555",
            }
        })

    def test_custom_ad_injection_config_persistence(self):
        """验证多网盘引流配置的持久化与精准路由读取"""
        cfg = get_custom_ad_injection_config()
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["ad_share_urls"]["quark"], "https://pan.quark.cn/s/quark_ad_123")
        self.assertEqual(cfg["ad_share_urls"]["baidu"], "https://pan.baidu.com/s/baidu_ad_789?pwd=abcd")

        self.assertEqual(get_ad_share_url_for_disk("夸克网盘"), "https://pan.quark.cn/s/quark_ad_123")
        self.assertEqual(get_ad_share_url_for_disk("UC网盘"), "https://drive.uc.cn/s/uc_ad_456")
        self.assertEqual(get_ad_share_url_for_disk("百度网盘"), "https://pan.baidu.com/s/baidu_ad_789?pwd=abcd")
        self.assertEqual(get_ad_share_url_for_disk("阿里云盘"), "https://www.alipan.com/s/ali_ad_999")
        self.assertEqual(get_ad_share_url_for_disk("迅雷网盘"), "https://pan.xunlei.com/s/xl_ad_888?pwd=1234")
        self.assertEqual(get_ad_share_url_for_disk("移动云盘"), "https://caiyun.139.com/w/i/cm_ad_777")
        self.assertEqual(get_ad_share_url_for_disk("光鸭云盘"), "https://www.guangyapan.com/s/gy_ad_666")
        self.assertEqual(get_ad_share_url_for_disk("悟空网盘"), "https://pan.wkbrowser.com/s/wk_ad_555")

    @patch("src.clients.aliyun_client.AliyunPanClient._refresh_access_token")
    def test_clients_have_alignment_methods(self, mock_ali_refresh):
        """验证所有 8 大网盘客户端均具备 get_or_create_dir、add_ad 与 BasePanClient 规范"""
        mock_ali_refresh.return_value = None
        clients = [
            QuarkPanClient("quark_cookie"),
            UcPanClient("uc_cookie"),
            BaiduPanClient("BDUSS=test"),
            AliyunPanClient("ali_refresh_token"),
            XunleiPanClient({"session_id": "test"}),
            CaiyunPanClient("caiyun_token"),
            GuangyaPanClient("gy_token"),
            WukongPanClient("wk_cookie"),
        ]
        for client in clients:
            self.assertIsInstance(client, BasePanClient)
            self.assertTrue(callable(getattr(client, "get_or_create_dir", None)))
            self.assertTrue(callable(getattr(client, "add_ad", None)))
            self.assertTrue(callable(getattr(client, "del_file", None)))
            self.assertTrue(callable(getattr(client, "store", None)))


    @patch("src.clients.baidu_client.BaiduPanClient._transfer_file")
    @patch("src.clients.baidu_client.BaiduPanClient._get_share_page_info")
    def test_baidu_client_add_ad(self, mock_get_info, mock_transfer):
        """测试百度网盘广告引流植入"""
        mock_get_info.return_value = ("share_123", "uk_456", [10001], ["广告.txt"])
        mock_transfer.return_value = 10002

        client = BaiduPanClient("BDUSS=mock")
        res = client.add_ad("/我的资源/电视剧")
        self.assertTrue(res)
        mock_transfer.assert_called_once()

    @patch("requests.Session.request")
    def test_aliyun_client_add_ad(self, mock_req):
        """测试阿里云盘广告引流植入"""
        client = AliyunPanClient("ali_token")
        client.drive_id = "test_drive_id"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = [
            {"file_infos": [{"file_id": "fid_ad_1"}]},  # get_share_by_anonymous
            {"share_token": "mock_token"},              # get_share_token
            {"responses": [{"body": {"file_id": "new_ad_fid"}}]},  # batch copy
        ]
        mock_req.return_value = mock_resp

        res = client.add_ad("root")
        self.assertTrue(res)

    @patch("src.clients.xunlei_client.XunleiPanClient._get_access_token")
    @patch("src.clients.xunlei_client.XunleiPanClient._request_pan")
    def test_xunlei_client_get_or_create_dir(self, mock_req, mock_token):
        """测试迅雷网盘目录自动获取/创建"""
        mock_token.return_value = "xl_token"
        mock_req.return_value = {"files": [{"id": "dir_xl_001", "name": "电影专区", "kind": "drive#folder"}]}

        client = XunleiPanClient({"session_id": "test"})
        dir_id = client.get_or_create_dir("电影专区")
        self.assertEqual(dir_id, "dir_xl_001")

    @patch("requests.Session.request")
    def test_caiyun_client_get_or_create_dir(self, mock_req):
        """测试移动云盘目录自动创建"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "data": {"catalogID": "cm_cat_123"}}
        mock_req.return_value = mock_resp

        client = CaiyunPanClient("mock_auth")
        cat_id = client.get_or_create_dir("动漫剧集")
        self.assertEqual(cat_id, "cm_cat_123")

    @patch("requests.Session.request")
    def test_guangya_client_add_ad(self, mock_req):
        """测试光鸭云盘引流广告植入"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = [
            {"files": [{"id": "gy_ad_fid_1"}], "pass_code_token": "token_123"},
            {"code": 0, "data": {"file_ids": ["gy_ad_fid_1"]}},
        ]
        mock_req.return_value = mock_resp

        client = GuangyaPanClient("mock_token")
        res = client.add_ad("0")
        self.assertTrue(res)

    @patch("requests.Session.request")
    def test_wukong_client_add_ad(self, mock_req):
        """测试悟空网盘引流广告植入"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = [
            {"code": 0, "data": {"files": [{"file_id": "wk_fid_1"}]}},
            {"code": 0, "data": {"file_ids": ["wk_fid_1"]}},
        ]
        mock_req.return_value = mock_resp

        client = WukongPanClient("mock_cookie")
        res = client.add_ad("0")
        self.assertTrue(res)



if __name__ == "__main__":
    unittest.main()
