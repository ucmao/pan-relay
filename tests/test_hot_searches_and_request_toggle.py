import unittest
import json
from app import app
from src.services.system_config_service import (
    is_resource_request_enabled,
    save_resource_request_config,
    is_hot_searches_enabled,
    get_hot_search_words,
    save_hot_searches_config,
    DEFAULT_HOT_SEARCH_WORDS,
)
from src.utils.auth_utils import create_jwt_token

class HotSearchesAndResourceRequestTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.token = create_jwt_token("admin")
        self.client.set_cookie("token", self.token)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        from src.services.system_config_service import save_active_theme
        save_active_theme("default")

    def tearDown(self):
        # Restore default settings
        save_resource_request_config(True)
        save_hot_searches_config(True, DEFAULT_HOT_SEARCH_WORDS)
        from src.services.system_config_service import save_active_theme
        save_active_theme("default")

    def test_system_config_service_defaults(self):
        # By default, both should be enabled and default words match
        self.assertTrue(is_resource_request_enabled())
        self.assertTrue(is_hot_searches_enabled())
        words = get_hot_search_words()
        self.assertIn("兰香如故", words)
        self.assertIn("凡人修仙传", words)
        self.assertEqual(len(words), 9)

    def test_save_and_toggle_resource_request(self):
        save_resource_request_config(False)
        self.assertFalse(is_resource_request_enabled())

        save_resource_request_config(True)
        self.assertTrue(is_resource_request_enabled())

    def test_save_and_toggle_hot_searches(self):
        custom_words = ["测试热词A", "测试热词B", "测试热词C"]
        save_hot_searches_config(False, custom_words)
        self.assertFalse(is_hot_searches_enabled())
        self.assertEqual(get_hot_search_words(), custom_words)

        save_hot_searches_config(True, DEFAULT_HOT_SEARCH_WORDS)
        self.assertTrue(is_hot_searches_enabled())
        self.assertEqual(get_hot_search_words(), DEFAULT_HOT_SEARCH_WORDS)

    def test_api_resource_request_toggle(self):
        # POST /api/frontend/resource-request/save
        resp = self.client.post(
            "/api/frontend/resource-request/save",
            data=json.dumps({"enabled": False}),
            content_type="application/json",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertFalse(is_resource_request_enabled())

        # When disabled, submitting request should be 403
        submit_resp = self.client.post(
            "/api/request_resource",
            data=json.dumps({"resource_name": "测试电影"}),
            content_type="application/json",
        )
        self.assertEqual(submit_resp.status_code, 403)

        # Re-enable
        resp = self.client.post(
            "/api/frontend/resource-request/save",
            data=json.dumps({"enabled": True}),
            content_type="application/json",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(is_resource_request_enabled())

    def test_api_hot_searches_save(self):
        # POST /api/frontend/hot-searches/save
        resp = self.client.post(
            "/api/frontend/hot-searches/save",
            data=json.dumps({
                "enabled": True,
                "words": "狂飙\n漫长的季节\n三体"
            }),
            content_type="application/json",
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("words"), ["狂飙", "漫长的季节", "三体"])
        self.assertEqual(get_hot_search_words(), ["狂飙", "漫长的季节", "三体"])

    def test_template_1_rendering(self):
        # Save custom words
        save_hot_searches_config(True, ["热词1", "热词2"])
        save_resource_request_config(True)

        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # Check progress bar & hot words bar
        self.assertIn('id="searchProgressBar"', html)
        self.assertIn('id="searchHotWordsBar"', html)
        self.assertIn('热词1', html)
        self.assertIn('热词2', html)
        self.assertIn('openResourceRequestBtn', html)

        # Now test disabling
        save_hot_searches_config(False, ["热词1"])
        save_resource_request_config(False)

        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertNotIn('openResourceRequestBtn', html)
        self.assertNotIn('searchHotWordsBar', html)

    def test_template_2_search_page_rendering(self):
        from src.services.system_config_service import save_active_theme
        save_active_theme("aurora")
        try:
            save_hot_searches_config(True, ["仙逆", "凡人修仙传"])
            save_resource_request_config(True)

            resp = self.client.get("/search?q=test")
            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)

            self.assertIn("openRequestModalBtn", html)
            self.assertIn("sideRequestBtn", html)
            self.assertIn("hotSearchList", html)
            self.assertIn("window.HOT_SEARCH_WORDS", html)

            # Test disabling
            save_hot_searches_config(False, ["仙逆"])
            save_resource_request_config(False)

            resp = self.client.get("/search?q=test")
            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)

            self.assertNotIn("openRequestModalBtn", html)
            self.assertNotIn("sideRequestBtn", html)
            self.assertNotIn("hotSearchList", html)
        finally:
            save_active_theme("default")

if __name__ == "__main__":
    unittest.main()
