import unittest
from unittest.mock import MagicMock, patch

from src.clients.baidu_client import BaiduPanClient
from src.pan_operator import _handle_netdisk_operation


class TestBaiduPanClient(unittest.TestCase):
    @patch.object(BaiduPanClient, "_get_bdstoken", return_value="mock_bdstoken")
    def test_init_cookies(self, mock_bdstoken):
        credential = "BAIDUID=test_baiduid; BDUSS=test_bduss"
        client = BaiduPanClient(credential)

        # Cookie should not be in headers as a fixed string
        self.assertNotIn("Cookie", client.session.headers)
        # Cookies should be loaded into session.cookies
        cookies = client.session.cookies.get_dict()
        self.assertEqual(cookies.get("BAIDUID"), "test_baiduid")
        self.assertEqual(cookies.get("BDUSS"), "test_bduss")

    @patch.object(BaiduPanClient, "_get_bdstoken", return_value="mock_bdstoken")
    def test_parse_share_url(self, mock_bdstoken):
        client = BaiduPanClient("BDUSS=123")

        # Standard url with pwd parameter
        url1 = "https://pan.baidu.com/s/12QWCylk4Cwl2KDuDyosxpw?pwd=lcfl"
        surl1, pwd1 = client._parse_share_url(url1)
        self.assertEqual(surl1, "2QWCylk4Cwl2KDuDyosxpw")
        self.assertEqual(pwd1, "lcfl")

        # Standard url with chinese extraction code
        url2 = "https://pan.baidu.com/s/12QWCylk4Cwl2KDuDyosxpw 提取码: lcfl"
        surl2, pwd2 = client._parse_share_url(url2)
        self.assertEqual(surl2, "2QWCylk4Cwl2KDuDyosxpw")
        self.assertEqual(pwd2, "lcfl")

        # Share init url
        url3 = "https://pan.baidu.com/share/init?surl=2QWCylk4Cwl2KDuDyosxpw&pwd=abcd"
        surl3, pwd3 = client._parse_share_url(url3)
        self.assertEqual(surl3, "2QWCylk4Cwl2KDuDyosxpw")
        self.assertEqual(pwd3, "abcd")

    @patch.object(BaiduPanClient, "_get_bdstoken", return_value="mock_bdstoken")
    def test_verify_pwd_and_transfer(self, mock_bdstoken):
        client = BaiduPanClient("BDUSS=123")

        # Mock requests
        def mock_request(method, url, params=None, data=None, headers=None):
            if "share/verify" in url:
                return {"errno": 0, "randsk": "test_randsk_value"}
            if "share/transfer" in url:
                # Check that sekey is passed in params
                if params.get("sekey") == "test_randsk_value":
                    return {"errno": 0, "extra": {}}
                return {"errno": 200025, "show_msg": "提取码输入错误，请重试"}
            if "api/list" in url:
                return {
                    "errno": 0,
                    "list": [{"server_filename": "FaceFusion", "fs_id": 999888}],
                }
            if "share/set" in url:
                return {"errno": 0, "shorturl": "https://pan.baidu.com/s/1newshare"}
            return {}

        client._request = MagicMock(side_effect=mock_request)

        # Mock _get_share_page_info
        client._get_share_page_info = MagicMock(
            return_value=("123456", "654321", ["111222"], ["FaceFusion"])
        )

        full_path, file_name, new_share_link = client.store(
            "https://pan.baidu.com/s/12QWCylk4Cwl2KDuDyosxpw?pwd=lcfl"
        )

        self.assertEqual(file_name, "FaceFusion")
        self.assertEqual(full_path, "/FaceFusion")
        self.assertTrue(new_share_link.startswith("https://pan.baidu.com/s/1newshare?pwd="))
        self.assertEqual(client.randsk, "test_randsk_value")

    @patch.object(BaiduPanClient, "del_file", return_value=True)
    def test_handle_netdisk_operation_delete(self, mock_del_file):
        status = _handle_netdisk_operation(
            client_class=BaiduPanClient,
            client_credential="BDUSS=123",
            share_url="https://pan.baidu.com/s/1abc",
            operation="delete",
            file_id="/test_file.txt",
        )
        self.assertTrue(status)
        mock_del_file.assert_called_once_with(["/test_file.txt"])


if __name__ == "__main__":
    unittest.main()
