# tests/test_resource_health_audit.py

import unittest
from unittest.mock import MagicMock, patch

from app import app
from src.services.link_checker import STATE_BAD, STATE_LOCKED, STATE_OK, STATE_UNCERTAIN
from src.services.resource_health_service import (
    audit_resources_batch,
    audit_single_resource,
    cleanup_dead_resources,
    get_resource_health_overview,
    scheduled_resource_health_audit_job,
)
from src.utils.auth_utils import create_jwt_token


class TestResourceHealthAudit(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.token = create_jwt_token()
        self.client.set_cookie("token", self.token)

    @patch("src.services.resource_health_service.get_resource_by_id")
    @patch("src.services.resource_health_service.check_link")
    @patch("src.services.resource_health_service.update_resource_health")
    def test_audit_single_resource_success(self, mock_update, mock_check, mock_get):
        mock_get.return_value = (
            True,
            "",
            {
                "id": 1,
                "name": "测试电影",
                "share_link": "https://pan.quark.cn/s/valid123",
                "cloud_name": "夸克网盘",
            },
        )
        mock_check.return_value = {
            "state": STATE_OK,
            "summary": "链接有效",
            "file_count": 5,
        }

        success, msg, data = audit_single_resource(1)
        self.assertTrue(success)
        self.assertEqual("检测完成", msg)
        self.assertEqual(STATE_OK, data["health_status"])
        self.assertEqual(5, data["file_count"])
        mock_update.assert_called_once_with(1, STATE_OK, "链接有效")

    @patch("src.services.resource_health_service.get_resources_for_audit")
    @patch("src.services.resource_health_service.check_links_batch")
    @patch("src.services.resource_health_service.update_resource_health")
    def test_audit_resources_batch(self, mock_update, mock_batch, mock_get_audit):
        mock_get_audit.return_value = [
            {"id": 10, "name": "资源1", "share_link": "https://pan.quark.cn/s/1", "cloud_name": "夸克网盘"},
            {"id": 20, "name": "资源2", "share_link": "https://pan.baidu.com/s/2", "cloud_name": "百度网盘"},
        ]
        mock_batch.return_value = [
            {"state": STATE_OK, "summary": "链接有效", "file_count": 1},
            {"state": STATE_BAD, "summary": "文件列表为空", "file_count": 0},
        ]

        res = audit_resources_batch(resource_ids=[10, 20])
        self.assertEqual(2, res["total"])
        self.assertEqual(1, res["ok_count"])
        self.assertEqual(1, res["bad_count"])
        self.assertEqual(2, mock_update.call_count)

    @patch("src.services.resource_health_service.get_dead_resources")
    @patch("src.services.resource_health_service.del_share")
    @patch("src.services.resource_health_service.delete_resource_by_id")
    def test_cleanup_dead_resources(self, mock_delete_id, mock_del_share, mock_get_dead):
        mock_get_dead.return_value = [
            {
                "id": 101,
                "name": "失效电影",
                "share_link": "https://pan.quark.cn/s/dead",
                "cloud_name": "夸克网盘",
                "file_id": "fid_dead_1",
                "health_message": "资源已失效或为空",
            }
        ]

        # 1. dry_run
        dry_res = cleanup_dead_resources(dry_run=True)
        self.assertEqual(1, dry_res["total_found"])
        self.assertEqual(1, dry_res["cleaned_count"])
        mock_delete_id.assert_not_called()

        # 2. actual delete
        res = cleanup_dead_resources(dry_run=False)
        self.assertEqual(1, res["total_found"])
        self.assertEqual(1, res["cleaned_count"])
        mock_del_share.assert_called_once()
        mock_delete_id.assert_called_once_with(101)

    @patch("src.services.resource_health_service.count_resources_by_health")
    def test_get_resource_health_overview(self, mock_count):
        mock_count.return_value = {
            "total": 100,
            "ok": 80,
            "bad": 10,
            "locked": 5,
            "uncertain": 2,
            "unknown": 3,
        }
        stats = get_resource_health_overview()
        self.assertEqual(100, stats["total"])
        self.assertEqual(80, stats["ok"])

    @patch("src.services.resource_health_service.audit_resources_batch")
    def test_scheduled_job(self, mock_batch):
        mock_batch.return_value = {"total": 10, "ok_count": 9, "bad_count": 1}
        res = scheduled_resource_health_audit_job()
        self.assertEqual(10, res["total"])

    # --- HTTP Routes ---

    @patch("src.services.resource_health_service.audit_single_resource")
    def test_api_check_single_resource_route(self, mock_audit):
        mock_audit.return_value = (
            True,
            "检测完成",
            {"id": 1, "health_status": STATE_OK, "health_message": "有效"},
        )
        resp = self.client.post("/admin/api/resources/1/check")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(STATE_OK, data["data"]["health_status"])

    @patch("src.services.resource_health_service.audit_resources_batch")
    def test_api_audit_resources_batch_route(self, mock_batch):
        mock_batch.return_value = {"total": 2, "ok_count": 2, "bad_count": 0}
        resp = self.client.post("/admin/api/resources/audit", json={"ids": [1, 2]})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(2, data["data"]["total"])

    @patch("src.services.resource_health_service.cleanup_dead_resources")
    def test_api_cleanup_dead_resources_route(self, mock_cleanup):
        mock_cleanup.return_value = {"total_found": 3, "cleaned_count": 3, "dry_run": False}
        resp = self.client.post("/admin/api/resources/cleanup-dead", json={"dry_run": False})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("已清理 3 条", data["message"])

    @patch("src.services.resource_health_service.get_resource_health_overview")
    def test_api_health_stats_route(self, mock_overview):
        mock_overview.return_value = {"total": 10, "ok": 8, "bad": 2}
        resp = self.client.get("/admin/api/resources/health-stats")
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(8, data["data"]["ok"])


if __name__ == "__main__":
    unittest.main()
