import json
import unittest
from unittest.mock import patch, MagicMock

from src.clients.base_client import BasePanClient
from src.clients.guangya_client import GuangyaPanClient
from src.clients.wukong_client import WukongPanClient
from src.clients.caiyun_client import CaiyunPanClient
from src.utils.netdisk_utils import match_netdisk_link, extract_canonical_resource_key


class TestNewPanClients(unittest.TestCase):
    """测试新增的光鸭云盘、悟空网盘、移动云盘客户端"""

    def setUp(self):
        from src.db.system_configs import delete_config_value
        delete_config_value("custom_ad_injection_config")
        delete_config_value("ad_filter_config")

    def tearDown(self):
        from src.db.system_configs import delete_config_value
        delete_config_value("custom_ad_injection_config")
        delete_config_value("ad_filter_config")

    def test_client_inheritance(self):
        """验证所有新客户端均继承 BasePanClient"""
        self.assertTrue(issubclass(GuangyaPanClient, BasePanClient))
        self.assertTrue(issubclass(WukongPanClient, BasePanClient))
        self.assertTrue(issubclass(CaiyunPanClient, BasePanClient))

    def test_netdisk_matching(self):
        """测试网盘链接类型识别"""
        self.assertEqual(match_netdisk_link("https://www.guangyapan.com/s/abc12345"), "光鸭云盘")
        self.assertEqual(match_netdisk_link("https://pan.wkbrowser.com/s/xyz98765"), "悟空网盘")
        self.assertEqual(match_netdisk_link("https://yun.139.com/shareweb/#/w/i/10086abc"), "移动云盘")
        self.assertEqual(match_netdisk_link("https://caiyun.139.com/w/i/10086xyz"), "移动云盘")

    def test_canonical_resource_key(self):
        """测试资源唯一键提取"""
        k_guangya = extract_canonical_resource_key("https://www.guangyapan.com/s/abc12345?pwd=1234")
        self.assertEqual(k_guangya, "guangya:abc12345")

        k_wukong = extract_canonical_resource_key("https://pan.wkbrowser.com/s/xyz98765?pwd=5678")
        self.assertEqual(k_wukong, "wukong:xyz98765")

        k_mobile = extract_canonical_resource_key("https://yun.139.com/shareweb/#/w/i/10086abc")
        self.assertEqual(k_mobile, "mobile:10086abc")

    def test_guangya_client_url_parse(self):
        """测试光鸭云盘链接与提取码解析"""
        client = GuangyaPanClient("test_token")
        sid, pwd = client._parse_share_url("https://www.guangyapan.com/s/gy123456?pwd=8888")
        self.assertEqual(sid, "gy123456")
        self.assertEqual(pwd, "8888")

    def test_wukong_client_url_parse(self):
        """测试悟空网盘链接与提取码解析"""
        client = WukongPanClient("test_cookie")
        sid, pwd = client._parse_share_url("https://pan.wkbrowser.com/s/wk654321?pwd=6666")
        self.assertEqual(sid, "wk654321")
        self.assertEqual(pwd, "6666")

    def test_caiyun_client_url_parse(self):
        """测试移动云盘链接与提取码解析"""
        client = CaiyunPanClient("test_auth")
        sid, pwd = client._parse_share_url("https://yun.139.com/shareweb/#/w/i/cm123456?pwd=9999")
        self.assertEqual(sid, "cm123456")
        self.assertEqual(pwd, "9999")

    @patch("requests.Session.request")
    def test_guangya_store_and_delete(self, mock_request):
        """测试光鸭云盘转存与删除 mock"""
        client = GuangyaPanClient("fake_token")

        # Mock GET share detail
        mock_resp_detail = MagicMock()
        mock_resp_detail.status_code = 200
        mock_resp_detail.json.return_value = {
            "code": 0,
            "pass_code_token": "token_abc",
            "files": [{"id": "f_1", "name": "test_video.mp4"}],
        }

        # Mock POST restore
        mock_resp_restore = MagicMock()
        mock_resp_restore.status_code = 200
        mock_resp_restore.json.return_value = {"code": 0, "file_ids": ["f_1"]}

        # Mock POST create share
        mock_resp_share = MagicMock()
        mock_resp_share.status_code = 200
        mock_resp_share.json.return_value = {
            "code": 0,
            "data": {"share_url": "https://www.guangyapan.com/s/new_share_123"},
        }

        mock_request.side_effect = [mock_resp_detail, mock_resp_restore, mock_resp_share]

        fid, fname, share_url = client.store("https://www.guangyapan.com/s/gy123456")
        self.assertIn("f_1", fid)
        self.assertEqual(fname, "test_video.mp4")
        self.assertEqual(share_url, "https://www.guangyapan.com/s/new_share_123")

        # Mock Delete
        mock_resp_del = MagicMock()
        mock_resp_del.status_code = 200
        mock_resp_del.json.return_value = {"code": 0}
        mock_request.side_effect = [mock_resp_del]

        del_ok = client.del_file("f_1")
        self.assertTrue(del_ok)

    @patch("requests.Session.request")
    def test_wukong_store_and_delete(self, mock_request):
        """测试悟空网盘转存与删除 mock"""
        client = WukongPanClient("fake_cookie")

        # Mock share info
        mock_info = MagicMock()
        mock_info.status_code = 200
        mock_info.json.return_value = {
            "code": 0,
            "data": {"files": [{"file_id": "wk_f1", "name": "sample.pdf"}]},
        }

        # Mock save
        mock_save = MagicMock()
        mock_save.status_code = 200
        mock_save.json.return_value = {"code": 0, "data": {"file_ids": ["wk_f1"]}}

        # Mock create share
        mock_share = MagicMock()
        mock_share.status_code = 200
        mock_share.json.return_value = {
            "code": 0,
            "data": {"share_url": "https://pan.wkbrowser.com/s/new_wk_link"},
        }

        mock_request.side_effect = [mock_info, mock_save, mock_share]

        fid, fname, share_url = client.store("https://pan.wkbrowser.com/s/wk123")
        self.assertIn("wk_f1", fid)
        self.assertEqual(fname, "sample.pdf")
        self.assertEqual(share_url, "https://pan.wkbrowser.com/s/new_wk_link")

        # Mock Delete
        mock_del = MagicMock()
        mock_del.status_code = 200
        mock_del.json.return_value = {"code": 0}
        mock_request.side_effect = [mock_del]

        self.assertTrue(client.del_file(["wk_f1"]))

    def test_caiyun_store_and_delete(self):
        """转存完成后只分享目标目录中新生成的文件 ID。"""
        client = CaiyunPanClient({"token": "example", "account": "13800000000"})
        shared = [{"caID": "source-folder", "caName": "专辑", "path": "source/path"}]
        before = [{"fileId": "old-folder", "name": "专辑", "type": "folder"}]
        after = before + [{"fileId": "new-folder", "name": "专辑", "type": "folder"}]
        with patch.object(client, "_share_entries", return_value=({"lkName": "专辑"}, shared)), \
             patch.object(client, "_list_personal", side_effect=[before, after]), \
             patch.object(client, "_transfer", return_value=True) as transfer, \
             patch.object(client, "_create_share", return_value="https://yun.139.com/shareweb/#/w/i/new") as create:
            fid, fname, share_url = client.store("https://yun.139.com/shareweb/#/w/i/cy123")
        self.assertEqual(json.loads(fid), ["new-folder"])
        self.assertEqual(fname, "专辑")
        self.assertEqual(share_url, "https://yun.139.com/shareweb/#/w/i/new")
        transfer.assert_called_once()
        create.assert_called_once_with([], ["new-folder"], "专辑")

        with patch.object(client, "_request_signed_api", return_value={"code": "0"}) as request:
            self.assertTrue(client.del_file(fid))
        self.assertEqual(request.call_args.args[1], {"fileIds": ["new-folder"]})


if __name__ == "__main__":
    unittest.main()
