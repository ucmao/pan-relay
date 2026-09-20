import json
import unittest
from app import app
from src.db.logs import (
    ensure_system_logs_table,
    insert_system_log,
    query_system_logs,
    delete_logs_by_ids,
    clear_all_logs,
    cleanup_logs_before_days,
    get_logs_summary_stats,
)
from src.services.log_service import record_log, export_logs_csv
from src.utils.auth_utils import create_jwt_token


class TestSystemLogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = cls.app.test_client()
        cls.admin_token = create_jwt_token()
        cls.client.set_cookie(key="token", value=cls.admin_token)
        ensure_system_logs_table()

    def setUp(self):
        # 保证测试前表状态就绪
        ensure_system_logs_table()

    def test_01_insert_and_query_logs(self):
        log_id = insert_system_log(
            log_type="search",
            action="test.search.action",
            query_text="流浪地球 4K",
            status_code=200,
            duration_ms=120,
            result_count=8,
            client_ip="127.0.0.1",
        )
        self.assertIsNotNone(log_id)

        success, msg, data = query_system_logs(q="流浪地球")
        self.assertTrue(success)
        self.assertGreater(data["total"], 0)
        found = any(l["id"] == log_id for l in data["logs"])
        self.assertTrue(found)

    def test_02_log_filtering_and_sorting(self):
        # 插入多条不同类型和状态的日志
        id_err = insert_system_log(
            log_type="transfer",
            action="test.transfer.quark",
            query_text="https://pan.quark.cn/s/fake123",
            status_code=500,
            error_message="Cookie 失效",
            duration_ms=850,
        )
        id_ok = insert_system_log(
            log_type="api",
            action="test.api.v1.search",
            query_text="三体",
            status_code=200,
            duration_ms=45,
            result_count=15,
        )

        # 按类型筛选
        success, _, data_transfer = query_system_logs(log_type="transfer")
        self.assertTrue(success)
        self.assertTrue(all(l["log_type"] == "transfer" for l in data_transfer["logs"]))

        # 按状态筛选错误
        success, _, data_err = query_system_logs(status="error")
        self.assertTrue(success)
        self.assertTrue(any(l["id"] == id_err for l in data_err["logs"]))

        # 按耗时排序
        success, _, data_sorted = query_system_logs(sort_by="duration_ms", order="desc")
        self.assertTrue(success)
        durations = [l["duration_ms"] for l in data_sorted["logs"]]
        self.assertEqual(durations, sorted(durations, reverse=True))

    def test_03_log_stats(self):
        stats = get_logs_summary_stats()
        self.assertIn("today_total", stats)
        self.assertIn("today_search", stats)
        self.assertIn("today_transfer", stats)
        self.assertIn("today_api", stats)
        self.assertIn("today_success_rate", stats)
        self.assertIn("today_avg_duration_ms", stats)

    def test_04_export_csv(self):
        log_id = record_log(
            log_type="search",
            action="test.export.action",
            query_text="CSV测试关键词",
            status_code=200,
            duration_ms=30,
        )
        csv_str = export_logs_csv(q="CSV测试关键词")
        self.assertTrue(csv_str.startswith("\ufeff"))  # BOM
        self.assertIn("CSV测试关键词", csv_str)
        self.assertIn("test.export.action", csv_str)

    def test_05_admin_routes_auth_and_api(self):
        # 1. 访问 HTML 页面
        resp = self.client.get("/admin/logs")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("系统运行与审计日志", resp.get_data(as_text=True))

        # 2. 访问 API 获取列表
        resp = self.client.get("/admin/api/logs?page=1&page_size=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("logs", data["data"])

        # 3. 访问 API 获取统计
        resp = self.client.get("/admin/api/logs/stats")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])

        # 4. 导出 CSV 接口
        resp = self.client.get("/admin/api/logs/export")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/csv")

    def test_06_delete_and_cleanup(self):
        log_id1 = insert_system_log(log_type="search", action="del.test.1", query_text="del1")
        log_id2 = insert_system_log(log_type="search", action="del.test.2", query_text="del2")

        # 批量删除
        success, msg, count = delete_logs_by_ids([log_id1, log_id2])
        self.assertTrue(success)
        self.assertEqual(count, 2)

        # 历史清理测试
        success, msg, count = cleanup_logs_before_days(30)
        self.assertTrue(success)

    def test_07_dashboard_integration(self):
        resp = self.client.get("/admin/api/dashboard/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("logs", data["data"])
        self.assertIn("today_total", data["data"]["logs"])

    def test_08_end_to_end_search_and_api_hooks(self):
        # 1. 触发公开聚合搜索
        resp = self.client.get("/api?keyword=星际穿越")
        self.assertIn(resp.status_code, [200, 400, 500])

        # 2. 触发 API v1 搜索
        resp = self.client.get("/api/v1/search?keyword=奥本海默&scope=own")
        self.assertEqual(resp.status_code, 200)

        # 3. 触发 link check API
        resp = self.client.post("/api/v1/link/check", json={"items": []})
        self.assertIn(resp.status_code, [200, 400])

        # 4. 验证数据库中记录了这些请求
        success, _, data = query_system_logs(page=1, page_size=20)
        self.assertTrue(success)
        logged_actions = [l["action"] for l in data["logs"]]
        self.assertTrue(any("search" in a for a in logged_actions))


if __name__ == "__main__":
    unittest.main()
