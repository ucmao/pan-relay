import os
import tempfile
import unittest

from scripts.check_sources_health import sync_api_defaults, sync_app_defaults


class HealthDefaultsSyncTestCase(unittest.TestCase):
    def test_sync_api_defaults_replaces_initial_rows_and_statuses(self):
        schema = """-- schema
INSERT OR IGNORE INTO api_config (name, url, method, request, response, status, response_time_ms, is_enabled) VALUES
('旧接口', 'https://old.example', 'get', '', 'data', 1, 1, 1);

-- ----------------------------
-- Default data for `resources`
-- ----------------------------
"""
        configs = [
            {
                "id": 1,
                "name": "健康'接口",
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
            path = os.path.join(temp_dir, "schema_sqlite.sql")
            with open(path, "w", encoding="utf-8") as file:
                file.write(schema)

            sync_api_defaults(path, configs)

            with open(path, "r", encoding="utf-8") as file:
                updated = file.read()

        self.assertIn("健康''接口", updated)
        self.assertIn("'data[*].[name, url]', 1, 123, 1", updated)
        self.assertIn("'data', 0, 456, 0", updated)
        self.assertNotIn("旧接口", updated)

    def test_sync_app_defaults_updates_tg_and_plugins(self):
        config = """DEFAULT_TG_CHANNELS = (
    "old_channel"
)
DEFAULT_DISABLED_TG_CHANNELS = ()

DEFAULT_PLUGIN_SETTINGS = {
    "old_plugin": True,
}
TG_CHANNELS = []
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "app_config.py")
            with open(path, "w", encoding="utf-8") as file:
                file.write(config)

            sync_app_defaults(
                path,
                ["healthy_one", "healthy_two"],
                ["healthy_two"],
                {"healthy_plugin": True, "dead_plugin": False},
            )

            with open(path, "r", encoding="utf-8") as file:
                updated = file.read()

        self.assertIn('"healthy_one,healthy_two"', updated)
        self.assertIn('DEFAULT_DISABLED_TG_CHANNELS = (\n    "healthy_two"', updated)
        self.assertIn("'healthy_plugin': True", updated)
        self.assertIn("'dead_plugin': False", updated)
        self.assertNotIn("old_plugin", updated)


if __name__ == "__main__":
    unittest.main()
