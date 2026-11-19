"""资源详情页、站点地图与 robots.txt 测试（Issue #7）。

数据库建在系统临时目录，不影响 data/ 下的真实数据。
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import src.db.connection as conn_mod
from app import app
from src.db.connection import db_cursor
from src.services.system_config_service import (
    build_frontend_seo_meta,
    build_resource_detail_seo_meta,
    get_frontend_seo_config,
    is_resource_detail_enabled,
    save_frontend_seo_config,
)
from src.utils.auth_utils import create_jwt_token


def _insert(name, share_link, origin_type="manual", is_replaced=0, health_status="ok",
            remarks="", cloud_name="夸克网盘"):
    with db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO resources (name, share_link, cloud_name, type, remarks, origin_type, is_replaced, health_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, share_link, cloud_name, "电影", remarks, origin_type, is_replaced, health_status),
        )
        return cursor.lastrowid


class ResourceDetailSeoTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="pan_relay_seo_")
        self.db_path = os.path.join(self.tmpdir, "pan_relay.db")
        self._db_patcher = patch("src.db.connection.SQLITE_DB_PATH", self.db_path)
        self._db_patcher.start()
        self._seed_patcher = patch(
            "src.services.system_config_service.init_default_search_sources", lambda: None
        )
        self._seed_patcher.start()
        self._frontend_patcher = patch("src.routes.seo_routes.is_frontend_enabled", return_value=True)
        self.mock_frontend = self._frontend_patcher.start()
        conn_mod._db_initialized = False
        conn_mod.init_sqlite_db()
        self.client = app.test_client()

        self.public_id = _insert("流浪地球2 4K", "https://pan.quark.cn/s/public1",
                                 remarks="转存自: https://pan.quark.cn/s/origin\n高码率版本，含花絮")
        self.relay_id = _insert("临时中转资源", "https://pan.quark.cn/s/relay1", origin_type="relay", is_replaced=1)
        self.replaced_id = _insert("换链待清理", "https://pan.quark.cn/s/replaced1", origin_type="manual", is_replaced=1)
        self.dead_id = _insert("已失效资源", "https://pan.quark.cn/s/dead1", health_status="bad")

    def tearDown(self):
        self._frontend_patcher.stop()
        self._seed_patcher.stop()
        self._db_patcher.stop()
        conn_mod._db_initialized = False
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _enable(self, enabled=True):
        config = get_frontend_seo_config()
        config["detail"]["enabled"] = enabled
        self.assertTrue(save_frontend_seo_config(config))

    # --- 默认关闭 ---

    def test_disabled_by_default(self):
        self.assertFalse(is_resource_detail_enabled())
        self.assertEqual(404, self.client.get(f"/r/{self.public_id}").status_code)
        self.assertEqual(404, self.client.get("/sitemap.xml").status_code)
        robots = self.client.get("/robots.txt")
        self.assertEqual(200, robots.status_code)
        self.assertIn("Disallow: /admin", robots.text)
        self.assertNotIn("Sitemap:", robots.text)

    # --- 详情页 ---

    def test_detail_page_for_permanent_resource(self):
        self._enable()
        resp = self.client.get(f"/r/{self.public_id}")
        self.assertEqual(200, resp.status_code)
        self.assertIn("流浪地球2 4K", resp.text)
        self.assertIn("https://pan.quark.cn/s/public1", resp.text)
        self.assertIn("高码率版本，含花絮", resp.text)
        # 系统自动备注含原始外链，不应展示
        self.assertNotIn("pan.quark.cn/s/origin", resp.text)
        self.assertIn('content="index,follow"', resp.text)
        self.assertIn(f'rel="canonical" href="http://localhost/r/{self.public_id}"', resp.text)

    def test_temporary_resources_have_no_page(self):
        self._enable()
        self.assertEqual(404, self.client.get(f"/r/{self.relay_id}").status_code)
        self.assertEqual(404, self.client.get(f"/r/{self.replaced_id}").status_code)
        self.assertEqual(404, self.client.get("/r/999999").status_code)

    def test_dead_resource_returns_410_noindex(self):
        self._enable()
        resp = self.client.get(f"/r/{self.dead_id}")
        self.assertEqual(410, resp.status_code)
        self.assertIn('content="noindex,follow"', resp.text)
        self.assertNotIn("https://pan.quark.cn/s/dead1", resp.text)

    def test_canonical_respects_forwarded_headers(self):
        self._enable()
        resp = self.client.get(
            f"/r/{self.public_id}",
            headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "pan.example.com"},
        )
        self.assertIn(f'href="https://pan.example.com/r/{self.public_id}"', resp.text)

    def test_seo_meta_tokens(self):
        meta = build_resource_detail_seo_meta({"name": "测试片", "cloud_name": "百度网盘"})
        self.assertTrue(meta["title"].startswith("测试片 - 百度网盘资源"))
        self.assertEqual("index,follow", meta["robots"])

    # --- 站点地图与 robots ---

    def test_sitemap_lists_only_public_alive_resources(self):
        self._enable()
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(200, resp.status_code)
        self.assertEqual("application/xml", resp.mimetype)
        self.assertIn("<loc>http://localhost/</loc>", resp.text)
        self.assertIn(f"<loc>http://localhost/r/{self.public_id}</loc>", resp.text)
        for hidden in (self.relay_id, self.replaced_id, self.dead_id):
            self.assertNotIn(f"/r/{hidden}<", resp.text)
        self.assertIn("<lastmod>", resp.text)

    def test_robots_includes_sitemap_when_enabled(self):
        self._enable()
        robots = self.client.get("/robots.txt")
        self.assertIn("Sitemap: http://localhost/sitemap.xml", robots.text)

    def test_frontend_disabled_blocks_crawling(self):
        self._enable()
        self.mock_frontend.return_value = False
        self.assertIn("Disallow: /\n", self.client.get("/robots.txt").text)
        self.assertEqual(404, self.client.get("/sitemap.xml").status_code)
        self.assertEqual(302, self.client.get(f"/r/{self.public_id}").status_code)

    # --- 后台配置接口 ---

    def test_admin_api_saves_detail_config(self):
        self.client.set_cookie("token", create_jwt_token())
        headers = {"Authorization": f"Bearer {create_jwt_token()}"}
        resp = self.client.put("/admin/api/frontend-seo-config", headers=headers, json={
            "detail": {"enabled": True, "title": "{name} 下载 - {site_name}", "description": "d", "keywords": ""},
        })
        self.assertEqual(200, resp.status_code, resp.text)
        config = get_frontend_seo_config()
        self.assertTrue(config["detail"]["enabled"])
        self.assertEqual("{name} 下载 - {site_name}", config["detail"]["title"])
        # 未提交的其它配置保持不变
        self.assertIn("{site_name}", config["home"]["title"])

        bad = self.client.put("/admin/api/frontend-seo-config", headers=headers, json={
            "detail": {"enabled": "yes", "title": "x"},
        })
        self.assertEqual(400, bad.status_code)


    # --- 固定站点根地址 ---

    def test_site_url_overrides_request_host(self):
        self._enable()
        config = get_frontend_seo_config()
        config["detail"]["site_url"] = "https://pan.example.com"
        self.assertTrue(save_frontend_seo_config(config))
        # 即使用 IP / 伪造的 Host 访问，canonical 与站点地图也固定为配置的域名
        resp = self.client.get(f"/r/{self.public_id}", headers={"X-Forwarded-Host": "evil.example.net"})
        self.assertIn(f'rel="canonical" href="https://pan.example.com/r/{self.public_id}"', resp.text)
        self.assertNotIn("evil.example.net", resp.text)
        sitemap = self.client.get("/sitemap.xml").text
        self.assertIn(f"<loc>https://pan.example.com/r/{self.public_id}</loc>", sitemap)
        self.assertNotIn("localhost", sitemap)
        self.assertIn("Sitemap: https://pan.example.com/sitemap.xml", self.client.get("/robots.txt").text)

    def test_admin_api_validates_site_url(self):
        self.client.set_cookie("token", create_jwt_token())
        headers = {"Authorization": f"Bearer {create_jwt_token()}"}
        ok = self.client.put("/admin/api/frontend-seo-config", headers=headers, json={
            "detail": {"enabled": True, "title": "{name}", "site_url": " https://Pan.Example.com/ "},
        })
        self.assertEqual(200, ok.status_code, ok.text)
        self.assertEqual("https://pan.example.com", get_frontend_seo_config()["detail"]["site_url"])
        for bad_url in ("pan.example.com", "ftp://pan.example.com", "https://pan.example.com/?a=1"):
            bad = self.client.put("/admin/api/frontend-seo-config", headers=headers, json={
                "detail": {"enabled": True, "title": "{name}", "site_url": bad_url},
            })
            self.assertEqual(400, bad.status_code, bad_url)
        self.assertEqual("https://pan.example.com", get_frontend_seo_config()["detail"]["site_url"])

    # --- lastmod 不随体检漂移 ---

    def test_health_check_keeps_updated_at(self):
        from src.db.resources import update_resource_basic_info
        from src.db.resources import update_resource_health
        with db_cursor() as cursor:
            cursor.execute("UPDATE resources SET updated_at = '2020-01-02 03:04:05' WHERE id = ?", (self.public_id,))
        self.assertTrue(update_resource_health(self.public_id, "ok", "fine"))
        with db_cursor() as cursor:
            cursor.execute("SELECT updated_at, checked_at FROM resources WHERE id = ?", (self.public_id,))
            updated_at, checked_at = tuple(cursor.fetchone())
        self.assertEqual("2020-01-02 03:04:05", str(updated_at))
        self.assertIsNotNone(checked_at)
        self._enable()
        self.assertIn("<lastmod>2020-01-02</lastmod>", self.client.get("/sitemap.xml").text)

        # 后台编辑资源内容则应刷新 updated_at
        ok, _ = update_resource_basic_info(self.public_id, {"name": "流浪地球2 4K 修订", "share_link": "https://pan.quark.cn/s/public1"})
        self.assertTrue(ok)
        with db_cursor() as cursor:
            cursor.execute("SELECT updated_at FROM resources WHERE id = ?", (self.public_id,))
            self.assertNotEqual("2020-01-02 03:04:05", str(tuple(cursor.fetchone())[0]))

    # --- 内链 ---

    def test_detail_page_links_to_neighbours(self):
        self._enable()
        newer_id = _insert("新资源", "https://pan.quark.cn/s/newer")
        resp = self.client.get(f"/r/{newer_id}")
        self.assertIn(f'href="/r/{self.public_id}"', resp.text)
        for hidden in (self.relay_id, self.replaced_id, self.dead_id):
            self.assertNotIn(f'href="/r/{hidden}"', resp.text)
        self.assertNotIn(f'href="/r/{newer_id}"', resp.text)
        # 反向也能链回，详情页之间串成链
        self.assertIn(f'href="/r/{newer_id}"', self.client.get(f"/r/{self.public_id}").text)

    def test_home_lists_recent_resources_for_classic_and_aurora(self):
        for theme in ("classic", "aurora"):
            with patch("app.is_frontend_enabled", return_value=True), \
                    patch("app.get_active_theme", return_value=theme):
                self._enable(False)
                self.assertNotIn(f'href="/r/{self.public_id}"', self.client.get("/").text, theme)
                self._enable(True)
                home = self.client.get("/").text
                self.assertIn(f'href="/r/{self.public_id}"', home, theme)
                self.assertIn("最近收录", home, theme)
                self.assertNotIn(f'href="/r/{self.dead_id}"', home, theme)

    def test_search_pages_are_noindex(self):
        self.assertEqual("index,follow", build_frontend_seo_meta("home")["robots"])
        self.assertEqual("noindex,follow", build_frontend_seo_meta("search", "流浪地球")["robots"])
        # 旧版本存过 allow_indexing=True 也不再生效
        config = get_frontend_seo_config()
        config["search"]["allow_indexing"] = True
        self.assertTrue(save_frontend_seo_config(config))
        self.assertEqual("noindex,follow", build_frontend_seo_meta("search", "x")["robots"])

    def test_theme_without_detail_falls_back_to_classic(self):
        self._enable()
        with patch("src.routes.seo_routes.get_active_theme", return_value="custom_theme"):
            resp = self.client.get(f"/r/{self.public_id}")
        self.assertEqual(200, resp.status_code)
        self.assertIn("流浪地球2 4K", resp.text)
        self.assertIn('rel="canonical"', resp.text)

if __name__ == "__main__":
    unittest.main()
