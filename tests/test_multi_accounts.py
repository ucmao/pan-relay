import os
import unittest
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

import src.configs.app_config
import src.db.connection

class TestMultiAccounts(unittest.TestCase):
    def setUp(self):
        import uuid
        self.db_path = os.path.abspath(f"data/test_acc_{uuid.uuid4().hex}.db")

        # Patch SQLITE_DB_PATH in both app_config and connection
        self.patcher1 = patch("src.configs.app_config.SQLITE_DB_PATH", self.db_path)
        self.patcher2 = patch("src.db.connection.SQLITE_DB_PATH", self.db_path)
        self.patcher1.start()
        self.patcher2.start()

        # Re-initialize DB
        import src.db.connection as conn_mod
        conn_mod._db_initialized = False
        conn_mod.init_sqlite_db()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        for f in [self.db_path, self.db_path + "-wal", self.db_path + "-shm"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_schema_and_columns(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check cloud_accounts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cloud_accounts'")
        self.assertIsNotNone(cursor.fetchone())

        # Check account_id in resources
        cursor.execute("PRAGMA table_info(resources)")
        res_cols = [r[1] for r in cursor.fetchall()]
        self.assertIn("account_id", res_cols)

        # Check account_id in temp_share
        cursor.execute("PRAGMA table_info(temp_share)")
        temp_cols = [r[1] for r in cursor.fetchall()]
        self.assertIn("account_id", temp_cols)

        conn.close()

    def test_account_crud(self):
        from src.db.accounts import (
            create_account,
            get_account_by_id,
            update_account,
            get_accounts_by_cloud,
            delete_account,
            record_account_transfer,
        )

        # 1. Create
        acc_id = create_account({
            "cloud_name": "夸克网盘",
            "account_name": "夸克主盘-01",
            "credential": "test_quark_cookie_1234567890",
            "priority": 1,
            "weight": 20,
            "total_space_bytes": 100 * 1024 * 1024 * 1024,
            "used_space_bytes": 30 * 1024 * 1024 * 1024,
        })
        self.assertIsNotNone(acc_id)

        # 2. Read
        acc = get_account_by_id(acc_id)
        self.assertEqual(acc["cloud_name"], "夸克网盘")
        self.assertEqual(acc["account_name"], "夸克主盘-01")
        self.assertEqual(acc["left_space_bytes"], 70 * 1024 * 1024 * 1024)

        # 3. Update
        update_account(acc_id, {"account_name": "夸克主盘-更新", "priority": 0})
        acc_updated = get_account_by_id(acc_id)
        self.assertEqual(acc_updated["account_name"], "夸克主盘-更新")
        self.assertEqual(acc_updated["priority"], 0)

        # 4. List by cloud
        list_accs = get_accounts_by_cloud("夸克网盘")
        self.assertEqual(len(list_accs), 1)

        # 5. Record transfer
        record_account_transfer(acc_id)
        acc_trans = get_account_by_id(acc_id)
        self.assertEqual(acc_trans["transferred_count"], 1)

        # 6. Delete
        del_res = delete_account(acc_id)
        self.assertTrue(del_res)
        self.assertIsNone(get_account_by_id(acc_id))

    def test_account_pool_scheduling(self):
        from src.db.accounts import create_account
        from src.services.account_pool_manager import AccountPoolManager

        pool_mgr = AccountPoolManager.get_instance()

        # Add two Baidu accounts with different priorities
        id1 = create_account({
            "cloud_name": "百度网盘",
            "account_name": "百度-主号",
            "credential": "BDUSS=test_baidu_cookie_one_very_long_string_12345678901234567890",
            "priority": 0,
            "total_space_bytes": 2000 * 1024 * 1024 * 1024,
            "used_space_bytes": 100 * 1024 * 1024 * 1024,
        })
        id2 = create_account({
            "cloud_name": "百度网盘",
            "account_name": "百度-备用号",
            "credential": "BDUSS=test_baidu_cookie_two_very_long_string_12345678901234567890",
            "priority": 1,
            "total_space_bytes": 1000 * 1024 * 1024 * 1024,
            "used_space_bytes": 50 * 1024 * 1024 * 1024,
        })

        # Priority 0 should be selected first
        acc, client = pool_mgr.select_account_for_transfer("百度网盘")
        self.assertIsNotNone(acc)
        self.assertEqual(acc["id"], id1)

        # Report failure on id1 as fatal
        pool_mgr.report_failure(id1, "Cookie expired", is_fatal=True)

        # Next select should failover to id2
        acc2, client2 = pool_mgr.select_account_for_transfer("百度网盘")
        self.assertIsNotNone(acc2)
        self.assertEqual(acc2["id"], id2)

    def test_temp_share_and_resource_account_id(self):
        from src.db.resources import insert_resource, get_resource_by_share_link
        from src.db.temp_shares import create_temp_share_record, list_expired_temp_shares

        # Test resource with account_id
        res_id = insert_resource({
            "name": "测试电影",
            "file_id": "fid_999",
            "share_link": "https://pan.quark.cn/s/test12345678",
            "cloud_name": "夸克网盘",
            "account_id": 42,
        })
        self.assertIsNotNone(res_id)
        saved_res = get_resource_by_share_link("https://pan.quark.cn/s/test12345678")
        self.assertEqual(saved_res["account_id"], 42)

        # Test temp_share with account_id
        temp_id = create_temp_share_record(
            original_url="https://pan.quark.cn/s/orig123",
            title="测试临时分享",
            cloud_name="夸克网盘",
            temp_share_url="https://pan.quark.cn/s/new123",
            file_id="temp_fid_888",
            account_id=42,
        )
        self.assertIsNotNone(temp_id)

        # Update expires_at to the past
        from src.db.connection import get_db_connection
        conn = get_db_connection()
        conn.execute("UPDATE temp_share SET expires_at = datetime('now', '-1 minute') WHERE id = ?", (temp_id,))
        conn.commit()
        conn.close()

        expired = list_expired_temp_shares(limit=10)
        matched = [e for e in expired if e["id"] == temp_id]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["account_id"], 42)

    def test_admin_api_endpoints(self):
        from app import app
        from src.utils.auth_utils import create_jwt_token
        import json

        token = create_jwt_token()
        with app.test_client() as client:
            client.set_cookie("token", token)

            # 1. Create account via POST /admin/api/accounts
            post_res = client.post(
                "/admin/api/accounts",
                data=json.dumps({
                    "cloud_name": "阿里云盘",
                    "account_name": "阿里测试号-01",
                    "credential": "test_refresh_token_xyz123456",
                    "priority": 2,
                    "weight": 10,
                    "auto_test": False,
                }),
                content_type="application/json",
            )
            self.assertEqual(post_res.status_code, 200)
            post_data = json.loads(post_res.data)
            self.assertTrue(post_data["success"])
            acc_id = post_data["account"]["id"]

            # 2. List accounts via GET /admin/api/accounts
            get_res = client.get("/admin/api/accounts")
            self.assertEqual(get_res.status_code, 200)
            get_data = json.loads(get_res.data)
            self.assertTrue(get_data["success"])
            self.assertGreaterEqual(len(get_data["accounts"]), 1)

            # 3. Update account via PUT /admin/api/accounts/<id>
            put_res = client.put(
                f"/admin/api/accounts/{acc_id}",
                data=json.dumps({"account_name": "阿里测试号-改名"}),
                content_type="application/json",
            )
            self.assertEqual(put_res.status_code, 200)
            put_data = json.loads(put_res.data)
            self.assertEqual(put_data["account"]["account_name"], "阿里测试号-改名")

            # 4. Delete account via DELETE /admin/api/accounts/<id>
            del_res = client.delete(f"/admin/api/accounts/{acc_id}")
            self.assertEqual(del_res.status_code, 200)
            del_data = json.loads(del_res.data)
            self.assertTrue(del_data["success"])


if __name__ == "__main__":
    unittest.main()

