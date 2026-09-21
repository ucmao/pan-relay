import json
import unittest
from app import app
from src.db.logs import (
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

    def setUp(self):
        pass

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
        html = resp.get_data(as_text=True)
        self.assertIn("搜索运营视角", html)
        self.assertIn("系统运维视角", html)

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
        self.assertIn("search_analytics", data["data"])
        self.assertIn("top_keywords", data["data"]["search_analytics"])
        self.assertIn("top_zero_keywords", data["data"]["search_analytics"])

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

    def test_09_search_analytics_and_search_logs(self):
        # 1. 插入 Web 搜索与 API 搜索记录 (包含命中和零结果)
        insert_system_log(
            log_type="search",
            action="search.web",
            query_text="阿凡达2",
            status_code=200,
            duration_ms=350,
            result_count=12,
            client_ip="1.2.3.4",
        )
        insert_system_log(
            log_type="search",
            action="search.api.v1.all",
            query_text="生僻冷门资料 [cloud=all]",
            status_code=200,
            duration_ms=450,
            result_count=0,
            client_ip="5.6.7.8",
        )

        # 2. 测试 /admin/api/search-logs API
        resp = self.client.get("/admin/api/search-logs?page=1&page_size=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("logs", data["data"])
        logs = data["data"]["logs"]
        self.assertTrue(len(logs) > 0)
        self.assertIn("channel", logs[0])
        self.assertIn("keyword", logs[0])
        self.assertIn("result_count", logs[0])

        # 3. 测试渠道过滤 (channel=web)
        resp_web = self.client.get("/admin/api/search-logs?channel=web")
        self.assertEqual(resp_web.status_code, 200)
        web_logs = resp_web.get_json()["data"]["logs"]
        self.assertTrue(all(l["channel"] == "web" for l in web_logs))

        # 4. 测试渠道过滤 (channel=api)
        resp_api = self.client.get("/admin/api/search-logs?channel=api")
        self.assertEqual(resp_api.status_code, 200)
        api_logs = resp_api.get_json()["data"]["logs"]
        self.assertTrue(all(l["channel"] == "api" for l in api_logs))

        # 5. 测试零结果过滤 (result_filter=zero_results)
        resp_zero = self.client.get("/admin/api/search-logs?result_filter=zero_results")
        self.assertEqual(resp_zero.status_code, 200)
        zero_logs = resp_zero.get_json()["data"]["logs"]
        self.assertTrue(all(l["result_count"] == 0 for l in zero_logs))

        # 5. 测试 /admin/api/search-analytics API
        resp_analytics = self.client.get("/admin/api/search-analytics")
        self.assertEqual(resp_analytics.status_code, 200)
        analytics_data = resp_analytics.get_json()["data"]
        self.assertIn("today_total_searches", analytics_data)
        self.assertIn("today_web_searches", analytics_data)
        self.assertIn("today_api_searches", analytics_data)
        self.assertIn("top_keywords", analytics_data)
        self.assertIn("top_zero_keywords", analytics_data)


if __name__ == "__main__":
    unittest.main()
