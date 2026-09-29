import os
import unittest
import sqlite3
import uuid
import io
from unittest.mock import patch, MagicMock

import src.configs.app_config
import src.db.connection
from src.db.accounts import create_account, get_all_accounts
from src.services.account_csv_service import (
    export_accounts_csv,
    generate_accounts_template_csv,
    import_accounts_from_csv,
    normalize_cloud_name,
)
from app import app


class TestAccountCSV(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.abspath(f"data/test_acc_csv_{uuid.uuid4().hex}.db")

        # Patch SQLITE_DB_PATH in both app_config and connection
        self.patcher1 = patch("src.configs.app_config.SQLITE_DB_PATH", self.db_path)
        self.patcher2 = patch("src.db.connection.SQLITE_DB_PATH", self.db_path)
        self.patcher1.start()
        self.patcher2.start()

        # Re-initialize DB
        import src.db.connection as conn_mod
        conn_mod._db_initialized = False
        conn_mod.init_sqlite_db()

        self.client = app.test_client()
        from src.utils.auth_utils import create_jwt_token
        token = create_jwt_token()
        self.client.set_cookie("token", token)

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        for f in [self.db_path, self.db_path + "-wal", self.db_path + "-shm"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_normalize_cloud_name(self):
        self.assertEqual(normalize_cloud_name("夸克"), "夸克网盘")
        self.assertEqual(normalize_cloud_name("quark"), "夸克网盘")
        self.assertEqual(normalize_cloud_name("百度网盘"), "百度网盘")
        self.assertEqual(normalize_cloud_name("aliyun"), "阿里云盘")
        self.assertEqual(normalize_cloud_name("uc"), "UC网盘")
        self.assertEqual(normalize_cloud_name("迅雷"), "迅雷网盘")
        self.assertEqual(normalize_cloud_name("光鸭云盘"), "光鸭云盘")
        self.assertEqual(normalize_cloud_name("wukong"), "悟空网盘")
        self.assertEqual(normalize_cloud_name("和彩云"), "移动云盘")
        self.assertIsNone(normalize_cloud_name("未知网盘ABC"))

    def test_generate_template_csv(self):
        csv_text = generate_accounts_template_csv()
        self.assertTrue(csv_text.startswith("\ufeff"))
        self.assertIn("网盘平台", csv_text)
        self.assertIn("凭据内容", csv_text)
        self.assertIn("夸克网盘", csv_text)
        self.assertIn("百度网盘", csv_text)

    def test_export_accounts_csv(self):
        # Insert test accounts
        create_account({
            "cloud_name": "夸克网盘",
            "account_name": "夸克-导出测试",
            "credential": "cookie_quark_val_123",
            "priority": 0,
            "weight": 15,
        })
        create_account({
            "cloud_name": "百度网盘",
            "account_name": "百度-导出测试",
            "credential": "cookie_baidu_val_456",
            "priority": 1,
            "weight": 25,
        })

        # 1. Export all
        all_csv = export_accounts_csv()
        self.assertTrue(all_csv.startswith("\ufeff"))
        self.assertIn("夸克-导出测试", all_csv)
        self.assertIn("百度-导出测试", all_csv)

        # 2. Export filtered
        quark_csv = export_accounts_csv(cloud_name="夸克网盘")
        self.assertIn("夸克-导出测试", quark_csv)
        self.assertNotIn("百度-导出测试", quark_csv)

    def test_import_accounts_csv_chinese_headers(self):
        csv_content = """网盘平台,账号备注,凭据内容,优先级,轮询权重,是否启用
夸克网盘,夸克导入-01,cookie_quark_789,0,20,是
百度网盘,百度导入-01,cookie_baidu_321,1,30,否
"""
        res = import_accounts_from_csv(csv_content, auto_test=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["imported"], 2)
        self.assertEqual(res["failed"], 0)

        accounts = get_all_accounts()
        self.assertEqual(len(accounts), 2)
        quark_acc = [a for a in accounts if a["account_name"] == "夸克导入-01"][0]
        self.assertEqual(quark_acc["cloud_name"], "夸克网盘")
        self.assertEqual(quark_acc["credential"], "cookie_quark_789")
        self.assertEqual(quark_acc["priority"], 0)
        self.assertEqual(quark_acc["weight"], 20)
        self.assertEqual(quark_acc["is_active"], 1)

        baidu_acc = [a for a in accounts if a["account_name"] == "百度导入-01"][0]
        self.assertEqual(baidu_acc["is_active"], 0)

    def test_import_accounts_csv_english_headers_and_aliases(self):
        csv_content = """cloud,name,credential,priority,weight,active
quark,Quark-Alias,cookie_quark_alias,2,10,1
aliyun,Ali-Alias,token_aliyun_alias,0,50,true
"""
        res = import_accounts_from_csv(csv_content, auto_test=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["imported"], 2)

        accounts = get_all_accounts()
        self.assertEqual(len(accounts), 2)
        names = {a["account_name"] for a in accounts}
        self.assertIn("Quark-Alias", names)
        self.assertIn("Ali-Alias", names)

    def test_import_accounts_with_errors(self):
        csv_content = """网盘平台,账号备注,凭据内容
未知网盘,测试账号1,some_credential
夸克网盘,测试账号2,
"""
        res = import_accounts_from_csv(csv_content, auto_test=False)
        self.assertEqual(res["imported"], 0)
        self.assertEqual(res["failed"], 2)
        self.assertEqual(len(res["errors"]), 2)

    def test_api_endpoints(self):
        # 1. Download template
        resp = self.client.get("/admin/api/accounts/template-csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.content_type)
        self.assertTrue(resp.data.startswith(b"\xef\xbb\xbf"))

        # 2. Import CSV via file upload
        csv_data = "网盘平台,账号备注,凭据内容\n夸克网盘,API导入夸克,cookie_api_123\n"
        data = {
            "file": (io.BytesIO(csv_data.encode("utf-8")), "accounts.csv"),
            "auto_test": "false",
        }
        resp = self.client.post(
            "/admin/api/accounts/import-csv",
            data=data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        json_data = resp.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(json_data["imported"], 1)

        # 3. Export CSV endpoint
        resp = self.client.get("/admin/api/accounts/export-csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.content_type)
        self.assertIn("API导入夸克", resp.data.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
