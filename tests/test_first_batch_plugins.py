import base64
import time
import unittest
from unittest.mock import MagicMock, patch

from src.configs.app_config import DEFAULT_PLUGIN_SETTINGS
from src.models.search_item import SearchResultItem
from src.plugins.hunhepan_plugin import HunhepanPlugin
from src.plugins.ikantv_plugin import IkanTVPlugin
from src.plugins.nyaa_plugin import NyaaPlugin
from src.plugins.ouge_plugin import OugePlugin
from src.plugins.quark4k_plugin import Quark4KPlugin
from src.plugins.quarksoo_plugin import QuarksooPlugin
from src.plugins.yunso_plugin import YunsoPlugin
from src.plugins.base_plugin import BasePlugin
from src.services.plugin_manager import PluginManager


def response(*, payload=None, text="", status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.text = text
    if payload is not None:
        mock.json.return_value = payload
    return mock


class FirstBatchPluginsTest(unittest.TestCase):
    expected_names = {"ikantv", "hunhepan", "ouge", "quark4k", "quarksoo", "yunso", "nyaa"}

    def test_all_plugins_are_discovered_with_synced_defaults(self):
        plugins = {plugin.name: plugin for plugin in PluginManager().get_all_plugins()}
        self.assertTrue(self.expected_names.issubset(plugins))
        for name in self.expected_names:
            self.assertEqual(DEFAULT_PLUGIN_SETTINGS[name], plugins[name].publish_by_default)

    def test_ikantv_parses_supported_links(self):
        plugin = IkanTVPlugin()
        plugin.request = MagicMock(return_value=response(payload={
            "code": 0,
            "data": [{
                "title": "三体全集",
                "datetime": "2026-01-02T03:04:05Z",
                "links": [
                    {"type": "quark", "url": "https://pan.quark.cn/s/threebody", "password": "7788"},
                    {"type": "unknown", "url": "https://example.com/file"},
                ],
            }],
        }))
        items = plugin.search("三体")
        self.assertEqual(1, len(items))
        self.assertEqual("夸克网盘", items[0].cloud_name)
        self.assertEqual("7788", items[0].password)

    def test_hunhepan_keeps_partial_success(self):
        plugin = HunhepanPlugin()
        record = {
            "disk_name": "庆余年 4K",
            "link": "https://pan.baidu.com/s/qingyu?pwd=1234",
            "disk_pass": "1234",
            "shared_time": "2026-01-02 03:04:05",
        }
        plugin._search_endpoint = MagicMock(side_effect=[[record], RuntimeError("down"), [], []])
        items = plugin.search("庆余年")
        self.assertEqual(1, len(items))
        self.assertEqual("百度网盘", items[0].cloud_name)

    def test_ouge_splits_provider_groups(self):
        plugin = OugePlugin()
        plugin.request = MagicMock(return_value=response(payload={
            "code": 1,
            "list": [{
                "vod_name": "阿凡达",
                "vod_down_from": "KG$$$BD",
                "vod_down_url": "https://pan.quark.cn/s/avatar$$$https://pan.baidu.com/s/avatar2?pwd=5566",
            }],
        }))
        items = plugin.search("阿凡达")
        self.assertEqual({"夸克网盘", "百度网盘"}, {item.cloud_name for item in items})

    def test_quark4k_reads_links_from_included_post(self):
        plugin = Quark4KPlugin()
        payload = {
            "data": [{
                "id": "1",
                "attributes": {"title": "三体 4K", "createdAt": "2026-01-02T03:04:05Z"},
                "relationships": {"mostRelevantPost": {"data": {"id": "post-1"}}},
            }],
            "included": [{
                "type": "posts",
                "id": "post-1",
                "attributes": {"contentHtml": '<a href="https://pan.quark.cn/s/4kthree">保存</a>'},
            }],
        }
        plugin._fetch_page = MagicMock(side_effect=[payload, {"data": [], "included": []}])
        items = plugin.search("三体")
        self.assertEqual(1, len(items))
        self.assertEqual("https://pan.quark.cn/s/4kthree", items[0].share_link)

    def test_quarksoo_parses_quark_link(self):
        plugin = QuarksooPlugin()
        plugin.request = MagicMock(return_value=response(text="""
            <table><tr><td>庆余年 第二季</td><td><a href="https://pan.quark.cn/s/qing2">保存</a></td></tr></table>
        """))
        items = plugin.search("庆余年")
        self.assertEqual(1, len(items))
        self.assertIn("pan.quark.cn", items[0].share_link)

    def test_yunso_decodes_xor_link(self):
        plugin = YunsoPlugin()
        raw = b"https://pan.quark.cn/s/yunso-three"
        encoded = bytes(byte ^ plugin.decrypt_key[index % len(plugin.decrypt_key)] for index, byte in enumerate(raw))
        encrypted = base64.b64encode(encoded).decode()
        fragment = f"""
            <div class="layui-card" data-qid="q1">
              <div class="layui-card-header">2026-01-02 03:04:05</div>
              <a onclick="open_sid()" url="{encrypted}" pa="8899">三体</a>
            </div>
        """
        plugin.request = MagicMock(return_value=response(payload={"code": 0, "data": fragment}))
        items = plugin.search("三体")
        self.assertEqual(1, len(items))
        self.assertEqual(raw.decode(), items[0].share_link)
        self.assertEqual("8899", items[0].password)

    def test_nyaa_parses_magnet(self):
        plugin = NyaaPlugin()
        plugin.request = MagicMock(return_value=response(text="""
            <table class="torrent-list"><tbody><tr>
              <td><a title="Anime"></a></td>
              <td colspan="2"><a href="/view/1">三体 动画</a></td>
              <td><a href="magnet:?xt=urn:btih:ABCDEF123456">磁力</a></td>
              <td data-timestamp="1700000000"></td>
            </tr></tbody></table>
        """))
        items = plugin.search("三体")
        self.assertEqual(1, len(items))
        self.assertEqual("磁力链接", items[0].cloud_name)


class PluginTimeoutTest(unittest.TestCase):
    def test_search_all_returns_without_waiting_for_slow_plugin(self):
        class SlowPlugin(BasePlugin):
            name = "slow"
            is_enabled = True
            timeout = 0.05

            def search(self, keyword):
                time.sleep(0.3)
                return [SearchResultItem("plugin:slow", keyword, "https://pan.quark.cn/s/slow", "夸克网盘")]

        manager = PluginManager()
        with manager._plugin_lock:
            previous = manager._plugins
            manager._plugins = {"slow": SlowPlugin()}
        try:
            started = time.monotonic()
            items = manager.search_all("超时", max_workers=1)
            elapsed = time.monotonic() - started
        finally:
            with manager._plugin_lock:
                manager._plugins = previous

        self.assertEqual([], items)
        self.assertLess(elapsed, 0.2)


if __name__ == "__main__":
    unittest.main()
