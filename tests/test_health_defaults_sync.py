import json
import os
import tempfile
import unittest

from scripts.check_sources_health import sync_api_defaults, sync_preset_defaults


class HealthDefaultsSyncTestCase(unittest.TestCase):
    def test_sync_api_defaults_replaces_initial_rows_and_statuses(self):
        configs = [
            {
                "id": 1,
                "name": "健康接口",
                "url": "https://new.example?q=[[keyword]]",
                "method": "GET",
                "request": "",
                "response": "data[*].[name, url]",
                "status": True,
                "response_time_ms": 123,
                "is_enabled": True,
            },
            {
                "id": 2,
                "name": "失效接口",
                "url": "https://dead.example",
                "method": "GET",
                "request": "",
                "response": "data",
                "status": False,
                "response_time_ms": 456,
                "is_enabled": False,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "api_configs_preset.json")
            sync_api_defaults(path, configs)

            with open(path, "r", encoding="utf-8") as file:
                updated_json = json.load(file)

        self.assertEqual(2, len(updated_json))
        self.assertEqual("健康接口", updated_json[0]["name"])
        self.assertEqual("healthy", updated_json[0]["status"])
        self.assertEqual(1, updated_json[0]["is_enabled"])
        self.assertEqual("unhealthy", updated_json[1]["status"])
        self.assertEqual(0, updated_json[1]["is_enabled"])

    def test_sync_preset_defaults_updates_tg_and_plugins(self):
        tg_data = [
            {"channel": "healthy_one", "title": "健康1", "is_enabled": True},
            {"channel": "healthy_two", "title": "健康2", "is_enabled": True},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            tg_path = os.path.join(temp_dir, "tg_channels_preset.json")
            plugin_path = os.path.join(temp_dir, "plugin_settings_preset.json")

            with open(tg_path, "w", encoding="utf-8") as f:
                json.dump(tg_data, f, ensure_ascii=False, indent=2)

            sync_preset_defaults(
                tg_path,
                plugin_path,
                ["healthy_two"],
                {"healthy_plugin": True, "dead_plugin": False},
            )

            with open(tg_path, "r", encoding="utf-8") as f:
                updated_tg = json.load(f)

            with open(plugin_path, "r", encoding="utf-8") as f:
                updated_plugins = json.load(f)

        self.assertTrue(updated_tg[0]["is_enabled"])
        self.assertFalse(updated_tg[1]["is_enabled"])
        self.assertTrue(updated_plugins["healthy_plugin"])
        self.assertFalse(updated_plugins["dead_plugin"])


if __name__ == "__main__":
    unittest.main()
