import unittest
from src.services.plugin_manager import PluginManager
from src.plugins.base_plugin import BasePlugin


class PortedPluginsTest(unittest.TestCase):
    def setUp(self):
        self.mgr = PluginManager()

    def test_plugin_discovery_and_metadata(self):
        plugins = self.mgr.get_all_plugins()
        self.assertGreaterEqual(len(plugins), 1)

        expected_names = ["yunso", "pansearch", "clxiong"]

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
