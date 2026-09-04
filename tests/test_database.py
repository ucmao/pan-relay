import unittest

from app import app
from src.db.api_configs import (
    delete_config,
    get_config_by_id,
    get_config_status,
    insert_config,
    update_status,
)
from src.db.credentials import (
    delete_cookie,
    get_cookie_by_cloud_name,
    save_cookie,
)
from src.db.resources import (
    delete_resource_by_id,
    get_resource_by_id,
    insert_resource_simple,
    list_resources,
    random_read_record,
    search_resources_advanced,
    search_resources_by_keyword,
    update_resource_basic_info,
)
from src.db.temp_shares import (
    create_temp_share_record,
    get_active_temp_share,
    touch_temp_share,
    mark_temp_share_deleted,
)
from src.services.dashboard_service import get_dashboard_summary


class NativeSqlDatabaseTest(unittest.TestCase):
    def test_resources_db_crud_and_purified_sql(self):
        # 1. 插入资源
        success, msg, res_id = insert_resource_simple({
            "name": "单元测试资源_纯净化",
            "share_link": "https://pan.quark.cn/s/phase4test",
            "cloud_name": "夸克网盘",
            "type": "电影",
            "remarks": "测试备注",
        })
        self.assertTrue(success)
        self.assertIsNotNone(res_id)

        try:
            # 2. 查询单个资源
            success, msg, item = get_resource_by_id(res_id)
            self.assertTrue(success)
            self.assertEqual("单元测试资源_纯净化", item["name"])

            # 3. 列表分页查询
            success, msg, data = list_resources(page=1, page_size=10, search="纯净化")
            self.assertTrue(success)
            self.assertGreaterEqual(data["total_count"], 1)

            # 4. 更新基础信息
            success, msg = update_resource_basic_info(res_id, {
                "name": "单元测试资源_纯净化_更新",
                "share_link": "https://pan.quark.cn/s/phase4test_updated",
                "cloud_name": "夸克网盘",
                "type": "电视剧",
                "remarks": "更新备注",
            })
            self.assertTrue(success)

            # 5. 关键词搜索
            results = search_resources_by_keyword("纯净化_更新")
            self.assertGreaterEqual(len(results), 1)

            # 6. 高级搜索
            success, msg, adv_results = search_resources_advanced(
                name="纯净化", sort="random", limit=5
            )
            self.assertTrue(success)
            self.assertGreaterEqual(len(adv_results), 1)

            # 7. 随机读取单条记录
            random_row = random_read_record()
            self.assertIsNotNone(random_row)

        finally:
            # 8. 删除资源
            success, msg, deleted_item = delete_resource_by_id(res_id)
            self.assertTrue(success)
            self.assertIsNotNone(deleted_item)

    def test_credentials_db_purified_sql(self):
        cloud_name = "测试网盘_SQL验证"
        test_cookie = "token_xyz_123"

        # 1. 新增
        success, msg = save_cookie(cloud_name, test_cookie)
        self.assertTrue(success)

        try:
            # 2. 查询
            fetched = get_cookie_by_cloud_name(cloud_name)
            self.assertEqual(test_cookie, fetched)

            # 3. 更新现有
            updated_cookie = "token_xyz_456"
            success, msg = save_cookie(cloud_name, updated_cookie)
            self.assertTrue(success)
            self.assertEqual(updated_cookie, get_cookie_by_cloud_name(cloud_name))

        finally:
            # 4. 删除
            success, msg = delete_cookie(cloud_name)
            self.assertTrue(success)
            self.assertIsNone(get_cookie_by_cloud_name(cloud_name))

    def test_api_configs_db_purified_sql(self):
        # 1. 插入新配置
        success, msg, new_id = insert_config({
            "name": "测试原生SQL_API",
            "url": "https://api.test/sql_purified",
            "method": "GET",
            "request": "{}",
            "response": "[]",
            "status": True,
            "is_enabled": True,
        })
        self.assertTrue(success)
        self.assertIsNotNone(new_id)

        try:
            # 2. 查询单条配置
            cfg = get_config_by_id(new_id)
            self.assertIsNotNone(cfg)
            self.assertEqual("测试原生SQL_API", cfg["name"])

            # 3. 更新状态与响应时间
            updated = update_status(new_id, True, 88)
            self.assertTrue(updated)
            status_info = get_config_status(new_id)
            self.assertTrue(status_info["status"])

        finally:
            # 4. 删除配置
            success, msg = delete_config(new_id)
            self.assertTrue(success)
            self.assertIsNone(get_config_by_id(new_id))

    def test_temp_shares_db_purified_sql(self):
        orig_url = "https://pan.quark.cn/s/orig_purified_test"
        title = "测试动态分享纯净化"
        cloud_name = "夸克网盘"
        temp_url = "https://pan.quark.cn/s/temp_purified_test"
        file_id = "test_fid_1"

        # 1. 创建未过期的动态分享
        rec_id = create_temp_share_record(
            original_url=orig_url,
            title=title,
            cloud_name=cloud_name,
            temp_share_url=temp_url,
            file_id=file_id,
            expires_in_hours=6,
        )
        self.assertIsNotNone(rec_id)

        try:
            # 2. 查询有效分享
            active = get_active_temp_share(orig_url, cloud_name)
            self.assertIsNotNone(active)
            self.assertEqual(temp_url, active["temp_share_url"])

            # 3. 刷新访问时间
            touched = touch_temp_share(rec_id)
            self.assertTrue(touched)

        finally:
            # 4. 标记删除
            deleted = mark_temp_share_deleted(rec_id)
            self.assertTrue(deleted)
            self.assertIsNone(get_active_temp_share(orig_url, cloud_name))

    def test_dashboard_summary_structure(self):
        summary = get_dashboard_summary()
        self.assertIn("resources", summary)
        self.assertIn("sources", summary)
        self.assertIn("credentials", summary)
        self.assertIn("system", summary)
        self.assertIn("total_count", summary["resources"])
        self.assertIn("api", summary["sources"])
        self.assertIn("plugins", summary["sources"])
        self.assertIn("telegram", summary["sources"])
        self.assertIn("overall_health_rate", summary["sources"])


if __name__ == "__main__":
    unittest.main()
