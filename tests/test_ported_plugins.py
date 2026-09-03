import unittest
from src.services.plugin_manager import PluginManager
from src.plugins.base_plugin import BasePlugin


class PortedPluginsTest(unittest.TestCase):
    def setUp(self):
        self.mgr = PluginManager()

    def test_plugin_discovery_and_metadata(self):
        plugins = self.mgr.get_all_plugins()
        self.assertGreaterEqual(len(plugins), 100)

        # Batch 1 + 2 + 3 + 4 (100 plugins)
        expected_names = [
            # Batch 1 (20)
            "gying", "libvio", "dyyjpro", "duoduo", "feikuai",
            "gaoqing888", "hdmoli", "ikantv", "jutoushe", "kkv",
            "dy4k", "lingjisp", "lou1", "melost", "meitizy",
            "miosou", "nyaa", "pansearch", "qqpd", "quark4k",
            # Batch 2 (30)
            "quarksoo", "quarktv", "qupanshe", "sousou", "thepiratebay",
            "ting77", "wanou", "weibo", "xb6v", "xiaokupan",
            "xiaozhang", "xiaoyu", "yingso", "yulinshufa", "yunso",
            "yunsou", "zlxapp", "zxzj", "rrbt", "quarkres",
            "diduan", "erxiao", "huban", "labi", "muou",
            "shandian", "zhizhen", "aikanzy", "ash", "bixin",
            # Batch 3 (30)
            "ahhhhfs", "alupan", "cldi", "clmao", "clxiong",
            "cyg", "daishudj", "discourse", "djgou", "duanjuw",
            "dyyj", "haitunsou", "hdr4k", "hunhepan", "javdb",
            "jikepan", "jsnoteclub", "jupansou", "kkmao", "leijing",
            "mikuclub", "mizixing", "nsgame", "ouge", "pan666",
            "panlian", "panta", "panwiki", "panyq", "panzun",
            # Batch 4 (20)
            "pianku", "pioz", "qingying", "qiwei", "qupansou",
            "sdso", "susu", "u3c3", "wuji", "xdpan",
            "xdyh", "xiaoji", "xinjuc", "xuexizhinan", "xys",
            "yiove", "ypfxw", "yuhuage", "haisou", "miaoso"
        ]

        registered_names = [p.name for p in plugins]
        for name in expected_names:
            self.assertIn(name, registered_names, f"Plugin {name} should be registered in PluginManager")

    def test_plugin_search_handles_exceptions(self):
        plugins = self.mgr.get_all_plugins()
        for plugin_obj in plugins:
            self.assertIsInstance(plugin_obj, BasePlugin)
            res = plugin_obj.search("")
            self.assertEqual([], res)


if __name__ == "__main__":
    unittest.main()
