import unittest
from unittest.mock import MagicMock, patch

from src.plugins.sougs_plugin import SougsPlugin
from src.services.plugin_manager import plugin_manager


class SougsPluginTest(unittest.TestCase):
    def setUp(self):
        self.plugin = SougsPlugin()

    def test_plugin_discovery(self):
        loaded = plugin_manager.get_plugin("sougs")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.display_name, "搜网盘")

    @patch("src.plugins.sougs_plugin.cffi_requests")
    def test_search_and_polling_mock(self, mock_cffi_requests):
        mock_session = MagicMock()
        mock_cffi_requests.Session.return_value = mock_session

        # 模拟 1: 初始搜索请求返回 search_id 和 1 条初始数据
        init_resp = MagicMock()
        init_resp.json.return_value = {
            "data": {
                "search_id": "sid_999",
                "complete": False,
                "items": [
                    {
                        "title": "凡人修仙传 4K 全集",
                        "drive_type": "夸克网盘",
                        "share_link": "https://pan.quark.cn/s/sougs_test_111",
                        "created_at": "2026-09-24",
                    }
                ],
            }
        }

        # 模拟 2: 轮询请求返回第 2 条数据并标记 complete=True
        poll_resp = MagicMock()
        poll_resp.json.return_value = {
            "data": {
                "complete": True,
                "items": [
                    {
                        "title": "凡人修仙传 1080P",
                        "disk_name": "百度网盘",
                        "link": "https://pan.baidu.com/s/sougs_test_222",
                    }
                ],
            }
        }

        mock_session.get.side_effect = [init_resp, poll_resp]

        results = self.plugin.search("凡人修仙传")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "凡人修仙传 4K 全集")
        self.assertEqual(results[0].cloud_name, "夸克网盘")
        self.assertEqual(results[1].title, "凡人修仙传 1080P")
        self.assertEqual(results[1].cloud_name, "百度网盘")

    @patch("src.plugins.sougs_plugin.CURL_CFFI_AVAILABLE", False)
    def test_fallback_when_dependency_missing(self):
        plugin = SougsPlugin()
        results = plugin.search("凡人修仙传")
        self.assertEqual(results, [])
        is_ok, msg = plugin.health_check()
        self.assertFalse(is_ok)
        self.assertIn("缺少 curl_cffi", msg)


if __name__ == "__main__":
    unittest.main()
