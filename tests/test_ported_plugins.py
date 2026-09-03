import unittest
from src.services.plugin_manager import PluginManager
from src.plugins.base_plugin import BasePlugin


class PortedPluginsTest(unittest.TestCase):
    def setUp(self):
        self.mgr = PluginManager()

    def test_plugin_discovery_and_metadata(self):
        plugins = self.mgr.get_all_plugins()
        self.assertGreaterEqual(len(plugins), 20)

        # Verify batch 1 plugins exist in manager
        batch1_names = [
            "gying", "libvio", "dyyjpro", "duoduo", "feikuai",
            "gaoqing888", "hdmoli", "ikantv", "jutoushe", "kkv",
            "dy4k", "lingjisp", "lou1", "melost", "meitizy",
            "miosou", "nyaa", "pansearch", "qqpd", "quark4k"
        ]

        registered_names = [p.name for p in plugins]
        for name in batch1_names:
            self.assertIn(name, registered_names, f"Plugin {name} should be registered in PluginManager")

    def test_plugin_search_handles_exceptions(self):
        plugins = self.mgr.get_all_plugins()
        for plugin_obj in plugins:
            self.assertIsInstance(plugin_obj, BasePlugin)
            res = plugin_obj.search("")
            self.assertEqual([], res)


if __name__ == "__main__":
    unittest.main()
