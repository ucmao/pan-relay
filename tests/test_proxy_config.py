"""出站网络代理测试：测活代理、API 代理与公共代理工具。

所有数据库都建在系统临时目录；代理行为用本机临时启动的迷你 HTTP 代理验证，不依赖外网。
"""

import http.server
import json
import shutil
import socket
import tempfile
import threading
import os
import unittest
from unittest.mock import patch

import requests

import src.db.connection as conn_mod
from src.services import system_config_service as cfg
from src.services.link_checker.constants import STATE_OK, STATE_UNCERTAIN
from src.services.link_checker.engine import LinkCheckEngine
from src.utils.proxy_utils import (
    mask_proxy_url,
    new_proxy_session,
    normalize_proxy_url,
    to_requests_proxies,
)


class _TempDbMixin:
    def _setup_db(self):
        self.tmpdir = tempfile.mkdtemp(prefix="pan_relay_proxy_")
        self.db_path = os.path.join(self.tmpdir, "pan_relay.db")
        self._db_patcher = patch("src.db.connection.SQLITE_DB_PATH", self.db_path)
        self._db_patcher.start()
        self._seed_patcher = patch(
            "src.services.system_config_service.init_default_search_sources", lambda: None
        )
        self._seed_patcher.start()
        conn_mod._db_initialized = False
        conn_mod.init_sqlite_db()

    def _teardown_db(self):
        self._seed_patcher.stop()
        self._db_patcher.stop()
        conn_mod._db_initialized = False
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------

