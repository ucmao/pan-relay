import json
import unittest

from app import app
from src.db.connection import get_db_connection
from src.db.resource_requests import (
    create_resource_request,
    get_resource_requests,
    get_resource_request_counts,
    update_resource_request_status,
    delete_resource_request,
)
from src.utils.auth_utils import create_jwt_token


class ResourceRequestsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.token = create_jwt_token("admin")
        self.client.set_cookie("token", self.token)
        from src.routes.search_routes import _request_resource_rate_limit
        _request_resource_rate_limit.clear()

        # 清理测试数据
        conn = get_db_connection()
        if conn:
            conn.execute("DELETE FROM resource_requests WHERE resource_name LIKE '测试求片_%'")
            conn.commit()
            conn.close()

    def tearDown(self):
        conn = get_db_connection()
        if conn:
            conn.execute("DELETE FROM resource_requests WHERE resource_name LIKE '测试求片_%'")
            conn.commit()
            conn.close()

    def test_db_crud_operations(self):
        # 1. 插入求片需求
        ok, msg, req_id = create_resource_request(
            resource_name="测试求片_凡人修仙传4K",
            contact="test@example.com",
            note="希望有高码率杜比视界版本",
            client_ip="127.0.0.1",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(req_id)

        # 2. 查询列表与计数
        items, total = get_resource_requests(keyword="测试求片_凡人修仙传")
        self.assertGreaterEqual(total, 1)
        self.assertEqual("测试求片_凡人修仙传4K", items[0]["resource_name"])
        self.assertEqual("pending", items[0]["status"])

        counts = get_resource_request_counts()
        self.assertGreaterEqual(counts["total"], 1)
        self.assertGreaterEqual(counts["pending"], 1)

        # 3. 更新状态
        updated = update_resource_request_status(req_id, "completed")
        self.assertTrue(updated)

        items_after, _ = get_resource_requests(status="completed", keyword="测试求片_凡人修仙传")
        self.assertEqual(1, len(items_after))
        self.assertEqual("completed", items_after[0]["status"])

        # 4. 删除求片
        deleted = delete_resource_request(req_id)
        self.assertTrue(deleted)

    def test_frontend_submit_api(self):
        # 空资源名称应返回 400
        resp = self.client.post(
            "/api/request_resource",
            data=json.dumps({"resource_name": ""}),
            content_type="application/json",
        )
        self.assertEqual(400, resp.status_code)
        self.assertFalse(resp.get_json()["success"])

        # 正常提交
        resp = self.client.post(
            "/api/request_resource",
            data=json.dumps({
                "resource_name": "测试求片_黑神话全集",
                "contact": "qq123456",
                "note": "最好是百度网盘",
            }),
            content_type="application/json",
        )
        self.assertEqual(200, resp.status_code)
        json_data = resp.get_json()
        self.assertTrue(json_data["success"])
        self.assertIn("request_id", json_data)

        # 立即再次提交触发 5 秒防刷限流 (429)
        resp_fast = self.client.post(
            "/api/request_resource",
            data=json.dumps({"resource_name": "测试求片_连击提交"}),
            content_type="application/json",
        )
        self.assertEqual(429, resp_fast.status_code)
        self.assertFalse(resp_fast.get_json()["success"])

    def test_admin_api_endpoints(self):
        # 先插入一条用于测试
        ok, _, req_id = create_resource_request(
            resource_name="测试求片_后台管理测试",
            contact="admin_test",
        )
        self.assertTrue(ok)

        headers = {"Authorization": f"Bearer {self.token}"}

        # 1. 访问后台管理页面
        page_resp = self.client.get("/admin/requests", headers=headers)
        self.assertEqual(200, page_resp.status_code)

        # 2. 请求后台列表接口
        list_resp = self.client.get("/admin/api/requests?search=后台管理测试", headers=headers)
        self.assertEqual(200, list_resp.status_code)
        list_data = list_resp.get_json()["data"]
        self.assertGreaterEqual(list_data["total"], 1)

        # 3. 修改状态接口
        status_resp = self.client.post(
            f"/admin/api/requests/{req_id}/status",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=headers,
        )
        self.assertEqual(200, status_resp.status_code)
        self.assertTrue(status_resp.get_json()["success"])

        # 4. 删除接口
        del_resp = self.client.delete(f"/admin/api/requests/{req_id}", headers=headers)
        self.assertEqual(200, del_resp.status_code)
        self.assertTrue(del_resp.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
