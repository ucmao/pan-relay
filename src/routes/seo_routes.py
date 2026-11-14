"""前台资源详情页、站点地图与 robots.txt。

只为私有资源库中的永久保留资源生成页面：
- 实时搜索结果（第三方 API / TG / 插件）不在库中，不生成页面；
- 临时中转资源会被定时清理物理删除，也不生成页面，避免搜索引擎收录死链。
功能默认关闭，在「前台配置 → SEO 设置」中开启。
"""

import re
from xml.sax.saxutils import escape

from flask import Blueprint, Response, abort, redirect, render_template, request, url_for

from src.db.resources import get_public_resource, list_sitemap_resources
from src.services.system_config_service import (
    build_resource_detail_seo_meta,
    get_active_theme,
    is_frontend_enabled,
    is_resource_detail_enabled,
)

seo_bp = Blueprint("seo", __name__)

# 转存时系统自动写入的备注，含原始外部链接，不对外展示
_AUTO_REMARK_PATTERN = re.compile(r"^\s*转存自\s*[:：]")


def _public_remarks(remarks) -> str:
    lines = [
        line for line in str(remarks or "").splitlines()
        if line.strip() and not _AUTO_REMARK_PATTERN.match(line)
    ]
    return "\n".join(lines).strip()


def _absolute_url(endpoint: str, **values) -> str:
    """生成绝对地址；反向代理（HTTPS 终止）场景下优先采用 X-Forwarded-Proto / Host。"""
    scheme = (request.headers.get("X-Forwarded-Proto") or request.scheme).split(",")[0].strip() or "http"
    host = (request.headers.get("X-Forwarded-Host") or request.host).split(",")[0].strip()
    return f"{scheme}://{host}{url_for(endpoint, **values)}"


def _lastmod_date(value) -> str:
    text = str(value or "").strip()
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else ""


@seo_bp.route("/r/<int:resource_id>")
def resource_detail(resource_id: int):
    if not is_frontend_enabled():
        return redirect(url_for("auth.login"))
    if not is_resource_detail_enabled():
        abort(404)

    resource = get_public_resource(resource_id)
    if not resource:
        abort(404)

    is_dead = resource.get("health_status") == "bad"
    resource["public_remarks"] = _public_remarks(resource.get("remarks"))
    theme = get_active_theme()
    html = render_template(
        # 主题可提供 themes/<theme>/templates/detail.html 覆盖通用模板
        [f"{theme}/templates/detail.html", "resource_detail.html"],
        resource=resource,
        is_dead=is_dead,
        hide_resource_request=True,  # 求片弹窗由首页脚本驱动，详情页不展示该入口
        seo_meta=build_resource_detail_seo_meta(resource, indexable=not is_dead),
        canonical_url=_absolute_url("seo.resource_detail", resource_id=resource_id),
    )
    # 已判定失效的资源返回 410，提示搜索引擎移除收录
    return html, (410 if is_dead else 200)


@seo_bp.route("/sitemap.xml")
def sitemap():
    if not is_frontend_enabled() or not is_resource_detail_enabled():
        abort(404)

    urls = [(_absolute_url("search_index"), "")]
    for item in list_sitemap_resources():
        urls.append((
            _absolute_url("seo.resource_detail", resource_id=item["id"]),
            _lastmod_date(item.get("lastmod")),
        ))

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{escape(loc)}</loc>")
        if lastmod:
            parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return Response("\n".join(parts) + "\n", mimetype="application/xml")


@seo_bp.route("/robots.txt")
def robots_txt():
    if not is_frontend_enabled():
        # 前台关闭（纯 API 部署）时禁止抓取
        body = "User-agent: *\nDisallow: /\n"
    else:
        lines = [
            "User-agent: *",
            "Disallow: /admin",
            "Disallow: /login",
            "Disallow: /api/",
            "Allow: /",
        ]
        if is_resource_detail_enabled():
            lines += ["", f"Sitemap: {_absolute_url('seo.sitemap')}"]
        body = "\n".join(lines) + "\n"
    return Response(body, mimetype="text/plain")
