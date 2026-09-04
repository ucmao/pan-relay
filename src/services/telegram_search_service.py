import concurrent.futures
import logging
import re
from html import unescape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.configs.app_config import (
    TG_PROXY,
    TG_SEARCH_ENABLED,
    TG_SEARCH_MAX_WORKERS,
    TG_SEARCH_TIMEOUT,
    user_agents,
)
from src.models.search_item import SearchResultItem
from src.utils.netdisk_utils import match_netdisk_link
from src.utils.test_keywords import build_test_keywords

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
    "城通网盘",
    "TeraBox",
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


def _request_proxies(proxy=None):
    if proxy is None:
        try:
            from src.services.system_config_service import get_tg_search_config
            proxy = get_tg_search_config().get("proxy", "")
        except Exception:
            proxy = TG_PROXY
    proxy = str(proxy or "").strip()
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


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


CLOUD_DISK_LABELS = {
    "链接", "地址", "资源地址", "资源", "下载地址", "网盘地址", "网盘链接", "网盘", "分享链接",
    "打开", "点击打开", "点击下载", "点此查看", "备用链接", "备用",
    "夸克", "夸克网盘", "夸克云盘", "quark", "pan.quark.cn",
    "百度", "百度网盘", "百度云", "baidu", "pan.baidu.com", "bdwp", "bdpan",
    "阿里", "阿里云", "阿里云盘", "阿里网盘", "aliyun", "alipan",
    "uc", "uc网盘", "uc云盘", "drive.uc.cn",
    "迅雷", "迅雷网盘", "迅雷云盘", "xunlei", "pan.xunlei.com",
    "115", "115网盘", "115云盘",
    "123", "123网盘", "123云盘", "123pan",
    "天翼", "天翼云", "天翼云盘", "天翼网盘", "cloud.189.cn",
    "移动", "移动云盘", "和彩云",
    "terabox", "terabox网盘", "terabox云盘", "1024tera",
    "google drive", "googledrive", "gdrive", "谷歌云盘", "谷歌网盘", "drive.google.com",
    "mega", "mega网盘", "mega.nz",
    "gofile", "gofile.io",
    "onedrive", "onedrive.live.com", "1drv.ms", "微软云盘", "微软网盘",
    "城通", "城通网盘", "ctfile", "pipipan",
}

TITLE_PREFIX_PATTERN = re.compile(
    r"^(?:(?:【|\(|\[|#)?(?:资源名称|影视名称|短剧名称|片名|剧名|名称|标题|title|资源)(?:】|\)|\])?[\s:：]+)+",
    re.IGNORECASE,
)

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u2b55\u200d\ufe0f]"
)

CHANNEL_WATERMARK_PATTERN = re.compile(
    r"(?:[|\-—~]\s*)?(?:(?:关注(?:频道|群聊|频道链接)?|永久发布页|发布页|via|来源)[\s:：]*)?@[a-zA-Z0-9_-]+.*$",
    re.IGNORECASE,
)


def clean_telegram_title(title: str) -> str:
    """清理标题，去除片名前缀、标签、表情符号及推广水印。"""
    if not title:
        return ""
    text = title.strip()

    # 1. 移除首尾表情符号
    text = EMOJI_PATTERN.sub("", text).strip()

    # 2. 移除常见前缀标签（如【片名】：、剧名：等）
    text = TITLE_PREFIX_PATTERN.sub("", text).strip()

    # 3. 移除行末连续的 hashtag（如 #4K #合集）
    parts = text.split()
    while parts and parts[-1].startswith("#"):
        parts.pop()
    text = " ".join(parts).strip()

    # 4. 移除频道推广水印后缀（如 | @tgsearchers 或 | 关注频道 @pansearch）
    text = CHANNEL_WATERMARK_PATTERN.sub("", text).strip()

    # 5. 移除残留修饰符号
    text = text.strip("-—:：|~ ")
    return text[:255]


def is_cloud_disk_label(text: str) -> bool:
    """判断一段文本是否仅为网盘名称或通用链接前缀词（防止误作为作品标题）。"""
    if not text:
        return True
    cleaned = text.strip("【】[]()：:|- ").lower()
    return cleaned in CLOUD_DISK_LABELS


def extract_title_from_link_line(line: str) -> Optional[str]:
    """
    从形如 '作品名：https://...' 或 '作品名 https://...' 的单行中提取作品标题。
    若行前缀只是网盘名称（如 '夸克网盘：'、'百度：'），则返回 None，交由上下文标题处理。
    """
    url_match = URL_PATTERN.search(line)
    if not url_match or url_match.start() == 0:
        return None

    prefix = line[: url_match.start()].strip()
    for sep in ["：", ":"]:
        if sep in prefix:
            candidate = prefix.split(sep)[0].strip()
            if is_cloud_disk_label(candidate):
                return None
            cleaned = clean_telegram_title(candidate)
            if cleaned and not is_cloud_disk_label(cleaned):
                return cleaned
            return None

    cleaned = clean_telegram_title(prefix)
    if cleaned and not is_cloud_disk_label(cleaned):
        return cleaned

    return None


