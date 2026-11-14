"""数据库版本化迁移测试（src/db/migrations.py）。

所有数据库都建在系统临时目录，不会污染 data/。
"""

import glob
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import src.db.connection as conn_mod
import src.db.migrations as migrations

LEGACY_SCHEMA = os.path.join(os.path.dirname(__file__), "fixtures", "db", "legacy_schema_v0.sql")
CURRENT_SCHEMA = os.path.join(conn_mod.BASE_DIR, "schema_sqlite.sql")


class TestDbMigrations(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="pan_relay_mig_")
        self.db_path = os.path.join(self.tmpdir, "pan_relay.db")
        self.patcher = patch("src.db.connection.SQLITE_DB_PATH", self.db_path)
        self.patcher.start()
        # 默认搜索源初始化与迁移无关，跳过以加快测试
        self.seed_patcher = patch(
            "src.services.system_config_service.init_default_search_sources", lambda: None
        )
        self.seed_patcher.start()

    def tearDown(self):
        self.seed_patcher.stop()
        self.patcher.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---- helpers ---------------------------------------------------------

    def _init(self):
        conn_mod._db_initialized = False
        conn_mod.init_sqlite_db()

    def _query(self, sql, params=(), path=None):
        conn = sqlite3.connect(path or self.db_path)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def _version(self, path=None):
        return self._query("PRAGMA user_version;", path=path)[0][0]

    def _backups(self):
        return glob.glob(self.db_path + ".bak-*")

    def _make_legacy_db(self, cookies=None):
        """构造账号池版本之前的老库，cookie_config 中带有旧凭据。"""
        if cookies is None:
            cookies = [
                ("夸克网盘", "kps=abc"),
                ("迅雷网盘", json.dumps({"refresh_token": "rt1"})),
                ("百度网盘", "   "),  # 空凭据应被忽略
            ]
        conn = sqlite3.connect(self.db_path)
        with open(LEGACY_SCHEMA, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.executemany("INSERT INTO cookie_config (cloud_name, cookie) VALUES (?, ?)", cookies)
        conn.execute(
            "INSERT INTO resources (name, share_link, cloud_name) VALUES (?, ?, ?)",
            ("老资源", "https://pan.quark.cn/s/legacy", "夸克网盘"),
        )
        conn.commit()
        conn.close()

    def _accounts(self):
        return self._query(
            "SELECT cloud_name, account_name, credential FROM cloud_accounts ORDER BY id"
        )

    # ---- tests -----------------------------------------------------------

    def test_migration_versions_are_strictly_increasing(self):
        versions = [v for v, _, _ in migrations.MIGRATIONS]
        self.assertEqual(versions, sorted(set(versions)), "迁移版本号必须唯一且递增")
        self.assertEqual(versions[0], 1)
        self.assertEqual(migrations.LATEST_VERSION, versions[-1])

    def test_fresh_install_reaches_latest_without_backup(self):
        self._init()
        self.assertEqual(self._version(), migrations.LATEST_VERSION)
        self.assertEqual(self._backups(), [])
        self.assertEqual(self._accounts(), [])

    def test_legacy_db_is_backed_up_and_upgraded(self):
        self._make_legacy_db()
        self._init()

        self.assertEqual(self._version(), migrations.LATEST_VERSION)

        # 旧凭据导入账号池，空凭据被忽略
        self.assertEqual(
            self._accounts(),
            [
                ("夸克网盘", "夸克网盘-账号", "kps=abc"),
                ("迅雷网盘", "迅雷网盘-账号", json.dumps({"refresh_token": "rt1"})),
            ],
        )

        # 历史字段补齐、老数据保留
        cols = {row[1] for row in self._query("PRAGMA table_info(resources);")}
        self.assertTrue({"account_id", "origin_type", "cover_url"} <= cols)
        self.assertEqual(self._query("SELECT name FROM resources"), [("老资源",)])

        # 旧表保留，便于回溯
        self.assertEqual(self._query("SELECT COUNT(*) FROM cookie_config")[0][0], 3)

        # 升级前生成了一份 v0 备份，内容是原始老库
        backups = self._backups()
        self.assertEqual(len(backups), 1)
        self.assertIn(".bak-v0-", backups[0])
        self.assertEqual(self._version(backups[0]), 0)
        self.assertEqual(self._query("SELECT COUNT(*) FROM cookie_config", path=backups[0])[0][0], 3)

    def test_restart_is_idempotent(self):
        self._make_legacy_db()
        self._init()
        self._init()
        self.assertEqual(len(self._accounts()), 2)
        self.assertEqual(len(self._backups()), 1, "已是最新版本时不应再备份")

    def test_skips_clouds_already_configured_in_pool(self):
        """已按旧逻辑升级、并手动重新添加过夸克的用户：只补回缺失的网盘。"""
        self._make_legacy_db()
        conn = sqlite3.connect(self.db_path)
        migrations.ensure_legacy_columns(conn)
        with open(CURRENT_SCHEMA, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute(
            "INSERT INTO cloud_accounts (cloud_name, account_name, credential) VALUES (?, ?, ?)",
            ("夸克网盘", "我的夸克", "kps=new"),
        )
        conn.commit()
        conn.close()

        self._init()
        self.assertEqual(
            self._accounts(),
            [
                ("夸克网盘", "我的夸克", "kps=new"),
                ("迅雷网盘", "迅雷网盘-账号", json.dumps({"refresh_token": "rt1"})),
            ],
        )

    def test_failed_migration_rolls_back_and_blocks_startup(self):
        self._make_legacy_db()
        original = list(migrations.MIGRATIONS)
        last_version, desc, fn = original[-1]

        def broken(conn):
            fn(conn)  # 先写入部分数据，验证会被回滚
            raise RuntimeError("模拟迁移失败")

        with patch.object(migrations, "MIGRATIONS", original[:-1] + [(last_version, desc, broken)]):
            with self.assertRaises(RuntimeError):
                self._init()

        self.assertEqual(self._version(), last_version - 1)
        self.assertEqual(self._accounts(), [], "失败迁移写入的数据应被回滚")

        # 修复后重启可以继续升级
        self._init()
        self.assertEqual(self._version(), migrations.LATEST_VERSION)
        self.assertEqual(len(self._accounts()), 2)

    def test_backup_pruning_keeps_latest_n(self):
        self._make_legacy_db()
        for i in range(migrations.MAX_BACKUPS + 2):
            stale = f"{self.db_path}.bak-v0-2000010{i}-000000"
            open(stale, "w").close()
            os.utime(stale, (1_000_000 + i, 1_000_000 + i))

        self._init()
        backups = self._backups()
        self.assertEqual(len(backups), migrations.MAX_BACKUPS)
        newest = max(backups, key=os.path.getmtime)
        self.assertEqual(self._version(newest), 0)
        self.assertGreater(os.path.getsize(newest), 0, "最新备份应是真实快照而非占位文件")


if __name__ == "__main__":
    unittest.main()
