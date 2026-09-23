# tests/test_link_checker_modular.py

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from src.services.link_checker import (
    STATE_BAD,
    STATE_LOCKED,
    STATE_OK,
    STATE_UNSUPPORTED,
    LinkCheckEngine,
    check_link,
    check_links_batch,
)
from src.services.link_checker.detectors import (
    AliyunDetector,
    BaiduDetector,
    CMCCDetector,
    Pan115Detector,
    Pan123Detector,
    QuarkDetector,
    TianyiDetector,
    UCDetector,
    XunleiDetector,
    UnicomDetector,
    WukongDetector,
    GuangyaDetector,
)


class ModularLinkCheckerTest(unittest.TestCase):
    def setUp(self):
        self.engine = LinkCheckEngine()
        self.engine.clear_cache()

    # --- 1. 夸克网盘深度测试 ---
    @patch("requests.Session.get")
    @patch("requests.Session.post")
    def test_quark_valid_with_files(self, mock_post, mock_get):
        token_resp = MagicMock()
        token_resp.json.return_value = {"code": 0, "data": {"stoken": "mock_stoken"}}
        mock_post.return_value = token_resp

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "code": 0,
            "data": {
                "list": [{"file_name": "movie.mp4"}, {"file_name": "sub.srt"}],
                "share": {"status": 1, "partial_violation": False},
                "is_expire": False,
            },
        }
        mock_get.return_value = detail_resp

        res = check_link("https://pan.quark.cn/s/c502b66a87c5")
        self.assertEqual(STATE_OK, res["state"])
        self.assertEqual(2, res["file_count"])
        self.assertEqual("链接有效", res["summary"])

    @patch("requests.Session.get")
    @patch("requests.Session.post")
    def test_quark_empty_file_list(self, mock_post, mock_get):
        """测试夸克虽然页面正常但文件已被清空或删除（空资源）"""
        token_resp = MagicMock()
        token_resp.json.return_value = {"code": 0, "data": {"stoken": "mock_stoken"}}
        mock_post.return_value = token_resp

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "code": 0,
            "data": {
                "list": [],  # 空文件列表
                "share": {"status": 1, "partial_violation": False},
                "is_expire": False,
            },
        }
        mock_get.return_value = detail_resp

        res = check_link("https://pan.quark.cn/s/emptyquark123")
        self.assertEqual(STATE_BAD, res["state"])
        self.assertEqual(0, res["file_count"])
        self.assertIn("文件列表为空", res["summary"])

    @patch("requests.Session.get")
    @patch("requests.Session.post")
    def test_quark_violation_and_expire(self, mock_post, mock_get):
        """测试夸克部分违规或过期"""
        token_resp = MagicMock()
        token_resp.json.return_value = {"code": 0, "data": {"stoken": "mock_stoken"}}
        mock_post.return_value = token_resp

        # 违规
        violation_resp = MagicMock()
        violation_resp.json.return_value = {
            "code": 0,
            "data": {
                "list": [{"file_name": "bad.mp4"}],
                "share": {"status": 3, "partial_violation": True},
                "is_expire": False,
            },
        }
        mock_get.return_value = violation_resp

        res = check_link("https://pan.quark.cn/s/violate123", force_refresh=True)
        self.assertEqual(STATE_BAD, res["state"])
        self.assertIn("违规", res["summary"])

    @patch("requests.Session.post")
    def test_quark_passcode_locked(self, mock_post):
        """测试夸克需要提取码"""
        token_resp = MagicMock()
        token_resp.json.return_value = {"code": 41008, "message": "请输入提取码"}
        mock_post.return_value = token_resp

        res = check_link("https://pan.quark.cn/s/locked123", force_refresh=True)
        self.assertEqual(STATE_LOCKED, res["state"])

    # --- 2. 百度网盘深度测试 ---
    @patch("requests.Session.get")
    def test_baidu_valid_and_empty(self, mock_get):
        # 有效资源
        ok_resp = MagicMock()
        ok_resp.json.return_value = {
            "errno": 0,
            "list": [{"server_filename": "video.mkv"}],
        }
        mock_get.return_value = ok_resp

        res = check_link("https://pan.baidu.com/s/1okbaidu123")
        self.assertEqual(STATE_OK, res["state"])
        self.assertEqual(1, res["file_count"])

        # 深入判空：errno == 0 但 list 为空
        empty_resp = MagicMock()
        empty_resp.json.return_value = {
            "errno": 0,
            "list": [],
        }
        mock_get.return_value = empty_resp

        res_empty = check_link("https://pan.baidu.com/s/1emptybaidu123", force_refresh=True)
        self.assertEqual(STATE_BAD, res_empty["state"])
        self.assertIn("无文件", res_empty["summary"])

    @patch("requests.Session.get")
    def test_baidu_violation(self, mock_get):
        violation_resp = MagicMock()
        violation_resp.json.return_value = {
            "errno": -7,
            "errmsg": "该分享因违规已被删除",
        }
        mock_get.return_value = violation_resp

        res = check_link("https://pan.baidu.com/s/1violatebaidu", force_refresh=True)
        self.assertEqual(STATE_BAD, res["state"])

    # --- 3. 阿里云盘深度测试 ---
    @patch("requests.Session.post")
    def test_aliyun_valid_and_empty(self, mock_post):
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "share_name": "全套剧集",
            "file_count": 10,
            "share_status": "enabled",
        }
        mock_post.return_value = ok_resp

        res = check_link("https://www.alipan.com/s/aliok123")
        self.assertEqual(STATE_OK, res["state"])
        self.assertEqual(10, res["file_count"])

        # 空文件判断
        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.json.return_value = {
            "share_name": "",
            "file_count": 0,
            "share_status": "enabled",
        }
        mock_post.return_value = empty_resp

        res_empty = check_link("https://www.alipan.com/s/aliempty123", force_refresh=True)
        self.assertEqual(STATE_BAD, res_empty["state"])
        self.assertIn("为空", res_empty["summary"])

    # --- 4. UC、迅雷、123、天翼、115、移动云盘测试 ---
    @patch("requests.Session.get")
    def test_uc_detector(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html><body>分享文件列表 drive.uc.cn</body></html>"
        mock_get.return_value = resp

        res = check_link("https://drive.uc.cn/s/ucok123", force_refresh=True)
        self.assertEqual(STATE_OK, res["state"])

        # 失效
        resp_bad = MagicMock()
        resp_bad.status_code = 200
        resp_bad.text = "<div>该分享已失效已被删除</div>"
        mock_get.return_value = resp_bad

        res_bad = check_link("https://drive.uc.cn/s/ucbad123", force_refresh=True)
        self.assertEqual(STATE_BAD, res_bad["state"])

    @patch("requests.Session.get")
    def test_xunlei_detector(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"share_status": "OK", "file_count": 3, "share_name": "迅雷合集"}
        mock_get.return_value = resp

        res = check_link("https://pan.xunlei.com/s/xunlei123", force_refresh=True)
        self.assertEqual(STATE_OK, res["state"])
        self.assertEqual(3, res["file_count"])

    @patch("requests.Session.get")
    def test_pan123_detector(self, mock_get):
        resp = MagicMock()
        resp.json.return_value = {"code": 0, "data": {"FileCount": 5, "ShareName": "123资源"}}
        mock_get.return_value = resp

        res = check_link("https://www.123pan.com/s/pan123ok", force_refresh=True)
        self.assertEqual(STATE_OK, res["state"])
        self.assertEqual(5, res["file_count"])

    @patch("requests.Session.get")
    def test_tianyi_detector(self, mock_get):
        resp = MagicMock()
        resp.text = "<shareVO><fileName>天翼文档.pdf</fileName></shareVO>"
        mock_get.return_value = resp

        res = check_link("https://cloud.189.cn/t/tianyi123", force_refresh=True)
        self.assertEqual(STATE_OK, res["state"])

    @patch("requests.Session.get")
    def test_pan115_detector(self, mock_get):
        resp = MagicMock()
        resp.json.return_value = {"state": True, "data": {"count": 2}}
        mock_get.return_value = resp

        res = check_link("https://115.com/s/pan115ok?password=test", force_refresh=True)
        self.assertEqual(STATE_OK, res["state"])
        self.assertEqual(2, res["file_count"])

    @patch("requests.Session.get")
    def test_cmcc_detector(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html><body>移动云盘 共享文件 139.com</body></html>"
        mock_get.return_value = resp

        res = check_link("https://yun.139.com/shareweb/#/w/i/cmcc123", force_refresh=True)
        self.assertEqual(STATE_OK, res["state"])

    @patch("requests.Session.get")
    def test_unicom_detector(self, mock_get):
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.text = "<html><body>联通云盘 沃云盘 资源下载 pan.wo.cn</body></html>"
        mock_get.return_value = resp_ok

        res_ok = check_link("https://pan.wo.cn/s/unicom123", force_refresh=True)
        self.assertEqual(STATE_OK, res_ok["state"])

        resp_bad = MagicMock()
        resp_bad.status_code = 200
        resp_bad.text = "<div>该分享已失效已被删除</div>"
        mock_get.return_value = resp_bad

        res_bad = check_link("https://pan.wo.cn/s/unicombad", force_refresh=True)
        self.assertEqual(STATE_BAD, res_bad["state"])

    @patch("requests.Session.get")
    def test_wukong_detector(self, mock_get):
        resp_ok = MagicMock()
        resp_ok.json.return_value = {
            "code": 0,
            "data": {
                "files": [{"file_id": "1", "name": "test.mp4"}],
                "title": "悟空合集",
            },
        }
        mock_get.return_value = resp_ok

        res_ok = check_link("https://pan.wkbrowser.com/s/wukong123", force_refresh=True)
        self.assertEqual(STATE_OK, res_ok["state"])
        self.assertEqual(1, res_ok["file_count"])

        # 密码锁定
        resp_lock = MagicMock()
        resp_lock.json.return_value = {"code": 401, "message": "请输入提取码"}
        mock_get.return_value = resp_lock

        res_lock = check_link("https://pan.wkbrowser.com/s/wukonglock", force_refresh=True)
        self.assertEqual(STATE_LOCKED, res_lock["state"])

    @patch("requests.Session.get")
    def test_guangya_detector(self, mock_get):
        resp_ok = MagicMock()
        resp_ok.json.return_value = {
            "code": 0,
            "files": [{"id": "g1", "name": "photo.png"}],
        }
        mock_get.return_value = resp_ok

        res_ok = check_link("https://www.guangyapan.com/s/guangya123", force_refresh=True)
        self.assertEqual(STATE_OK, res_ok["state"])
        self.assertEqual(1, res_ok["file_count"])

        # 空列表
        resp_empty = MagicMock()
        resp_empty.json.return_value = {
            "code": 0,
            "files": [],
        }
        mock_get.return_value = resp_empty

        res_empty = check_link("https://www.guangyapan.com/s/guangyaempty", force_refresh=True)
        self.assertEqual(STATE_BAD, res_empty["state"])
        self.assertEqual(0, res_empty["file_count"])

    # --- 5. 引擎 SingleFlight 并发与缓存测试 ---
    def test_cache_hit(self):
        with patch.object(self.engine._detectors[0], "check") as mock_check:
            mock_check.return_value = {"state": STATE_OK, "summary": "链接有效", "file_count": 1}

            res1 = self.engine.check_link("https://pan.quark.cn/s/cachetest123", force_refresh=True)
            self.assertFalse(res1["cache_hit"])

            res2 = self.engine.check_link("https://pan.quark.cn/s/cachetest123", force_refresh=False)
            self.assertTrue(res2["cache_hit"])
            self.assertEqual(1, mock_check.call_count)

    def test_singleflight_concurrency(self):
        """测试 10 个线程同时请求同一个链接，实际底层 check 只执行 1 次"""
        call_counter = 0
        call_lock = threading.Lock()

        def slow_check(url, password=None, session=None):
            nonlocal call_counter
            with call_lock:
                call_counter += 1
            time.sleep(0.1)
            return {"state": STATE_OK, "summary": "链接有效", "file_count": 1}

        with patch.object(self.engine._detectors[0], "check", side_effect=slow_check):
            threads = []
            results = []

            def worker():
                r = self.engine.check_link("https://pan.quark.cn/s/singleflight123", force_refresh=False)
                results.append(r)

            for _ in range(10):
                t = threading.Thread(target=worker)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            self.assertEqual(10, len(results))
            self.assertEqual(1, call_counter)  # 严格只发起 1 次探测
            for r in results:
                self.assertEqual(STATE_OK, r["state"])

    def test_check_links_batch(self):
        items = [
            {"url": "https://pan.quark.cn/s/batch1"},
            {"url": "https://pan.baidu.com/s/1batch2"},
        ]
        with patch("src.services.link_checker.LinkCheckEngine.check_link") as mock_check_single:
            mock_check_single.return_value = {"state": STATE_OK, "summary": "有效"}
            results = check_links_batch(items)
            self.assertEqual(2, len(results))


if __name__ == "__main__":
    unittest.main()