def extract_items_from_message_element(message_element, dt: Optional[str] = None) -> List[SearchResultItem]:
    """
    双遍扫描 Telegram 消息节点，精确将网盘链接、上下文标题与专属提取码绑定。
    解决单帖多资源标题串味、多网盘密码错配的问题。
    """
    import copy
    soup = copy.copy(message_element)

    # 1. 将 <a> 标签转换为带有真实 URL 的文本占位
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        text = a.get_text(strip=True)
        if href and URL_PATTERN.search(href):
            a.replace_with(f" {text} {href} ")
        elif text:
            a.replace_with(f" {text} ")

    # 2. 将换行与块级标签替换为换行符
    for br in soup.find_all(["br", "p", "div", "blockquote"]):
        br.replace_with("\n" + br.get_text())

    raw_text = soup.get_text()
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return []

    # 寻找全局候选标题作为最终保底
    global_fallback_title = None
    for line in lines:
        if not URL_PATTERN.search(line) and not line.startswith("#"):
            cleaned = clean_telegram_title(line)
            if cleaned and not is_cloud_disk_label(cleaned):
                global_fallback_title = cleaned
                break

    items = []
    seen_links = set()
    current_context_title = global_fallback_title

    # 第一遍扫描：逐行解析状态机
    for idx, line in enumerate(lines):
        urls_in_line = URL_PATTERN.findall(line)

        if not urls_in_line:
            # 非链接行，检查是否为新的段落作品标题
            if line.startswith("#") and len(line.split()) <= 4:
                continue
            if any(ad in line for ad in ["关注频道", "入群交流", "永久发布页", "版权归原作者", "防走丢"]):
                continue
            if PASSWORD_PATTERN.search(line) and len(line) <= 15:
                continue

            cleaned = clean_telegram_title(line)
            if cleaned and not is_cloud_disk_label(cleaned):
                current_context_title = cleaned
        else:
            # 链接行：判断本行是否有自带的专属标题
            line_title = extract_title_from_link_line(line)
            title_to_use = line_title or current_context_title or global_fallback_title or "Telegram 频道资源"

            # 提取本行之后下一行可能存在的独立提取码
            next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
            next_line_has_url = bool(URL_PATTERN.search(next_line))

            for raw_url in urls_in_line:
                clean_url, inline_pwd = _clean_and_extract_inline_password(raw_url)
                if not clean_url:
                    continue

                netdisk_name = match_netdisk_link(clean_url)
                if netdisk_name == "其他":
                    continue

                base_key = clean_url.split("?")[0].rstrip("/")
                if base_key in seen_links:
                    continue
                seen_links.add(base_key)

                pwd = inline_pwd
                if not pwd and netdisk_name in PASSWORD_SUPPORTED_NETDISKS:
                    pwd = _extract_password_from_text(line)
                    if not pwd and next_line and not next_line_has_url:
                        pwd = _extract_password_from_text(next_line)
                    if not pwd and len(seen_links) == 1 and idx == len(lines) - 1:
                        pwd = _extract_password_from_text(raw_text)

                final_url = _attach_password(clean_url, netdisk_name, pwd)
                items.append(
                    SearchResultItem(
                        source="tg",
                        title=title_to_use,
                        share_link=final_url,
                        cloud_name=netdisk_name,
                        password=pwd,
                        datetime=dt,
                    )
                )

    return items


def _extract_title(message_element):
    text = message_element.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Telegram 频道资源"

    for line in lines:
        if not line.startswith("#") and not URL_PATTERN.search(line):
            cleaned = clean_telegram_title(line)
            if cleaned and not is_cloud_disk_label(cleaned):
                return cleaned

    return clean_telegram_title(lines[0]) or "Telegram 频道资源"


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

        time_tag = message.select_one(".tgme_widget_message_date time")
        dt = time_tag.get("datetime") if time_tag else None

        items = extract_items_from_message_element(content, dt=dt)
        for item in items:
            base_key = item.share_link.split("?")[0].rstrip("/")
            if base_key in seen:
                continue
            seen.add(base_key)
            results.append(item)

    logger.info("Telegram 频道 '%s' 解析到 %d 条网盘资源。", channel, len(results))
    return results


def search_telegram_channel(keyword, channel, proxy=None, timeout=None, raise_on_error=False):
    channel = _normalize_channel(channel)
    if not channel:
        if raise_on_error:
            raise ValueError("Telegram 频道名称不能为空")
        return []

    if timeout is None:
        try:
            from src.services.system_config_service import get_tg_search_config
            timeout = get_tg_search_config().get("timeout", TG_SEARCH_TIMEOUT)
        except Exception:
            timeout = TG_SEARCH_TIMEOUT

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
            proxies=_request_proxies(proxy),
            timeout=timeout,
        )
        response.raise_for_status()

        # 公开预览失效时，Telegram 会从 /s/<频道> 重定向到 /<频道>。
        if f"/s/{channel}" not in response.url:
            logger.warning(
                "Telegram 频道 '%s' 未返回公开预览页，最终地址为 %s。",
                channel,
                response.url,
            )
            if raise_on_error:
                raise requests.RequestException(f"频道 @{channel} 未返回公开预览页")
            return []

        return parse_telegram_search_html(response.text, channel)
    except requests.RequestException as err:
        logger.warning("Telegram 频道 '%s' 搜索失败: %s", channel, err)
        if raise_on_error:
            raise
        return []


