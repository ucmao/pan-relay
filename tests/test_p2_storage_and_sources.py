import json
import unittest
from unittest.mock import MagicMock, patch

from app import app
from src.configs.preset_loader import load_preset_api_configs
from src.db.resources import (
    count_expired_resources,
    insert_resource,
    list_expired_resources,
)
from src.services.storage_cleanup_service import (
    cleanup_all_storage,
    cleanup_expired_resources,
    get_storage_stats,
)
from src.services.system_config_service import (
    get_ad_filter_config,
    get_storage_cleanup_config,
    save_ad_filter_config,
    save_storage_cleanup_config,
)
from src.utils.auth_utils import create_jwt_token


from src.db.system_configs import delete_config_value


class TestP2StorageAndSources(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.token = create_jwt_token()
        self.client.set_cookie("token", self.token)

    def tearDown(self):
        delete_config_value("ad_filter_config")
        delete_config_value("custom_ad_injection_config")
        delete_config_value("storage_cleanup_config")

    def test_storage_cleanup_config_lifecycle(self):
        """测试存储自动清理配置的保存与读取"""
        config = {
            "enabled": True,
            "retention_unit": "days",
            "retention_value": 20,
            "auto_cleanup_interval_hours": 6,
            "clean_temp_shares": True,
            "clean_old_resources": True,
            "limit_per_run": 50,
        }
        self.assertTrue(save_storage_cleanup_config(config))
        current = get_storage_cleanup_config()
        self.assertTrue(current["enabled"])
        self.assertEqual(current["retention_unit"], "days")
        self.assertEqual(current["retention_value"], 20)
        self.assertEqual(current["retention_minutes"], 20 * 1440)
        self.assertEqual(current["auto_cleanup_interval_hours"], 6)
        self.assertEqual(current["limit_per_run"], 50)

        # 测试分钟单位及最小30分钟底线保护
        minute_config = {
            "retention_unit": "minutes",
            "retention_value": 45,
            "cleanup_interval_unit": "minutes",
            "cleanup_interval_value": 30,
        }
        self.assertTrue(save_storage_cleanup_config(minute_config))
        curr_min = get_storage_cleanup_config()
        self.assertEqual(curr_min["retention_unit"], "minutes")
        self.assertEqual(curr_min["retention_value"], 45)
        self.assertEqual(curr_min["retention_minutes"], 45)
        self.assertEqual(curr_min["cleanup_interval_unit"], "minutes")
        self.assertEqual(curr_min["cleanup_interval_value"], 30)
        self.assertEqual(curr_min["auto_cleanup_interval_minutes"], 30)

        # 尝试设置小于30分钟/小于15分钟扫描周期，自动钳位
        clamp_config = {
            "retention_unit": "minutes",
            "retention_value": 5,
            "cleanup_interval_unit": "minutes",
            "cleanup_interval_value": 5,
        }
        self.assertTrue(save_storage_cleanup_config(clamp_config))
        curr_clamped = get_storage_cleanup_config()
        self.assertEqual(curr_clamped["retention_unit"], "minutes")
        self.assertEqual(curr_clamped["retention_value"], 30)
        self.assertEqual(curr_clamped["retention_minutes"], 30)
        self.assertEqual(curr_clamped["cleanup_interval_unit"], "minutes")
        self.assertEqual(curr_clamped["cleanup_interval_value"], 15)

    @patch("src.services.storage_cleanup_service.del_share", return_value=True)
    @patch("src.services.storage_cleanup_service.list_expired_resources")
    @patch("src.services.storage_cleanup_service.delete_resource_by_id")
    def test_cleanup_expired_resources(self, mock_delete_id, mock_list_expired, mock_del_share):
        """测试过期转存资源清理与网盘物理删除"""
        mock_list_expired.return_value = [
            {
                "id": 101,
                "file_id": "fid_old_1",
                "name": "旧电影1.mp4",
                "share_link": "https://pan.quark.cn/s/old1",
                "cloud_name": "夸克网盘",
            },
            {
                "id": 102,
                "file_id": "fid_old_2",
                "name": "旧电影2.mp4",
                "share_link": "https://pan.quark.cn/s/old2",
                "cloud_name": "夸克网盘",
            },
        ]
        mock_delete_id.return_value = (True, "删除成功", {})

        cleaned_count = cleanup_expired_resources(retention_days=15, limit=100)
        self.assertEqual(cleaned_count, 2)
        self.assertEqual(mock_del_share.call_count, 2)
        self.assertEqual(mock_delete_id.call_count, 2)

    @patch("src.services.storage_cleanup_service.cleanup_expired_temp_shares", return_value=3)
    @patch("src.services.storage_cleanup_service.cleanup_expired_resources", return_value=5)
    def test_cleanup_all_storage(self, mock_res_cleanup, mock_temp_cleanup):
        """测试统一存储清理主任务"""
        save_storage_cleanup_config(
            {
                "enabled": True,
                "clean_temp_shares": True,
                "clean_old_resources": True,
                "retention_days": 15,
                "limit_per_run": 100,
            }
        )

        res = cleanup_all_storage()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["temp_shares_cleaned"], 3)
        self.assertEqual(res["resources_cleaned"], 5)

    def test_get_storage_stats(self):
        """测试获取存储统计概览"""
        stats = get_storage_stats()
        self.assertIn("config", stats)
        self.assertIn("expired_resources_count", stats)
        self.assertIsInstance(stats["expired_resources_count"], int)

    def test_storage_cleanup_api_endpoints(self):
        """测试存储清理与配置管理 HTTP API 接口"""
        # 1. GET config
        res = self.client.get("/admin/api/storage-cleanup-config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("data", data)

        # 2. PUT config
        put_payload = {
            "enabled": True,
            "retention_days": 10,
            "auto_cleanup_interval_hours": 8,
            "clean_temp_shares": True,
            "clean_old_resources": True,
            "limit_per_run": 30,
        }
        res_put = self.client.put(
            "/admin/api/storage-cleanup-config",
            json=put_payload,
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertTrue(res_put.get_json()["success"])

        # 3. POST run immediately
        res_run = self.client.post("/admin/api/storage-cleanup/run")
        self.assertEqual(res_run.status_code, 200)
        self.assertTrue(res_run.get_json()["success"])

    def test_ad_filter_api_endpoints(self):
        """测试广告过滤配置 HTTP API 接口"""
        res_get = self.client.get("/admin/api/ad-filter-config")
        self.assertEqual(res_get.status_code, 200)
        self.assertTrue(res_get.get_json()["success"])

        res_put = self.client.put(
            "/admin/api/ad-filter-config",
            json={"enabled": True, "keywords": ["关注公众号防失联", "扫码进一手资源群"]},
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertTrue(res_put.get_json()["success"])
        self.assertIn("关注公众号防失联", res_put.get_json()["config"]["keywords"])

    def test_custom_ad_config_api_endpoints(self):
        """测试自定义引流广告植入配置 HTTP API 接口"""
        res_get = self.client.get("/admin/api/custom-ad-config")
        self.assertEqual(res_get.status_code, 200)
        self.assertTrue(res_get.get_json()["success"])

        res_put = self.client.put(
            "/admin/api/custom-ad-config",
            json={
                "enabled": True,
                "ad_share_url": "https://pan.quark.cn/s/c098a72b5f6e",
            },
        )
        self.assertEqual(res_put.status_code, 200)
        data = res_put.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["config"]["enabled"])
        self.assertEqual(data["config"]["ad_share_url"], "https://pan.quark.cn/s/c098a72b5f6e")

    def test_preset_api_configs_expanded(self):
        """测试预置 API 搜索源扩展"""
        presets = load_preset_api_configs()
        self.assertGreaterEqual(len(presets), 8)
        names = [item["name"] for item in presets]
        self.assertIn("狗狗盘搜 API", names)
        self.assertIn("量子影视资源 API", names)


if __name__ == "__main__":
    unittest.main()
