# tests/test_api_v1_link_status.py

import json
import unittest
from unittest.mock import MagicMock, patch

from app import app
from src.services.link_checker import STATE_BAD, STATE_LOCKED, STATE_OK


class ApiV1LinkStatusTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("src.routes.api_v1_routes.is_public_search_api_enabled", return_value=True)
    @patch("src.routes.api_v1_routes.search_public_resources")
    @patch("src.routes.api_v1_routes.check_links_batch")
    def test_search_with_check_status(self, mock_batch, mock_search, mock_api_enabled):
        mock_search.return_value = (
            True,
            "成功",
            [
                {
                    "title": "资源A",
                    "share_link": "https://pan.quark.cn/s/link1",
                    "cloud_name": "夸克网盘",
                },
                {
                    "title": "资源B",
                    "share_link": "https://pan.baidu.com/s/1link2",
                    "cloud_name": "百度网盘",
                },
            ],
        )
        mock_batch.return_value = [
            {"state": STATE_OK, "summary": "链接有效", "file_count": 3},
            {"state": STATE_BAD, "summary": "分享链接无文件或已失效", "file_count": 0},
        ]

        # 1. 开启 check_status
        resp = self.client.get("/api/v1/search?keyword=黑神话&scope=all&check_status=true")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(2, data["total"])
        self.assertEqual(STATE_OK, data["results"][0]["health_state"])
        self.assertEqual(3, data["results"][0]["file_count"])
        self.assertEqual(STATE_BAD, data["results"][1]["health_state"])

    @patch("src.routes.api_v1_routes.is_public_search_api_enabled", return_value=True)
    @patch("src.routes.api_v1_routes.search_public_resources")
    @patch("src.routes.api_v1_routes.check_links_batch")
    def test_search_with_filter_bad(self, mock_batch, mock_search, mock_api_enabled):
        mock_search.return_value = (
            True,
            "成功",
            [
                {
                    "title": "资源A (有效)",
                    "share_link": "https://pan.quark.cn/s/link1",
                    "cloud_name": "夸克网盘",
                },
                {
                    "title": "资源B (已失效空资源)",
                    "share_link": "https://pan.quark.cn/s/empty_link",
                    "cloud_name": "夸克网盘",
                },
            ],
        )
        mock_batch.return_value = [
            {"state": STATE_OK, "summary": "链接有效", "file_count": 1},
            {"state": STATE_BAD, "summary": "分享链接无效：文件列表为空", "file_count": 0},
        ]

        resp = self.client.get("/api/v1/search?keyword=黑神话&scope=all&filter_bad=true")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        # 自动剔除 STATE_BAD，仅剩 1 条
        self.assertEqual(1, data["total"])
        self.assertEqual("资源A (有效)", data["results"][0]["title"])

    @patch("src.routes.api_v1_routes.get_transfer_api_key", return_value=None)
    @patch("src.routes.api_v1_routes.check_link")
    def test_transfer_intercept_invalid_link(self, mock_check, mock_key):
        mock_check.return_value = {
            "state": STATE_BAD,
            "summary": "分享链接无效：文件列表为空",
            "disk_type": "夸克网盘",
        }

        payload = {
            "url": "https://pan.quark.cn/s/empty_or_dead",
            "title": "某电影",
            "netdisk_name": "夸克网盘",
        }
        resp = self.client.post("/api/v1/transfer", json=payload)
        self.assertEqual(422, resp.status_code)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertEqual("LINK_INVALID", data["code"])
        self.assertIn("文件列表为空", data["message"])

    @patch("src.routes.api_v1_routes.get_transfer_api_key", return_value=None)
    @patch("src.routes.api_v1_routes.check_link")
    def test_transfer_intercept_locked_without_password(self, mock_check, mock_key):
        mock_check.return_value = {
            "state": STATE_LOCKED,
            "summary": "需要提取码",
            "disk_type": "百度网盘",
        }

        payload = {
            "url": "https://pan.baidu.com/s/1needpwd",
            "title": "学习资料",
            "netdisk_name": "百度网盘",
        }
        resp = self.client.post("/api/v1/transfer", json=payload)
        self.assertEqual(422, resp.status_code)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertEqual("LINK_LOCKED", data["code"])
        self.assertIn("提取码", data["message"])

    @patch("src.routes.api_v1_routes.get_transfer_api_key", return_value=None)
    @patch("src.routes.api_v1_routes.check_link")
    @patch("src.routes.api_v1_routes.resolve_view_url")
    def test_transfer_skip_check_flag(self, mock_resolve, mock_check, mock_key):
        mock_resolve.return_value = {
            "url": "https://pan.quark.cn/s/relayed",
            "mode": "temp_share",
            "netdisk_name": "夸克网盘",
        }

        payload = {
            "url": "https://pan.quark.cn/s/already_checked",
            "title": "电影",
            "netdisk_name": "夸克网盘",
            "skip_check": True,
        }
        resp = self.client.post("/api/v1/transfer", json=payload)
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(0, mock_check.call_count)


if __name__ == "__main__":
    unittest.main()
