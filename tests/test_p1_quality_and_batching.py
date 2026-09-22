import json
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from src.clients.baidu_client import BaiduPanClient
from src.clients.quark_client import QuarkPanClient
from src.clients.uc_client import UcPanClient
from src.pan_operator import create_share, _get_transfer_lock
from src.services.ad_filter_service import is_ad_filename
from src.services.system_config_service import (
    get_ad_filter_config,
    save_ad_filter_config,
)


from src.db.system_configs import delete_config_value


class TestP1QualityAndBatching(unittest.TestCase):
    def setUp(self):
        # 确保广告过滤测试处于开启状态
        save_ad_filter_config({"enabled": True, "keywords": ["公众号", "防失联", "福利群", "免费分享", "扫码进群"]})

    def tearDown(self):
        delete_config_value("ad_filter_config")

    def test_ad_filter_keyword_matching(self):
        """测试广告词匹配逻辑"""
        self.assertTrue(is_ad_filename("关注微信公众号获取解压密码.txt"))
        self.assertTrue(is_ad_filename("【防失联】最新发布页.url"))
        self.assertTrue(is_ad_filename("进福利群看后续.docx"))
        self.assertTrue(is_ad_filename("扫码进群免费领.png"))
        self.assertFalse(is_ad_filename("第01集.mp4"))
        self.assertFalse(is_ad_filename("Python从入门到精通.pdf"))
        self.assertFalse(is_ad_filename("Avatar.2009.1080p.BluRay.x264.mkv"))

    def test_ad_filter_config_toggle(self):
        """测试广告过滤禁用与启用配置"""
        save_ad_filter_config({"enabled": False, "keywords": ["公众号"]})
        self.assertFalse(is_ad_filename("关注微信公众号.txt"))

        save_ad_filter_config({"enabled": True, "keywords": ["自定义广告词"]})
        self.assertTrue(is_ad_filename("这是自定义广告词文件.txt"))
        self.assertFalse(is_ad_filename("关注微信公众号.txt"))

    @patch.object(QuarkPanClient, "del_file")
    @patch.object(QuarkPanClient, "get_share_link")
    @patch.object(QuarkPanClient, "task")
    @patch.object(QuarkPanClient, "share_task_id")
    @patch.object(QuarkPanClient, "save_task_id")
    @patch.object(QuarkPanClient, "detail")
    @patch.object(QuarkPanClient, "get_stoken")
    def test_quark_multi_file_batch_transfer(
        self, mock_stoken, mock_detail, mock_save_task, mock_share_task, mock_task, mock_link, mock_del
    ):
        """测试夸克网盘多文件批量保存与分享"""
        client = QuarkPanClient("fake_quark_cookie")
        mock_stoken.return_value = "fake_stoken"
        mock_detail.return_value = {
            "title": "电影合集",
            "list": [
                {"fid": "fid_1", "share_fid_token": "token_1", "file_name": "ep1.mp4"},
                {"fid": "fid_2", "share_fid_token": "token_2", "file_name": "ep2.mp4"},
            ],
        }
        mock_save_task.return_value = "task_save_123"
        mock_task.side_effect = [
            {"data": {"save_as": {"save_as_top_fids": ["saved_fid_1", "saved_fid_2"]}}},
            {"data": {"share_id": "share_id_999"}},
        ]
        mock_share_task.return_value = "task_share_456"
        mock_link.return_value = "https://pan.quark.cn/s/newlink"

        with patch.object(client, "get_dir_file", return_value=[]):
            file_id, file_name, share_link = client.store("https://pan.quark.cn/s/abcdef")

        self.assertEqual(share_link, "https://pan.quark.cn/s/newlink")
        self.assertEqual(file_name, "电影合集")
        mock_save_task.assert_called_once_with(
            "abcdef", "fake_stoken", ["fid_1", "fid_2"], ["token_1", "token_2"], "0"
        )
        mock_share_task.assert_called_once_with(["saved_fid_1", "saved_fid_2"], "电影合集")

    @patch.object(QuarkPanClient, "_request")
    def test_quark_task_polling_wait_pending_status(self, mock_request):
        """测试夸克网盘任务轮询：当初次返回 pending (status 0) 且包含空 save_as 字典时，不会误判提前返回"""
        client = QuarkPanClient("fake_quark_cookie")
        # 第一次请求返回 status 0 和空列表，第二次返回 status 2 和真实 fid
        mock_request.side_effect = [
            {"status": 200, "data": {"status": 0, "save_as": {"save_as_top_fids": []}}},
            {"status": 200, "data": {"status": 2, "save_as": {"save_as_top_fids": ["fid_ok_123"]}}},
        ]
        result = client.task("test_task_id")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("data", {}).get("status"), 2)
        self.assertEqual(
            result.get("data", {}).get("save_as", {}).get("save_as_top_fids"),
            ["fid_ok_123"],
        )
        self.assertEqual(mock_request.call_count, 2)


    @patch.object(QuarkPanClient, "del_file")
    @patch.object(QuarkPanClient, "get_dir_file")
    @patch.object(QuarkPanClient, "get_share_link")
    @patch.object(QuarkPanClient, "task")
    @patch.object(QuarkPanClient, "share_task_id")
    @patch.object(QuarkPanClient, "save_task_id")
    @patch.object(QuarkPanClient, "detail")
    @patch.object(QuarkPanClient, "get_stoken")
    def test_quark_ad_cleaning_in_directory(
        self, mock_stoken, mock_detail, mock_save_task, mock_share_task, mock_task, mock_link, mock_get_dir, mock_del
    ):
        """测试夸克网盘转存后自动检测并剔除广告文件"""
        client = QuarkPanClient("fake_quark_cookie")
        mock_stoken.return_value = "fake_stoken"
        mock_detail.return_value = {
            "title": "电影文件夹",
            "list": [{"fid": "dir_fid", "share_fid_token": "token_dir", "file_name": "电影文件夹"}],
        }
        mock_save_task.return_value = "task_save_123"
        mock_task.side_effect = [
            {"data": {"save_as": {"save_as_top_fids": ["saved_dir_fid"]}}},
            {"data": {"share_id": "share_id_999"}},
        ]
        mock_share_task.return_value = "task_share_456"
        mock_link.return_value = "https://pan.quark.cn/s/newlink"

        # 目录下包含 1 个正片文件 + 1 个广告引流文件
        mock_get_dir.return_value = [
            {"fid": "c_fid_1", "file_name": "第01集.mp4"},
            {"fid": "c_fid_2", "file_name": "关注公众号防失联.url"},
        ]

        file_id, file_name, share_link = client.store("https://pan.quark.cn/s/abcdef")

        self.assertEqual(share_link, "https://pan.quark.cn/s/newlink")
        # 验证广告文件 c_fid_2 是否被单独删除
        mock_del.assert_called_with(["c_fid_2"])

    @patch.object(QuarkPanClient, "del_file")
    @patch.object(QuarkPanClient, "get_dir_file")
    @patch.object(QuarkPanClient, "task")
    @patch.object(QuarkPanClient, "save_task_id")
    @patch.object(QuarkPanClient, "detail")
    @patch.object(QuarkPanClient, "get_stoken")
    def test_quark_all_ads_aborts_sharing(
        self, mock_stoken, mock_detail, mock_save_task, mock_task, mock_get_dir, mock_del
    ):
        """测试夸克网盘转存后若全部为广告，则删除空目录并中止分享"""
        client = QuarkPanClient("fake_quark_cookie")
        mock_stoken.return_value = "fake_stoken"
        mock_detail.return_value = {
            "title": "纯广告文件夹",
            "list": [{"fid": "dir_fid", "share_fid_token": "token_dir", "file_name": "纯广告文件夹"}],
        }
        mock_save_task.return_value = "task_save_123"
        mock_task.return_value = {"data": {"save_as": {"save_as_top_fids": ["saved_dir_fid"]}}}

        # 目录下全部为广告
        mock_get_dir.return_value = [
            {"fid": "ad_1", "file_name": "关注公众号.txt"},
            {"fid": "ad_2", "file_name": "福利群扫码.png"},
        ]

        file_id, file_name, share_link = client.store("https://pan.quark.cn/s/abcdef")

        self.assertIsNone(file_id)
        self.assertIsNone(share_link)
        # 验证整个文件夹被删除
        mock_del.assert_any_call("saved_dir_fid")

    @patch.object(BaiduPanClient, "del_file")
    @patch.object(BaiduPanClient, "_request")
    @patch.object(BaiduPanClient, "_create_share")
    @patch.object(BaiduPanClient, "_get_file_id_by_path")
    @patch.object(BaiduPanClient, "_transfer_file")
    @patch.object(BaiduPanClient, "_get_share_page_info")
    @patch.object(BaiduPanClient, "_parse_share_url")
    def test_baidu_ad_cleaning(
        self, mock_parse, mock_info, mock_transfer, mock_get_id, mock_share, mock_request, mock_del
    ):
        """测试百度网盘转存后自动清理目录内的广告文件"""
        client = BaiduPanClient("BDUSS=fake_baidu_cookie;")
        mock_parse.return_value = ("test_surl", "")
        mock_info.return_value = ("share_id", "uk", ["12345"], ["学习资料"])
        mock_transfer.return_value = 99999
        mock_get_id.return_value = 99999
        mock_share.return_value = "https://pan.baidu.com/s/1newshare?pwd=1234"

        # 模拟目录列表返回 1 个正常文件和 1 个广告文件
        mock_request.return_value = {
            "errno": 0,
            "list": [
                {"server_filename": "课程第一讲.mp4", "path": "/学习资料/课程第一讲.mp4"},
                {"server_filename": "扫码进群获取更多.txt", "path": "/学习资料/扫码进群获取更多.txt"},
            ],
        }

        full_path, file_name, share_link = client.store("https://pan.baidu.com/s/1test_surl")

        self.assertEqual(share_link, "https://pan.baidu.com/s/1newshare?pwd=1234")
        mock_del.assert_called_once_with(["/学习资料/扫码进群获取更多.txt"])

    @patch("src.pan_operator.get_and_validate_credential", return_value="fake_credential")
    @patch("src.pan_operator.check_link", return_value={"state": 0})
    @patch("src.pan_operator._handle_netdisk_operation")
    def test_concurrent_transfer_deduplication_lock(
        self, mock_handle_op, mock_check, mock_cred
    ):
        """测试并发转存互斥锁防击穿机制"""
        transfer_calls = []

        def slow_transfer(*args, **kwargs):
            transfer_calls.append(time.time())
            time.sleep(0.05)
            return "new_fid_1", "资源名", "https://pan.quark.cn/s/shared1"

        mock_handle_op.side_effect = slow_transfer

        share_data = {
            "share_url": "https://pan.quark.cn/s/concurrent_test_1",
            "name": "并发测试资源",
            "save_to_netdisk": {"quark": True},
        }

        results = []

        def worker():
            res = create_share(share_data)
            results.append(res)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有线程都能拿到结果
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertIsNotNone(r)


if __name__ == "__main__":
    unittest.main()
