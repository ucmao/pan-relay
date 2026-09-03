import concurrent.futures
import logging
import re
from html import unescape
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.configs.app_config import (
    TG_CHANNELS,
    TG_PROXY,
    TG_SEARCH_ENABLED,
    TG_SEARCH_MAX_WORKERS,
    TG_SEARCH_TIMEOUT,
    user_agents,
)
from src.models.search_item import SearchResultItem
from src.utils.netdisk_utils import match_netdisk_link

logger = logging.getLogger(__name__)

TELEGRAM_PUBLIC_CHANNEL_URL = "https://t.me/s/{channel}"
URL_PATTERN = re.compile(
    r"(?:magnet:\?xt=urn:btih:[A-Za-z0-9]+[^\s<>\"']*|"
    r"ed2k://\|file\|[^\s<>\"']+|https?://[^\s<>\"']+)",
    re.IGNORECASE,
)
TRAILING_URL_CHARS = ".,;:!?，。；：！？、)]}）】》〉'\"#"

PASSWORD_SUPPORTED_NETDISKS = {
    "百度网盘",
    "天翼云盘",
    "123云盘",
    "迅雷网盘",
    "115网盘",
    "移动云盘",
    "阿里云盘",
}

PASSWORD_PATTERN = re.compile(
    r"(?:(?:提取|访问|提取密|密)码|pwd|code)[:：=\s]*([a-zA-Z0-9]{4,6})",
    re.IGNORECASE,
)

TIANYI_INLINE_PATTERN = re.compile(
    r"(?:（(?:访问码|提取码)：|%EF%BC%88%E8%AE%BF%E9%97%AE%E7%A0%81%EF%BC%9A)([a-zA-Z0-9]{4,6})(?:）|%EF%BC%89)?",
    re.IGNORECASE,
)

PAN123_INLINE_PATTERN = re.compile(
    r"[?&](?:提取码|%E6%8F%90%E5%8F%96%E7%A0%81)[:=]([a-zA-Z0-9]{4,6})",
    re.IGNORECASE,
)


def _request_proxies():
    if not TG_PROXY:
        return None
    return {"http": TG_PROXY, "https": TG_PROXY}


def _normalize_channel(channel):
    channel = str(channel or "").strip().lstrip("@").strip("/")
    if channel.startswith("https://t.me/") or channel.startswith("http://t.me/"):
        channel = urlparse(channel).path.strip("/")
        if channel.startswith("s/"):
            channel = channel[2:]
    return channel


def _clean_and_extract_inline_password(raw_url):
    """从 URL 中提取内联的访问码/提取码后缀，并清理 URL。"""
    raw_url = unescape(str(raw_url or "")).strip()
    pwd = None

    tianyi_match = TIANYI_INLINE_PATTERN.search(raw_url)
    if tianyi_match:
        pwd = tianyi_match.group(1)
        raw_url = raw_url[:tianyi_match.start()]

    pan123_match = PAN123_INLINE_PATTERN.search(raw_url)
    if pan123_match:
        pwd = pan123_match.group(1)
        raw_url = PAN123_INLINE_PATTERN.sub("", raw_url)

    clean_url = raw_url.rstrip(TRAILING_URL_CHARS)
    return clean_url, pwd


def _extract_password_from_text(text):
    """从文本或上下文片段中提取 4-6 位提取码/密码。"""
    if not text:
        return None

    query_match = re.search(r"[?&](?:pwd|password)=([a-zA-Z0-9]{4,6})", text, re.IGNORECASE)
    if query_match:
        return query_match.group(1)

    match = PASSWORD_PATTERN.search(text)
    if match:
        return match.group(1)

    return None


def _attach_password(url, netdisk_name, pwd):
    """为网盘链接拼接提取码参数（若已有密码则不重复追加）。"""
    if not pwd:
        return url

    if re.search(r"[?&](?:pwd|password)=", url, re.IGNORECASE):
        return url

    param_name = "password" if netdisk_name == "115网盘" else "pwd"
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{param_name}={pwd}"


def _get_anchor_context(anchor):
    """提取 <a> 标签紧邻的前后兄弟节点文本（跨过 br 等节点）。"""
    parts = []

    curr = anchor.previous_sibling
    for _ in range(2):
        if not curr:
            break
        text = curr.get_text() if hasattr(curr, "get_text") else str(curr or "")
        if text.strip():
            parts.insert(0, text.strip())
        curr = curr.previous_sibling

    parts.append(anchor.get_text(strip=True))

    curr = anchor.next_sibling
    for _ in range(3):
        if not curr:
            break
        text = curr.get_text() if hasattr(curr, "get_text") else str(curr or "")
        if text.strip():
            parts.append(text.strip())
        curr = curr.next_sibling

    return " ".join(parts)


