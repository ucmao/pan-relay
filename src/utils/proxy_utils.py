"""
出站网络代理工具。

项目中三类第三方请求可以分别配置独立代理（留空即直连），均由前台 Web 与开放 API 两层共用：
- Telegram 频道抓取：TG_PROXY / 搜索源页「搜索调度参数设置」
- API 接口搜索源：API_PROXY / 搜索源页「搜索调度参数设置」
- 网盘链接测活：LINK_CHECK_PROXY / 系统配置「搜索与风控」分页「测活网络代理」

插件搜索与网盘账号操作（转存、保活等）不走这些代理。
配置了代理时一律经代理发出，代理不可用直接报错，不回退直连，避免暴露服务器真实 IP。
"""

from typing import Dict, Optional
from urllib.parse import urlsplit, urlunsplit

import requests

ALLOWED_PROXY_SCHEMES = ("http", "https", "socks5", "socks5h")
PROXY_FORMAT_HINT = "代理地址格式应为 协议://[用户名:密码@]主机:端口，协议支持 http、https、socks5、socks5h"


def normalize_proxy_url(value: Optional[str]) -> str:
    """
    规范化并校验代理地址，空值返回空字符串。
    未写协议时按 http 处理（与 requests 的行为一致）。
    """
    url = str(value or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = f"http://{url}"

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ValueError(PROXY_FORMAT_HINT)

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_PROXY_SCHEMES or not parts.hostname or not port:
        raise ValueError(PROXY_FORMAT_HINT)
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def to_requests_proxies(proxy_url: Optional[str]) -> Optional[Dict[str, str]]:
    """转换为 requests 的 proxies 参数；未配置代理返回 None。"""
    url = normalize_proxy_url(proxy_url)
    if not url:
        return None
    return {"http": url, "https": url}


def mask_proxy_url(proxy_url: Optional[str]) -> str:
    """隐藏代理地址中的密码，用于日志与界面提示。"""
    url = str(proxy_url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url if "://" in url else f"http://{url}")
        if parts.password is None:
            return url
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        netloc = f"{parts.username or ''}:***@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except ValueError:
        return "***"


def _raise_on_proxy_auth_error(response, *args, **kwargs):
    # HTTPS 经代理隧道时，隧道建立失败由 requests 抛出 ProxyError；
    # 访问 HTTP 地址时代理会直接回 407，这里同样转为异常，避免被当成目标站点的响应解析。
    if response.status_code == 407:
        raise requests.exceptions.ProxyError("代理认证失败（HTTP 407），请检查代理用户名和密码", response=response)
    return response


def new_proxy_session(proxy_url: str) -> requests.Session:
    """
    创建一个强制经指定代理发出请求的 Session。

    - 每次新建 Session 即新建连接，配合"每个连接换一个出口 IP"的住宅代理网关，
      保证每次检测使用新的 IP；同一 Session 内的多步请求复用连接与 IP。
    - 关闭 trust_env，避免系统 HTTP(S)_PROXY / NO_PROXY 环境变量覆盖或绕过配置的代理。
    """
    proxies = to_requests_proxies(proxy_url)
    if not proxies:
        raise ValueError("未配置代理地址")
    session = requests.Session()
    session.trust_env = False
    session.proxies.update(proxies)
    session.hooks["response"].append(_raise_on_proxy_auth_error)
    return session
