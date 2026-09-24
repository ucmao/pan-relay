import unittest
from unittest.mock import MagicMock, patch

from src.plugins.http_plugin import PluginRequestError
from src.plugins.yingpanshe_plugin import YingpanshePlugin
from src.services.plugin_manager import plugin_manager


class YingpanshePluginTest(unittest.TestCase):
    def setUp(self):
        self.plugin = YingpanshePlugin()

    def test_plugin_discovery(self):
        loaded_plugin = plugin_manager.get_plugin("yingpanshe")
        self.assertIsNotNone(loaded_plugin)
        self.assertEqual(loaded_plugin.display_name, "影盘社")

    @patch.object(YingpanshePlugin, "request")
    def test_search_parsing(self, mock_request):
        sample_html = """
        <html>
        <body>
            <article class="search-item">
                <a class="search-item-title" href="https://pan.quark.cn/s/abcdef123456">凡人修仙传 4K 全集</a>
                <span class="search-item-logo">夸克网盘</span>
                <div class="search-item-info">资源更新极快</div>
                <span class="search-item-meta">动漫</span>
                <span class="search-item-meta">2026-09-24</span>
                <a class="search-item-action" href="/detail/12345">查看</a>
            </article>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.text = sample_html
        mock_request.return_value = mock_response

        results = self.plugin.search("凡人修仙传")
        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item.title, "凡人修仙传 4K 全集")
        self.assertEqual(item.share_link, "https://pan.quark.cn/s/abcdef123456")
        self.assertEqual(item.cloud_name, "夸克网盘")
        self.assertEqual(item.datetime, "2026-09-24 00:00:00")

    @patch.object(YingpanshePlugin, "request")
    def test_empty_or_error_search(self, mock_request):
        mock_request.side_effect = PluginRequestError("HTTP 500")
        results = self.plugin.search("测试")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