def _clean_candidate_url(value):
    value = unescape(str(value or "")).strip().rstrip(TRAILING_URL_CHARS)
    return value


def _extract_supported_links(message_element):
    raw_candidates = []

    # 1. 优先提取 <a> 标签链接及其邻近上下文
    for anchor in message_element.select("a[href]"):
        href = anchor.get("href", "").strip()
        if href:
            context = _get_anchor_context(anchor)
            raw_candidates.append((href, context))

    # 2. 从纯文本行中提取链接及前后行上下文
    message_text = message_element.get_text("\n", strip=True)
    lines = [line.strip() for line in message_text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        for text_url in URL_PATTERN.findall(line):
            next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
            context = f"{line}\n{next_line}"
            raw_candidates.append((text_url, context))

    results = []
    seen = set()

    for raw_url, context in raw_candidates:
        clean_url, inline_pwd = _clean_and_extract_inline_password(raw_url)
        if not clean_url:
            continue

        netdisk_name = match_netdisk_link(clean_url)
        if netdisk_name == "其他":
            continue

        base_key = clean_url.split("?")[0].rstrip("/")
        if base_key in seen:
            continue

        pwd = inline_pwd
        if not pwd and netdisk_name in PASSWORD_SUPPORTED_NETDISKS:
            pwd = _extract_password_from_text(context)
            # 仅当消息中只有一个候选链接时，才回退到全文本范围匹配提取码
            if not pwd and len(raw_candidates) == 1:
                pwd = _extract_password_from_text(message_text)

        final_url = _attach_password(clean_url, netdisk_name, pwd)
        seen.add(base_key)
        results.append((final_url, netdisk_name))

    return results


def _extract_title(message_element):
    text = message_element.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Telegram 频道资源"

    for line in lines:
        if line.startswith("名称："):
            return line.partition("：")[2].strip() or lines[0]
        if line.startswith("名称:"):
            return line.partition(":")[2].strip() or lines[0]

    for line in lines:
        if not line.startswith("#") and not URL_PATTERN.search(line):
            return line[:255]

    return lines[0][:255]


def parse_telegram_search_html(html, channel):
    """解析 Telegram 公开频道搜索页，返回项目统一的搜索结果结构。"""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    for wrapper in soup.select(".tgme_widget_message_wrap"):
        message = wrapper.select_one(".tgme_widget_message") or wrapper
        content = message.select_one(".tgme_widget_message_text")
        if content is None:
            continue

        title = _extract_title(content)
        for url, netdisk_name in _extract_supported_links(content):
            if url in seen:
                continue
            seen.add(url)
            results.append(
                SearchResultItem(source="tg", title=title, share_link=url, cloud_name=netdisk_name)
            )

    logger.info("Telegram 频道 '%s' 解析到 %d 条网盘资源。", channel, len(results))
    return results


def search_telegram_channel(keyword, channel):
    channel = _normalize_channel(channel)
    if not channel:
        return []

    target_url = TELEGRAM_PUBLIC_CHANNEL_URL.format(channel=channel)
    headers = {
        "User-Agent": user_agents[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        response = requests.get(
            target_url,
            params={"q": keyword},
            headers=headers,
            proxies=_request_proxies(),
            timeout=TG_SEARCH_TIMEOUT,
        )
        response.raise_for_status()

        # 公开预览失效时，Telegram 会从 /s/<频道> 重定向到 /<频道>。
        if f"/s/{channel}" not in response.url:
            logger.warning(
                "Telegram 频道 '%s' 未返回公开预览页，最终地址为 %s。",
                channel,
                response.url,
            )
            return []

        return parse_telegram_search_html(response.text, channel)
    except requests.RequestException as err:
        logger.warning("Telegram 频道 '%s' 搜索失败: %s", channel, err)
        return []


def search_telegram_resources(keyword):
    """并发搜索配置的 Telegram 公开频道。"""
    keyword = str(keyword or "").strip()
    if not TG_SEARCH_ENABLED or not keyword or not TG_CHANNELS:
        return []

    max_workers = min(TG_SEARCH_MAX_WORKERS, len(TG_CHANNELS))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(search_telegram_channel, keyword, channel)
            for channel in TG_CHANNELS
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as err:
                logger.warning("收集 Telegram 搜索结果失败: %s", err)

    deduped = []
    seen = set()
    for item in results:
        if item[2] in seen:
            continue
        seen.add(item[2])
        deduped.append(item)

    logger.info(
        "Telegram 搜索完成：关键词 '%s'，频道 %d 个，资源 %d 条。",
        keyword,
        len(TG_CHANNELS),
        len(deduped),
    )
    return deduped
