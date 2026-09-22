import unittest
from unittest.mock import MagicMock, patch

from app import app
from src.db.resources import (
    delete_by_share_link,
    get_resource_by_share_link,
    list_resources,
)
from src.db.temp_shares import (
    create_temp_share_record,
    get_active_temp_share,
    list_expired_temp_shares,
)
from src.services.temp_share_service import (
    cleanup_expired_temp_shares,
    resolve_view_url,
)
from src.services.storage_cleanup_service import cleanup_expired_resources
from src.utils.auth_utils import create_jwt_token


class TestTransferAndResourcePersistence(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.token = create_jwt_token()
        self.client.set_cookie("token", self.token)
        self._clean_test_db()

    def tearDown(self):
        self._clean_test_db()

    def _clean_test_db(self):
        from src.db.connection import db_cursor
        with db_cursor() as cur:
            cur.execute("DELETE FROM temp_share WHERE original_url LIKE '%test%' OR original_url LIKE '%orig_%' OR temp_share_url LIKE '%test%'")
            cur.execute("DELETE FROM resources WHERE share_link LIKE '%test%' OR share_link LIKE '%api_test%'")

    @patch("src.pan_operator._handle_netdisk_operation")
    @patch("src.services.temp_share_service.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    @patch("src.pan_operator.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    @patch("src.pan_operator.check_link", return_value={"state": "ok", "summary": "有效"})
    def test_web_transfer_mode_persists_to_resources(self, mock_chk, mock_pan_cred, mock_temp_cred, mock_op):
        """测试 Web 端转存模式下，点击查看会替换存储并固化保存到‘我的资源管理’ (resources 表)"""
        mock_op.return_value = ("fid_web_001", "流浪地球2.4K.mp4", "https://pan.quark.cn/s/new_test_123")

        orig_url = "https://pan.quark.cn/s/original_web_001"
        res = self.client.post(
            "/api/view-link",
            json={
                "title": "流浪地球2 4K原盘",
                "url": orig_url,
                "netdisk_name": "夸克网盘",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("url"), "https://pan.quark.cn/s/new_test_123")
        self.assertEqual(data.get("mode"), "temp_share")

        # 验证‘我的资源管理’数据库记录已被正确固化存储
        saved = get_resource_by_share_link("https://pan.quark.cn/s/new_test_123")
        self.assertIsNotNone(saved, "转存后的新链接应该存在于 resources 数据库表中")
        self.assertEqual(saved["name"], "流浪地球2 4K原盘")
        self.assertEqual(saved["cloud_name"], "夸克网盘")
        self.assertEqual(saved["file_id"], "fid_web_001")
        self.assertEqual(saved["is_replaced"], 1)

        # 验证通过后台 API 能够分页查询到该资源
        admin_res = self.client.get("/admin/api/resources?search=流浪地球2")
        self.assertEqual(admin_res.status_code, 200)
        admin_data = admin_res.get_json()
        self.assertTrue(admin_data["success"])
        items = admin_data["data"]["items"]
        self.assertTrue(any(i["share_link"] == "https://pan.quark.cn/s/new_test_123" for i in items))

    @patch("src.pan_operator._handle_netdisk_operation")
    @patch("src.services.temp_share_service.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    @patch("src.pan_operator.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    @patch("src.pan_operator.check_link", return_value={"state": "ok", "summary": "有效"})
    @patch("src.routes.api_v1_routes.check_link", return_value={"state": "ok", "summary": "有效"})
    def test_api_transfer_mode_persists_to_resources(self, mock_v1_chk, mock_chk, mock_pan_cred, mock_temp_cred, mock_op):
        """测试 API 模式下 (/api/v1/transfer)，转存成功后也存入‘我的资源管理’"""
        mock_op.return_value = ("fid_api_002", "三体.全24集.4K.mp4", "https://pan.quark.cn/s/api_test_456")

        orig_url = "https://pan.quark.cn/s/original_api_002"
        res = self.client.post(
            "/api/v1/transfer",
            json={
                "title": "三体 电视剧版",
                "url": orig_url,
                "netdisk_name": "夸克网盘",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["data"]["url"], "https://pan.quark.cn/s/api_test_456")

        # 验证持久化
        saved = get_resource_by_share_link("https://pan.quark.cn/s/api_test_456")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["name"], "三体 电视剧版")
        self.assertEqual(saved["is_replaced"], 1)

        # 验证 /api/v1/resources 对外 API 能够查出该资源
        api_res_list = self.client.get("/api/v1/resources?search=三体")
        self.assertEqual(api_res_list.status_code, 200)
        self.assertTrue(api_res_list.get_json()["success"])
        items = api_res_list.get_json()["data"]["items"]
        self.assertTrue(any(i["share_link"] == "https://pan.quark.cn/s/api_test_456" for i in items))

    @patch("src.pan_operator._handle_netdisk_operation")
    @patch("src.services.temp_share_service.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    @patch("src.pan_operator.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    @patch("src.pan_operator.check_link", return_value={"state": "ok", "summary": "有效"})
    def test_scheduled_cleanup_removes_from_resources_and_temp_share(self, mock_chk, mock_pan_cred, mock_temp_cred, mock_op):
        """测试定时任务清理过期分享时，一并删除‘我的资源管理’中的记录"""
        mock_op.return_value = ("fid_clean_003", "测试待清理资源.mp4", "https://pan.quark.cn/s/cleanup_test_789")

        # 1. 模拟转存生成记录
        resolve_view_url(
            title="测试待清理资源",
            original_url="https://pan.quark.cn/s/original_clean_003",
            netdisk_name="夸克网盘",
        )

        # 确认已存在于 resources
        saved_before = get_resource_by_share_link("https://pan.quark.cn/s/cleanup_test_789")
        self.assertIsNotNone(saved_before)

        # 2. 模拟物理删除成功
        mock_op.return_value = True

        # 3. 将 temp_share 的过期时间提前以模拟过期
        from src.db.connection import db_cursor
        with db_cursor() as cur:
            cur.execute("UPDATE temp_share SET expires_at = datetime('now', '-1 hour') WHERE temp_share_url = ?",
                        ("https://pan.quark.cn/s/cleanup_test_789",))

        # 4. 执行定时清理
        cleaned = cleanup_expired_temp_shares()
        self.assertGreaterEqual(cleaned, 1)

        # 5. 验证‘我的资源管理’ (resources 表) 记录已一并被删除
        saved_after = get_resource_by_share_link("https://pan.quark.cn/s/cleanup_test_789")
        self.assertIsNone(saved_after, "定时任务清理后，resources 表中对应的记录应被同步删除")

    @patch("src.pan_operator._handle_netdisk_operation")
    @patch("src.services.temp_share_service.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    @patch("src.pan_operator.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    @patch("src.pan_operator.check_link", return_value={"state": "ok", "summary": "有效"})
    def test_repeated_transfer_updates_without_conflict(self, mock_chk, mock_pan_cred, mock_temp_cred, mock_op):
        """测试多次重复转存相同链接时，能够安全复用并更新记录，不会发生 UNIQUE 约束崩溃"""
        mock_op.return_value = ("fid_repeat_004", "重复转存电影.mp4", "https://pan.quark.cn/s/new_test_123")

        # 首次转存
        res1 = resolve_view_url("重复转存电影 v1", "https://pan.quark.cn/s/orig_repeat_1", "夸克网盘")
        self.assertEqual(res1["url"], "https://pan.quark.cn/s/new_test_123")

        saved1 = get_resource_by_share_link("https://pan.quark.cn/s/new_test_123")
        self.assertIsNotNone(saved1)

        # 再次转存
        mock_op.return_value = ("fid_repeat_004", "重复转存电影_更新版.mp4", "https://pan.quark.cn/s/new_test_123")
        res2 = resolve_view_url("重复转存电影 v2", "https://pan.quark.cn/s/orig_repeat_2", "夸克网盘")
        self.assertEqual(res2["url"], "https://pan.quark.cn/s/new_test_123")

        saved2 = get_resource_by_share_link("https://pan.quark.cn/s/new_test_123")
        self.assertIsNotNone(saved2)
        self.assertEqual(saved2["id"], saved1["id"])

    @patch("src.pan_operator._handle_netdisk_operation", return_value=True)
    @patch("src.pan_operator.get_and_validate_credential", return_value="mock_cookie_val_long_enough_123456789012345678901234567890")
    def test_manual_delete_resource_syncs_temp_share(self, mock_cred, mock_op):
        """测试后台手工删除‘我的资源管理’中的资源时，网盘物理删除及 temp_share 状态同步标记为 deleted"""
        from src.services.resource_service import add_resource_and_share, delete_resource_and_share
        from src.db.temp_shares import create_temp_share_record, get_active_temp_share

        # 1. 插入资源到 resources
        ok, msg, res_id = add_resource_and_share({
            "name": "待手工删除资源",
            "share_link": "https://pan.quark.cn/s/cleanup_test_789",
            "cloud_name": "夸克网盘",
        })
        self.assertTrue(ok)

        # 2. 插入 temp_share 记录
        create_temp_share_record(
            original_url="https://pan.quark.cn/s/orig_cleanup",
            title="待手工删除资源",
            cloud_name="夸克网盘",
            temp_share_url="https://pan.quark.cn/s/cleanup_test_789",
            file_id="fid_manual_del",
            expires_in_hours=6,
        )
        self.assertIsNotNone(get_active_temp_share("https://pan.quark.cn/s/orig_cleanup", "夸克网盘"))

        # 3. 删除资源
        del_ok, del_msg = delete_resource_and_share(res_id)
        self.assertTrue(del_ok)

        # 4. 验证 resources 已被删除
        self.assertIsNone(get_resource_by_share_link("https://pan.quark.cn/s/cleanup_test_789"))

        # 5. 验证 temp_share 已被标记为已删除 (不再为 active)
        self.assertIsNone(get_active_temp_share("https://pan.quark.cn/s/orig_cleanup", "夸克网盘"))


if __name__ == "__main__":
    unittest.main()
