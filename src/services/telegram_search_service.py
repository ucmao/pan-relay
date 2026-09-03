import concurrent.futures
import logging
import re
from html import unescape
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from configs.app_config import (
    TG_CHANNELS,
    TG_PROXY,
    TG_SEARCH_ENABLED,
    TG_SEARCH_MAX_WORKERS,
    TG_SEARCH_TIMEOUT,
    user_agents,
)
from utils.netdisk_utils import match_netdisk_link

logger = logging.getLogger(__name__)

TELEGRAM_PUBLIC_CHANNEL_URL = "https://t.me/s/{channel}"
URL_PATTERN = re.compile(
    r"(?:magnet:\?xt=urn:btih:[A-Za-z0-9]+[^\s<>\"']*|"
    r"ed2k://\|file\|[^\s<>\"']+|https?://[^\s<>\"']+)",
    re.IGNORECASE,
)
TRAILING_URL_CHARS = ".,;:!?，。；：！？、)]}）】》〉'\""


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


def _clean_candidate_url(value):
    value = unescape(str(value or "")).strip().rstrip(TRAILING_URL_CHARS)
    return value


def _extract_supported_links(message_element):
    candidates = []

    for anchor in message_element.select("a[href]"):
        candidates.append(anchor.get("href", ""))

    message_text = message_element.get_text("\n", strip=True)
    candidates.extend(URL_PATTERN.findall(message_text))

    results = []
    seen = set()
    for candidate in candidates:
        url = _clean_candidate_url(candidate)
        if not url or url in seen:
            continue

        netdisk_name = match_netdisk_link(url)
        if netdisk_name == "其他":
            continue

        seen.add(url)
        results.append((url, netdisk_name))

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
            results.append(["tg", title, url, netdisk_name])

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
