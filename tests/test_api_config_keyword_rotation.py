import unittest
from unittest.mock import Mock, patch

import requests

from src.services.api_config_service import test_single_api
from src.utils.test_keywords import build_test_keywords


class ApiConfigKeywordRotationTestCase(unittest.TestCase):
    def setUp(self):
        self.config = {
            "name": "测试源",
            "url": "https://example.com/search?name=[[keyword]]",
            "method": "GET",
            "request": "",
            "response": "data[*].[name, url]",
        }

    @staticmethod
    def response(payload, status_code=200):
        response = Mock()
        response.status_code = status_code
        response.text = payload
        return response

    def test_default_keywords_are_deduplicated_and_primary_first(self):
        self.assertEqual(["自定义", "仙逆", "逆袭", "总裁"], build_test_keywords("自定义,仙逆"))

    @patch("src.services.api_config_service.requests.get")
    def test_detailed_result_reports_no_data(self, mock_get):
        mock_get.side_effect = [self.response('{"data":[]}')] * 3

        result = test_single_api("未知ID", self.config, return_details=True)

        self.assertEqual("no_data", result[5])
        self.assertEqual(0, result[6])
        self.assertIsNone(result[7])

    @patch("src.services.api_config_service.update_api_status_in_db")
    @patch("src.services.api_config_service.requests.get")
    def test_no_data_retries_next_keyword(self, mock_get, mock_update_status):
        mock_get.side_effect = [
            self.response('{"error":"未找到相关短剧"}'),
            self.response('{"data":[{"name":"逆袭人生","url":"https://pan.quark.cn/s/test"}]}'),
        ]

        url, status, status_code, rule_status, _elapsed = test_single_api(1, self.config)

        self.assertTrue(status)
        self.assertEqual(200, status_code)
        self.assertTrue(rule_status)
        self.assertIn("逆袭", url)
        self.assertEqual(2, mock_get.call_count)
        mock_update_status.assert_called_once()

    @patch("src.services.api_config_service.update_api_enabled_status_in_db")
    @patch("src.services.api_config_service.update_api_status_in_db")
    @patch("src.services.api_config_service.requests.get")
    def test_all_no_data_stays_healthy(self, mock_get, mock_update_status, mock_disable):
        mock_get.side_effect = [self.response('{"error":"未找到相关短剧"}')] * 3

        _url, status, status_code, rule_status, _elapsed = test_single_api(1, self.config)

        self.assertTrue(status)
        self.assertEqual(200, status_code)
        self.assertTrue(rule_status)
        self.assertEqual(3, mock_get.call_count)
        mock_update_status.assert_called_once()
        mock_disable.assert_not_called()

    @patch("src.services.api_config_service.update_api_enabled_status_in_db")
    @patch("src.services.api_config_service.update_api_status_in_db")
    @patch("src.services.api_config_service.requests.get")
    def test_all_request_errors_updates_health_status_without_disabling(self, mock_get, mock_update_status, mock_disable):
        mock_get.side_effect = requests.ConnectionError("连接失败")

        _url, status, status_code, rule_status, _elapsed = test_single_api(1, self.config)

        self.assertFalse(status)
        self.assertIsNone(status_code)
        self.assertFalse(rule_status)
        self.assertEqual(3, mock_get.call_count)
        mock_update_status.assert_called_once_with("1", False, unittest.mock.ANY)
        mock_disable.assert_not_called()


if __name__ == "__main__":
    unittest.main()