class TestProxyUtils(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_proxy_url(""), "")
        self.assertEqual(normalize_proxy_url("   "), "")
        self.assertEqual(normalize_proxy_url(" 127.0.0.1:7890 "), "http://127.0.0.1:7890")
        self.assertEqual(normalize_proxy_url("SOCKS5H://127.0.0.1:1080"), "socks5h://127.0.0.1:1080")
        self.assertEqual(
            normalize_proxy_url("http://u:p%40ss@gw.example.com:7777"),
            "http://u:p%40ss@gw.example.com:7777",
        )
        for bad in ("ftp://1.2.3.4:21", "http://gw.example.com", "http://:8080", "http://h:abc"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize_proxy_url(bad)

    def test_to_requests_proxies(self):
        self.assertIsNone(to_requests_proxies(""))
        self.assertEqual(
            to_requests_proxies("socks5://h:1"), {"http": "socks5://h:1", "https": "socks5://h:1"}
        )

    def test_mask_hides_password(self):
        self.assertEqual(mask_proxy_url("http://user:secret@gw.example.com:7777"), "http://user:***@gw.example.com:7777")
        self.assertEqual(mask_proxy_url("http://gw.example.com:7777"), "http://gw.example.com:7777")
        self.assertEqual(mask_proxy_url(""), "")

    def test_proxy_session_ignores_env_proxy(self):
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://env-proxy:1", "NO_PROXY": "*"}):
            with new_proxy_session("http://gw.example.com:7777") as session:
                self.assertFalse(session.trust_env)
                self.assertEqual(session.proxies["https"], "http://gw.example.com:7777")


# ---------------------------------------------------------------------------
# 真实代理行为（本机迷你代理）
# ---------------------------------------------------------------------------

class _RecordingProxyHandler(http.server.BaseHTTPRequestHandler):
    """把经过的请求记下来；status_code=407 时模拟代理认证失败。"""

    seen = []
    status_code = 200

    def do_GET(self):  # noqa: N802
        type(self).seen.append(self.path)
        body = b"via-proxy" if type(self).status_code == 200 else b"auth required"
        self.send_response(type(self).status_code)
        if type(self).status_code == 407:
            self.send_header("Proxy-Authenticate", 'Basic realm="proxy"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestProxyBehaviour(unittest.TestCase):
    def setUp(self):
        _RecordingProxyHandler.seen = []
        _RecordingProxyHandler.status_code = 200
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RecordingProxyHandler)
        self.proxy_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_request_goes_through_proxy(self):
        with new_proxy_session(self.proxy_url) as session:
            resp = session.get("http://target.invalid/share?id=1", timeout=5)
        self.assertEqual(resp.text, "via-proxy")
        self.assertEqual(_RecordingProxyHandler.seen, ["http://target.invalid/share?id=1"])

    def test_proxy_auth_failure_raises(self):
        _RecordingProxyHandler.status_code = 407
        with new_proxy_session(self.proxy_url) as session:
            with self.assertRaises(requests.exceptions.ProxyError):
                session.get("http://target.invalid/", timeout=5)

    def test_unreachable_proxy_does_not_fall_back_to_direct(self):
        dead_proxy = f"http://127.0.0.1:{_free_port()}"
        with new_proxy_session(dead_proxy) as session:
            with self.assertRaises(requests.exceptions.ProxyError):
                # 若回退直连，会改为访问这个本机地址并成功拿到 via-proxy
                session.get(f"{self.proxy_url}/direct", timeout=5)
        self.assertEqual(_RecordingProxyHandler.seen, [])


# ---------------------------------------------------------------------------
# 配置读写
# ---------------------------------------------------------------------------

class TestProxyConfig(_TempDbMixin, unittest.TestCase):
    def setUp(self):
        self._setup_db()

    def tearDown(self):
        self._teardown_db()

    def test_link_check_proxy_env_fallback_and_override(self):
        with patch("src.configs.app_config.LINK_CHECK_PROXY", "http://env-proxy:1"):
            self.assertEqual(cfg.get_link_check_proxy(), "http://env-proxy:1")

            self.assertTrue(cfg.save_link_check_proxy(" gw.example.com:7777 "))
            self.assertEqual(cfg.get_link_check_proxy(), "http://gw.example.com:7777")

            # 后台保存为空 = 明确直连，不再回退环境变量
            self.assertTrue(cfg.save_link_check_proxy(""))
            self.assertEqual(cfg.get_link_check_proxy(), "")

    def test_link_check_proxy_rejects_invalid(self):
        with self.assertRaises(ValueError):
            cfg.save_link_check_proxy("ftp://1.2.3.4:21")

    def test_api_proxy_defaults_and_saving(self):
        with patch("src.configs.app_config.API_PROXY", "http://env-api:2"):
            self.assertEqual(cfg.get_api_proxy(), "http://env-api:2")

            # 老版本保存的调度配置里没有 api.proxy：继续读取环境变量
            legacy = {
                "api": {"timeout": 10, "max_workers": 8},
                "tg": {"enabled": True, "proxy": "socks5h://127.0.0.1:7890", "timeout": 10, "max_workers": 4},
                "plugin": {"timeout": 10, "max_workers": 6},
            }
            self.assertTrue(cfg.set_config_value(cfg.SEARCH_SCHEDULER_CONFIG_KEY, legacy))
            self.assertEqual(cfg.get_api_proxy(), "http://env-api:2")

            saved = json.loads(json.dumps(legacy))
            saved["api"]["proxy"] = "socks5://gw.example.com:1080"
            self.assertTrue(cfg.save_search_scheduler_config(saved))
            self.assertEqual(cfg.get_api_proxy(), "socks5://gw.example.com:1080")
            # TG 代理保持原样
            self.assertEqual(cfg.get_search_scheduler_config()["tg"]["proxy"], "socks5h://127.0.0.1:7890")

            saved["api"]["proxy"] = "gw.example.com"
            with self.assertRaises(ValueError):
                cfg.save_search_scheduler_config(saved)
            self.assertEqual(cfg.get_api_proxy(), "socks5://gw.example.com:1080")


# ---------------------------------------------------------------------------
# 测活引擎接入
# ---------------------------------------------------------------------------

class _FakeDetector:
    platform_name = "fake"

    def __init__(self):
        self.sessions = []

    def can_handle(self, url, disk_type=None):
        return True

    def check(self, url, password=None, session=None):
        self.sessions.append(session)
        return {"state": STATE_OK, "summary": "ok"}


class TestLinkCheckEngineProxy(unittest.TestCase):
    def setUp(self):
        self.engine = LinkCheckEngine()
        self.engine.clear_cache()
        self.detector = _FakeDetector()
        self._orig_detectors = self.engine._detectors
        self.engine._detectors = [self.detector]

    def tearDown(self):
        self.engine._detectors = self._orig_detectors
        self.engine.clear_cache()

    def _check(self, suffix):
        return self.engine.check_link(f"https://pan.quark.cn/s/proxytest{suffix}", force_refresh=True)

    def test_direct_uses_shared_session(self):
        with patch("src.services.link_checker.engine._get_link_check_proxy", return_value=""):
            self.assertEqual(self._check("a")["state"], STATE_OK)
        self.assertIs(self.detector.sessions[0], self.engine._session)

    def test_proxy_uses_fresh_session_per_check(self):
        with patch(
            "src.services.link_checker.engine._get_link_check_proxy",
            return_value="http://user:pw@gw.example.com:7777",
        ):
            self._check("b")
            self._check("c")
        first, second = self.detector.sessions
        self.assertIsNot(first, self.engine._session)
        self.assertIsNot(first, second, "每次检测都应新建连接以更换出口 IP")
        for session in (first, second):
            self.assertFalse(session.trust_env)
            self.assertEqual(session.proxies["https"], "http://user:pw@gw.example.com:7777")

    def test_invalid_proxy_is_uncertain_not_direct(self):
        with patch("src.services.link_checker.engine._get_link_check_proxy", return_value="ftp://x:21"):
            result = self._check("d")
        self.assertEqual(result["state"], STATE_UNCERTAIN)
        self.assertIn("测活代理地址无效", result["summary"])
        self.assertEqual(self.detector.sessions, [], "代理无效时不能改为直连发起检测")


# ---------------------------------------------------------------------------
# API 搜索源接入
# ---------------------------------------------------------------------------

class TestApiSourceProxy(unittest.TestCase):
    def test_fetch_data_passes_proxy(self):
        from src.services import search_service

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"ok": True}

        with patch.object(search_service, "get_api_proxy", return_value="socks5h://gw.example.com:1080"), \
                patch.object(search_service.requests, "get", return_value=_Resp()) as mocked:
            self.assertEqual(search_service.fetch_data("https://api.example.com/s", "GET", "{}"), {"ok": True})
        self.assertEqual(
            mocked.call_args.kwargs["proxies"],
            {"http": "socks5h://gw.example.com:1080", "https": "socks5h://gw.example.com:1080"},
        )

    def test_fetch_data_direct_when_no_proxy(self):
        from src.services import search_service

        with patch.object(search_service, "get_api_proxy", return_value=""), \
                patch.object(search_service.requests, "post") as mocked:
            mocked.return_value.json.return_value = {}
            search_service.fetch_data("https://api.example.com/s", "POST", "{}")
        self.assertIsNone(mocked.call_args.kwargs["proxies"])

    def test_fetch_data_invalid_proxy_skips_request(self):
        from src.services import search_service

        with patch.object(search_service, "get_api_proxy", return_value="ftp://x:21"), \
                patch.object(search_service.requests, "get") as mocked:
            self.assertIsNone(search_service.fetch_data("https://api.example.com/s", "GET", "{}"))
        mocked.assert_not_called()

    def test_api_test_button_uses_proxy(self):
        from src.services import api_config_service

        with patch("src.services.system_config_service.get_api_proxy", return_value="http://gw.example.com:7777"), \
                patch.object(api_config_service.requests, "get") as mocked:
            api_config_service._request_api({"method": "GET", "url": "https://api.example.com/s", "request": "{}"})
        self.assertEqual(mocked.call_args.kwargs["proxies"]["https"], "http://gw.example.com:7777")


if __name__ == "__main__":
    unittest.main()
