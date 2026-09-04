import unittest
import time
from unittest.mock import Mock, patch
import requests

from src.services import search_service
from src.services.telegram_search_service import (
    clean_telegram_title,
    extract_title_from_link_line,
    is_cloud_disk_label,
    parse_telegram_search_html,
    search_telegram_channel,
)

MULTI_RESOURCE_HTML = """
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="tgchannel/101">
    <div class="tgme_widget_message_date">
      <time datetime="2026-03-01T10:00:00+00:00"></time>
    </div>
    <div class="tgme_widget_message_text">
      🎬 【片名】：庆余年 第二季 (2024) 4K | @tgsearchers #国剧<br>
      夸克网盘：https://pan.quark.cn/s/qingyunian_quark<br>
      阿里云盘：https://www.alipan.com/s/qingyunian_ali<br>
      <br>
      🎬 剧名：繁花 (2023) 4K 杜比视界<br>
      夸克网盘：https://pan.quark.cn/s/fanhua_quark<br>
      百度网盘：https://pan.baidu.com/s/fanhua_baidu<br>
      提取码：7788<br>
    </div>
  </div>
</div>
"""

COMPOUND_LINE_HTML = """
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="tgchannel/102">
    <div class="tgme_widget_message_text">
      【热播短剧大合集】<br>
      重生之都市修仙：https://pan.quark.cn/s/duxiu123<br>
      绝世武神 4K：https://pan.baidu.com/s/wushen456 提取码: ab12<br>
    </div>
  </div>
</div>
"""


class TelegramParserTest(unittest.TestCase):
    def test_clean_telegram_title(self):
        dirty1 = "🎬 【片名】：繁花 (2023) 4K | 关注频道 @pansearch #国剧 #王家卫"
        self.assertEqual("繁花 (2023) 4K", clean_telegram_title(dirty1))

        dirty2 = "名称：周星驰电影合集"
        self.assertEqual("周星驰电影合集", clean_telegram_title(dirty2))

        dirty3 = "🏷️ 剧名: 庆余年 第二季"
        self.assertEqual("庆余年 第二季", clean_telegram_title(dirty3))

    def test_is_cloud_disk_label(self):
        self.assertTrue(is_cloud_disk_label("夸克网盘"))
        self.assertTrue(is_cloud_disk_label("百度云"))
        self.assertFalse(is_cloud_disk_label("繁花"))

    def test_extract_title_from_link_line(self):
        line1 = "重生之都市修仙：https://pan.quark.cn/s/111"
        self.assertEqual("重生之都市修仙", extract_title_from_link_line(line1))

        line2 = "夸克网盘：https://pan.quark.cn/s/111"
        self.assertIsNone(extract_title_from_link_line(line2))

    def test_multi_resource_message_pairing(self):
        results = parse_telegram_search_html(MULTI_RESOURCE_HTML, "tgchannel")
        self.assertEqual(4, len(results))

        qyn_quark = results[0]
        self.assertEqual("庆余年 第二季 (2024) 4K", qyn_quark.title)
        self.assertEqual("https://pan.quark.cn/s/qingyunian_quark", qyn_quark.share_link)

        fh_baidu = results[3]
        self.assertEqual("繁花 (2023) 4K 杜比视界", fh_baidu.title)
        self.assertEqual("https://pan.baidu.com/s/fanhua_baidu?pwd=7788", fh_baidu.share_link)
        self.assertEqual("7788", fh_baidu.password)

    def test_compound_line_list_pairing(self):
        results = parse_telegram_search_html(COMPOUND_LINE_HTML, "tgchannel")
        self.assertEqual(2, len(results))

        item1 = results[0]
        self.assertEqual("重生之都市修仙", item1.title)


class TelegramSearchServiceTest(unittest.TestCase):
    @patch("src.services.telegram_search_service.requests.get")
    def test_search_channel_skips_non_public_redirect(self, mock_get):
        response = Mock()
        response.url = "https://t.me/tgsearchers6"
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        self.assertEqual([], search_telegram_channel("流浪地球", "tgsearchers6"))

        with self.assertRaises(requests.RequestException):
            search_telegram_channel("流浪地球", "tgsearchers6", raise_on_error=True)

    @patch("src.services.telegram_search_service.requests.get")
    def test_search_channel_parses_public_preview(self, mock_get):
        response = Mock()
        response.url = "https://t.me/s/tgsearchers7?q=test"
        response.text = MULTI_RESOURCE_HTML
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        results = search_telegram_channel("流浪地球", "@tgsearchers7")
        self.assertEqual(4, len(results))


class TelegramSearchIntegrationTest(unittest.TestCase):
    @patch("src.services.search_service.plugin_manager.get_enabled_plugins", return_value=[])
    @patch("src.services.search_service.search_telegram_channel")
    @patch("src.services.search_service.get_enabled_channel_names", return_value=["slow_channel", "fast_channel"])
    @patch(
        "src.services.system_config_service.get_search_scheduler_config",
        return_value={"api": {"timeout": 10, "max_workers": 8}, "tg": {"enabled": True, "max_workers": 2, "timeout": 10, "proxy": ""}, "plugin": {"timeout": 10, "max_workers": 6}},
    )
    @patch("src.services.search_service.read_all_api_configs_from_db", return_value=[])
    def test_upstream_iterator_yields_each_tg_channel_when_ready(
        self,
        _mock_configs,
        _mock_tg_config,
        _mock_channels,
        mock_search_channel,
        _mock_plugins,
    ):
        def search_channel(_keyword, channel, **_kwargs):
            if channel == "slow_channel":
                time.sleep(0.05)
            return [["tg", channel, f"https://pan.quark.cn/s/{channel}", "夸克网盘"]]

        mock_search_channel.side_effect = search_channel

        results = list(search_service.iter_upstream_search_results("流浪地球"))
        self.assertEqual("fast_channel", results[0][0][1])
        self.assertEqual("slow_channel", results[1][0][1])

    @patch("src.services.search_service.filter_results_by_frontend_netdisks", side_effect=lambda value: value)
    @patch("src.services.search_service.iter_upstream_search_results")
    @patch("src.services.search_service.search_in_database", return_value=[])
    def test_public_search_includes_telegram_results(
        self,
        _mock_database,
        mock_upstreams,
        _mock_filter,
    ):
        mock_upstreams.return_value = iter([[
            ["tg", "流浪地球", "https://pan.quark.cn/s/abc123", "夸克网盘"]
        ]])

        success, _, results = search_service.search_public_resources("流浪地球")
        self.assertTrue(success)
        self.assertEqual(1, len(results))
        self.assertEqual("tg", results[0]["source"])


if __name__ == "__main__":
    unittest.main()