def search_telegram_resources(keyword):
    """并发搜索配置的 Telegram 公开频道（优先使用数据库配置）。"""
    try:
        from src.db.telegram_channels import get_enabled_channel_names
        from src.services.system_config_service import get_tg_search_config
        cfg = get_tg_search_config()
        is_enabled = cfg.get("enabled", TG_SEARCH_ENABLED)
        channels = get_enabled_channel_names()
        timeout = cfg.get("timeout", TG_SEARCH_TIMEOUT)
        max_workers = cfg.get("max_workers", TG_SEARCH_MAX_WORKERS)
        proxy = cfg.get("proxy", TG_PROXY)
    except Exception:
        is_enabled = TG_SEARCH_ENABLED
        channels = []
        timeout = TG_SEARCH_TIMEOUT
        max_workers = TG_SEARCH_MAX_WORKERS
        proxy = TG_PROXY

    keyword = str(keyword or "").strip()
    if not is_enabled or not keyword or not channels:
        return []

    workers = min(max_workers, len(channels))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(search_telegram_channel, keyword, channel, proxy=proxy, timeout=timeout)
            for channel in channels
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as err:
                logger.warning("收集 Telegram 搜索结果失败: %s", err)

    deduped = []
    seen = set()
    for item in results:
        share_link = item.share_link if hasattr(item, "share_link") else item[2]
        if share_link in seen:
            continue
        seen.add(share_link)
        deduped.append(item)

    logger.info(
        "Telegram 搜索完成：关键词 '%s'，频道 %d 个，资源 %d 条。",
        keyword,
        len(channels),
        len(deduped),
    )
    return deduped


def test_telegram_connection(
    channel: str,
    keyword: Optional[str] = None,
    proxy: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """
    在线测试指定 Telegram 公开频道的连通性与检索解析能力。
    返回耗时、状态、抓取条数及前 10 条样本数据。
    """
    import time
    channel = _normalize_channel(channel)
    if not channel:
        return {
            "success": False,
            "message": "频道名称不能为空",
            "channel": "",
            "latency_ms": 0,
            "count": 0,
            "results": [],
        }

    try:
        from src.services.system_config_service import get_tg_search_config
        cfg = get_tg_search_config()
        if proxy is None:
            proxy = cfg.get("proxy", "")
        if timeout is None:
            timeout = cfg.get("timeout", 10)
    except Exception:
        proxy = proxy or TG_PROXY
        timeout = timeout or 10

    keywords = build_test_keywords(keyword)
    start_time = time.time()
    saw_empty_response = False
    last_error = None

    for test_keyword in keywords:
        try:
            results = search_telegram_channel(
                keyword=test_keyword,
                channel=channel,
                proxy=proxy,
                timeout=timeout,
                raise_on_error=True,
            )
            if not results:
                saw_empty_response = True
                continue

            latency_ms = int((time.time() - start_time) * 1000)
            serialized = [
                r.to_dict() if hasattr(r, "to_dict") else {
                    "source": r[0],
                    "title": r[1],
                    "share_link": r[2],
                    "cloud_name": r[3],
                }
                for r in results
            ]
            return {
                "success": True,
                "message": f"频道 @{channel} 使用关键词“{test_keyword}”测试成功，发现 {len(results)} 条网盘资源",
                "channel": channel,
                "keyword": test_keyword,
                "tested_keywords": keywords,
                "latency_ms": latency_ms,
                "count": len(results),
                "results": serialized[:10],
            }
        except Exception as e:
            last_error = str(e)
            logger.warning("测试 Telegram 频道 @%s 使用关键词“%s”异常，继续轮询: %s", channel, test_keyword, e)

    latency_ms = int((time.time() - start_time) * 1000)
    if saw_empty_response:
        return {
            "success": True,
            "message": f"频道 @{channel} 连通正常，但轮询关键词均未发现网盘资源",
            "channel": channel,
            "keyword": None,
            "tested_keywords": keywords,
            "latency_ms": latency_ms,
            "count": 0,
            "results": [],
        }

    logger.error("测试 Telegram 频道 @%s 多关键词轮询均异常: %s", channel, last_error)
    return {
        "success": False,
        "message": f"多关键词测试均失败: {last_error or '未知异常'}",
        "channel": channel,
        "keyword": None,
        "tested_keywords": keywords,
        "latency_ms": latency_ms,
        "count": 0,
        "results": [],
    }
