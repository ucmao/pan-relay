import unittest
from unittest.mock import Mock, patch

from src.services import search_service
from src.services.telegram_search_service import (
    parse_telegram_search_html,
    search_telegram_channel,
)


SAMPLE_HTML = """
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="tgsearchers7/123">
    <div class="tgme_widget_message_text">
      <b>流浪地球 1-2 合集</b><br>
      夸克：<a href="https://pan.quark.cn/s/abc123">打开</a><br>
      百度：https://pan.baidu.com/s/xyz789?pwd=1234
    </div>
  </div>
</div>
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="tgsearchers7/124">
    <div class="tgme_widget_message_text">
      无关网页 <a href="https://example.com/test">打开</a>
    </div>
  </div>
</div>
"""

SAMPLE_PASSWORD_HTML = """
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="tgsearchers7/125">
    <div class="tgme_widget_message_text">
      <b>大奉打更人</b><br>
      百度网盘：https://pan.baidu.com/s/testbaidu123<br>
      提取码：5678<br>
      天翼云盘：https://cloud.189.cn/t/test189（访问码：abcd）<br>
      115网盘：<a href="https://115.com/s/test115">打开</a> 密码：9999
    </div>
  </div>
</div>
"""


class TelegramSearchServiceTest(unittest.TestCase):
    def test_parse_telegram_search_html_extracts_supported_links(self):
        results = parse_telegram_search_html(SAMPLE_HTML, "tgsearchers7")

        self.assertEqual(2, len(results))
        self.assertEqual("tg", results[0][0])
        self.assertEqual("流浪地球 1-2 合集", results[0][1])
        self.assertEqual("夸克网盘", results[0][3])
        self.assertEqual("https://pan.quark.cn/s/abc123", results[0][2])
        self.assertEqual("百度网盘", results[1][3])
        self.assertEqual("https://pan.baidu.com/s/xyz789?pwd=1234", results[1][2])

    def test_parse_telegram_search_html_extracts_passwords(self):
        results = parse_telegram_search_html(SAMPLE_PASSWORD_HTML, "tgsearchers7")

        self.assertEqual(3, len(results))

        baidu_item = next(r for r in results if r[3] == "百度网盘")
        self.assertEqual("https://pan.baidu.com/s/testbaidu123?pwd=5678", baidu_item[2])

        tianyi_item = next(r for r in results if r[3] == "天翼云盘")
        self.assertEqual("https://cloud.189.cn/t/test189?pwd=abcd", tianyi_item[2])

        pan115_item = next(r for r in results if r[3] == "115网盘")
        self.assertEqual("https://115.com/s/test115?password=9999", pan115_item[2])

    @patch("src.services.telegram_search_service.requests.get")
    def test_search_channel_skips_non_public_redirect(self, mock_get):
        response = Mock()
        response.url = "https://t.me/tgsearchers6"
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        self.assertEqual([], search_telegram_channel("流浪地球", "tgsearchers6"))

    @patch("src.services.telegram_search_service.requests.get")
    def test_search_channel_parses_public_preview(self, mock_get):
        response = Mock()
        response.url = "https://t.me/s/tgsearchers7?q=test"
        response.text = SAMPLE_HTML
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        results = search_telegram_channel("流浪地球", "@tgsearchers7")

        self.assertEqual(2, len(results))
        mock_get.assert_called_once()


class TelegramSearchIntegrationTest(unittest.TestCase):
    @patch("src.services.search_service.filter_results_by_frontend_netdisks", side_effect=lambda value: value)
    @patch("src.services.search_service.search_telegram_resources")
    @patch("src.services.search_service.read_all_api_configs_from_db", return_value=[])
    @patch("src.services.search_service.search_in_database", return_value=[])
    def test_public_search_includes_telegram_results(
        self,
        _mock_database,
        _mock_configs,
        mock_telegram,
        _mock_filter,
    ):
        mock_telegram.return_value = [
            ["tg", "流浪地球", "https://pan.quark.cn/s/abc123", "夸克网盘"]
        ]

        success, _, results = search_service.search_public_resources("流浪地球")

        self.assertTrue(success)
        self.assertEqual(1, len(results))
        self.assertEqual("tg", results[0]["source"])


if __name__ == "__main__":
    unittest.main()
