import unittest
from unittest.mock import patch

from app import app
from src.services.security_service import check_request_security, IPConcurrencyGuard, _request_records, _active_searches
from src.services.system_config_service import save_security_config, get_security_config, add_ip_to_blacklist, remove_ip_from_blacklist


class TestSecurityService(unittest.TestCase):
    def setUp(self):
        _request_records.clear()
        _active_searches.clear()
        app.config["ENABLE_SECURITY_RATE_LIMIT_IN_TESTS"] = True
        self.client = app.test_client()

    def tearDown(self):
        app.config["ENABLE_SECURITY_RATE_LIMIT_IN_TESTS"] = False


    def test_ip_blacklist(self):
        # 添加测试 IP 到黑名单
        add_ip_to_blacklist("182.149.235.13")
        cfg = get_security_config()
        self.assertIn("182.149.235.13", cfg["ip_blacklist"])

        # 模拟 182.149.235.13 请求
        with app.test_request_context('/api/search_stream?keyword=测试资源', headers={'X-Forwarded-For': '182.149.235.13'}):
            allowed, msg, status_code = check_request_security()
            self.assertFalse(allowed)
            self.assertEqual(status_code, 403)
            self.assertIn("已被系统封禁", msg)

        # 解封 IP
        remove_ip_from_blacklist("182.149.235.13")
        with app.test_request_context('/api/search_stream?keyword=测试资源', headers={'X-Forwarded-For': '182.149.235.13'}):
            allowed, msg, status_code = check_request_security()
            self.assertTrue(allowed)

    def test_min_keyword_length(self):
        save_security_config({"min_keyword_length": 2, "rate_limit_per_minute": 10, "max_concurrent_searches": 2, "ip_blacklist": []})
        
        # 1. 尝试搜索单字 "零"
        res = self.client.get('/api/search_stream?keyword=零', headers={'X-Forwarded-For': '1.2.3.4'})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("搜索关键词过短", data["error"])

        # 2. 尝试搜索合格词 "黑客帝国"
        res = self.client.get('/api/search_stream?keyword=黑客帝国', headers={'X-Forwarded-For': '1.2.3.4'})
        self.assertNotEqual(res.status_code, 400)

    def test_concurrency_guard(self):
        save_security_config({"min_keyword_length": 2, "rate_limit_per_minute": 10, "max_concurrent_searches": 1, "ip_blacklist": []})
        
        ip = "10.0.0.1"
        with app.test_request_context('/api/search_stream?keyword=测试资源', headers={'X-Forwarded-For': ip}):
            # 开启第 1 个并发搜索
            with IPConcurrencyGuard(ip):
                # 尝试开启第 2 个并发搜索
                allowed, msg, status_code = check_request_security()
                self.assertFalse(allowed)
                self.assertEqual(status_code, 429)
                self.assertIn("请勿并发提交", msg)

            # 离开第 1 个并发搜索后，恢复正常
            allowed, msg, status_code = check_request_security()
            self.assertTrue(allowed)


if __name__ == "__main__":
    unittest.main()
