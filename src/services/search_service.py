import concurrent.futures
import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

import jmespath
import requests

from src.configs.app_config import user_agents
from src.db.resources import search_resources_by_title_terms, search_resources_advanced
from src.models.search_item import SearchResultItem
from src.services.plugin_manager import plugin_manager
from src.services.sensitive_word_service import check_input_keyword, filter_search_results
from src.services.system_config_service import get_allowed_frontend_netdisks, get_title_filter_mode
from src.services.ad_filter_service import is_ad_filename
from src.services.telegram_search_service import search_telegram_channel
from src.db.telegram_channels import get_enabled_channel_names
from src.utils.netdisk_utils import (
    match_netdisk_link,
    extract_canonical_resource_key,
    extract_password_from_url,
    parse_netdisk_names,
)
from src.services.log_service import record_log, get_current_client_ip

import threading

logger = logging.getLogger(__name__)

# --- 高频搜索词 TTL 内存缓存机制 ---
_SEARCH_CACHE: Dict[str, Tuple[float, List[SearchResultItem]]] = {}
_SEARCH_CACHE_LOCK = threading.Lock()
SEARCH_CACHE_TTL_SECONDS = 300  # 默认缓存 5 分钟 (300 秒)


def get_cached_search_items(keyword: str) -> Optional[List[SearchResultItem]]:
    """读取未过期的搜索结果缓存"""
    clean_kw = str(keyword or "").strip().lower()
    if not clean_kw:
        return None
    now = time.time()
    with _SEARCH_CACHE_LOCK:
        if clean_kw in _SEARCH_CACHE:
            ts, items = _SEARCH_CACHE[clean_kw]
            if now - ts < SEARCH_CACHE_TTL_SECONDS:
                return [SearchResultItem.from_item(i) for i in items]
            else:
                del _SEARCH_CACHE[clean_kw]
    return None


def set_cached_search_items(keyword: str, items: List[Any]):
    """将搜索结果存入 TTL 缓存，支持淘汰机制"""
    clean_kw = str(keyword or "").strip().lower()
    if not clean_kw or not items:
        return
    typed_items = [SearchResultItem.from_item(i) for i in items if i]
    now = time.time()
    with _SEARCH_CACHE_LOCK:
        if len(_SEARCH_CACHE) > 500:
            expired_keys = [k for k, (ts, _) in _SEARCH_CACHE.items() if now - ts >= SEARCH_CACHE_TTL_SECONDS]
            for k in expired_keys:
                del _SEARCH_CACHE[k]
            if len(_SEARCH_CACHE) > 500:
                sorted_keys = sorted(_SEARCH_CACHE.keys(), key=lambda k: _SEARCH_CACHE[k][0])
                for k in sorted_keys[:100]:
                    del _SEARCH_CACHE[k]
        _SEARCH_CACHE[clean_kw] = (now, typed_items)


def clear_search_cache():
    """主动清空搜索结果缓存（用于后台配置变动时）"""
    with _SEARCH_CACHE_LOCK:
        _SEARCH_CACHE.clear()
    logger.info("搜索结果内存缓存已主动清空。")



def filter_results_by_frontend_netdisks(results):
    """按后台配置过滤前端可见网盘。"""
    allowed_netdisks = get_allowed_frontend_netdisks()
    if not allowed_netdisks:
        return results

    filtered_results = []
    for item in results:
        if isinstance(item, SearchResultItem):
            if item.cloud_name in allowed_netdisks:
                filtered_results.append(item)
        elif isinstance(item, (list, tuple)) and len(item) >= 4:
            netdisk_name = item[3]
            if netdisk_name in allowed_netdisks:
                filtered_results.append(item)
        elif isinstance(item, dict):
            netdisk_name = item.get("cloud_name") or match_netdisk_link(item.get("share_link", ""))
            if netdisk_name in allowed_netdisks:
                filtered_results.append(item)

    return filtered_results


def read_all_api_configs_from_db():
    """从数据库读取所有 API 配置（用于搜索服务，不排序）"""
    from src.db.api_configs import get_all_configs
    return get_all_configs(order_by_created=False)


read_api_configs = read_all_api_configs_from_db


def fetch_data(url, method, request_data, timeout=10):
    """根据配置发起 HTTP 请求并返回响应内容。"""
    headers = {
        "User-Agent": random.choice(user_agents),
        "Content-Type": "application/json",
    }

    try:
        data_obj = json.loads(request_data) if request_data else None
    except json.JSONDecodeError:
        data_obj = {}

    response = None

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=data_obj, timeout=timeout)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data_obj, timeout=timeout)
        else:
            raise requests.exceptions.RequestException(f"不支持的 HTTP 方法: {method}")

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"API 请求失败 ({url}): {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"API 响应不是有效的 JSON ({url})")
        return None


def extract_from_json(json_data, jmespath_query):
    """使用 JMESPath 表达式从 JSON 数据中提取结果。"""
    if not json_data or not jmespath_query:
        return []

    try:
        results = jmespath.search(jmespath_query, json_data)

        if results and isinstance(results, list):
            # 确保结果是 [ [title, url], [title, url], ... ] 格式
            return [[str(item[0]), str(item[1])] for item in results if len(item) >= 2]

    except Exception as e:
        logger.error(f"JMESPath 提取失败 (Query: {jmespath_query}): {e}")
        return []

    return []


def replace_keyword_in_config(configs, placeholder, keyword):
    """用实际关键词替换 API 配置中的占位符（如 '[[keyword]]'）。"""
    updated_configs = []
    placeholder = str(placeholder)
    keyword = str(keyword)

    for config in configs:
        new_config = config.copy()

        # 替换 URL
        if "url" in new_config and isinstance(new_config["url"], str):
            new_config["url"] = new_config["url"].replace(placeholder, keyword)

        # 替换 Request Body (JSON 字符串)
        if "request" in new_config and isinstance(new_config["request"], str):
            new_config["request"] = new_config["request"].replace(placeholder, keyword)

        updated_configs.append(new_config)
    return updated_configs


QUALIFIER_WORDS = {
    "4k", "1080p", "720p", "remux", "hdr", "原盘", "全集", "资料", "高清", "版",
    "mp4", "mkv", "avi", "rmvb", "pdf", "zip", "rar", "7z", "1080", "2160p"
}


def parse_search_terms_fallback(keyword: str) -> List[str]:
    """
    零第三方库依赖的智能切词：
    1. 用户含空格时，按空格切分。
    2. 无空格时，英文/数字串（如 APScheduler, Win11, 4K）整词保留；
    3. 连续中文串长于 4 字时，按双字滑动切分。
    """
    kw = str(keyword or "").strip()
    if not kw:
        return []

    if " " in kw:
        return [w for w in kw.split() if w]

    # 按英文/数字串和非 ASCII (中文/符号) 分组提取
    tokens = re.findall(r"[a-zA-Z0-9]+|[^\x00-\x7F]+", kw)
    out = []

    for tok in tokens:
        if re.fullmatch(r"[a-zA-Z0-9]+", tok):
            out.append(tok)
        else:
            if len(tok) >= 4:
                out.extend([tok[i:i + 2] for i in range(0, len(tok), 2)])
            else:
                out.append(tok)

    return [w.strip() for w in out if w.strip()]


def parse_search_terms(keyword: str) -> List[str]:
    """按任意空白字符拆分搜索词；若无空格则使用降级分词。"""
    kw = str(keyword or "").strip()
    if not kw:
        return []
    if " " in kw:
        return [w for w in kw.split() if w]
    return parse_search_terms_fallback(kw)


def get_title_matched_terms(title: str, keyword: str) -> List[str]:
    """返回标题命中的搜索词。"""
    normalized_title = str(title or "").casefold()
    terms = parse_search_terms(keyword)
    return [term for term in terms if term.casefold() in normalized_title]


def is_title_matched_loose(title: str, keyword: str) -> bool:
    """
    loose 模式匹配判断：
    1. 提取核心词（排除 4k/原盘 等通用规格词和单字符）
    2. 标题命中【任意核心词】或字符覆盖率 >= 40% 即判定通过
    """
    t_clean = str(title or "").casefold()
    terms = parse_search_terms_fallback(keyword)
    if not terms:
        return True

    core_terms = [
        w.casefold() for w in terms
        if w.casefold() not in QUALIFIER_WORDS and len(w) > 1
    ]
    if not core_terms:
        core_terms = [w.casefold() for w in terms]

    # 条件 A：命中任意一个核心词
    if any(core in t_clean for core in core_terms):
        return True

    # 条件 B：计算字符覆重合率
    kw_chars = set(keyword.casefold()) - set(" ")
    if not kw_chars:
        return False
    matched_chars = sum(1 for c in kw_chars if c in t_clean)
    return (matched_chars / len(kw_chars)) >= 0.4


def filter_results_by_title(results: List[Any], keyword: str) -> List[SearchResultItem]:
    """
    根据后台配置的标题匹配模式 (loose / exact / off) 过滤搜索结果。
    统一拦截广告/黑名单词。
    """
    if not results:
        return []

    mode = get_title_filter_mode()  # 'loose' (默认) | 'exact' | 'off'
    matched_results = []

    for item in results:
        try:
            typed_item = SearchResultItem.from_item(item)
        except (TypeError, ValueError, IndexError):
            continue

        title = typed_item.title or ""

        # 1. 任何模式下都拦截广告黑名单词（如“关注公众号”、“防走丢”）
        if is_ad_filename(title):
            continue

        # 2. 根据模式判断标题匹配
        if mode == "off":
            matched_results.append(typed_item)
        else:
            # loose 智能匹配模式（默认开启）
            if is_title_matched_loose(title, keyword):
                matched_results.append(typed_item)

    return matched_results


def clean_and_extract_data(data):
    """
    清洗并提取数据，并新增网盘信息。
    输入格式: [[source, title, url], ...]
    输出格式: [[source, title, url, netdisk_name], ...]
    """

    def extract_url(url):
        """ 清洗URL冗余内容后，提取http/磁力/迅雷等常见链接，无匹配则返回清洗后原文 """
        url = str(url).strip()
        url = re.sub(r"</?br\s*/?>.*分享", "", url, flags=re.IGNORECASE)
        url = re.sub(r"</?br\s*/?>", " ", url, flags=re.IGNORECASE)
        url_pattern = re.compile(r"(magnet:|thunder://|ed2k://|https?:\/\/).*?(?=\s|$)", re.IGNORECASE)
        match = url_pattern.search(url)
        if match:
            return match.group(0)
        return url

    def extract_title(title):
        """ 移除标题中的所有 HTML 标签（通用版），并轻量格式化 """
        title = str(title)
        title = re.sub(r"</?\w+[^>]*>", "", title)
        title = re.sub(r"(\[?(描述|简介|介绍)\]?)\s*[：:]\s*.*?$", "", title)
        title = re.sub(r"\s+", " ", title)
        return title.strip()

    cleaned_data = []
    for d_lst in data:
        source = d_lst[0]
        title = extract_title(d_lst[1])
        url = extract_url(d_lst[2])
        netdisk_name = match_netdisk_link(url)

        cleaned_data.append(
            SearchResultItem(source=source, title=title, share_link=url, cloud_name=netdisk_name)
        )

    return cleaned_data


def process_config(config, keyword, timeout=10):
    """
    处理单个 API 配置，获取、筛选数据，并返回包含网盘名称的结果。
    """
    config_name = config.get("name", "未知 API")
    final_results = []

    try:
        response_data = fetch_data(config["url"], config["method"], config["request"], timeout=timeout)

        if response_data:
            extracted_data = extract_from_json(response_data, config["response"])

            if extracted_data and isinstance(extracted_data, list):
                extracted_data_with_source = [["other", item[0], item[1]] for item in extracted_data]
                final_results = clean_and_extract_data(extracted_data_with_source)

            num_results = len(final_results)
            log_message = f"API '{config_name}' ({config['url']}) 搜索到 {num_results} 条资源。"
            if num_results > 0:
                sample_results = [res[1] for res in final_results[:2]]
                log_message += f" 示例 (Title): {sample_results}"

            logger.info(log_message)

    except Exception as e:
        logger.error(f"处理配置 '{config_name}' ({config['url']}) 时发生异常: {e}")
        return []

    return final_results


def _search_plugin(plugin, keyword):
    """执行单个插件搜索，避免一个插件失败中断其他搜索源。"""
    try:
        logger.info("插件 [%s] 开始搜索: %s", plugin.name, keyword)
        results = plugin.search(keyword)
        logger.info("插件 [%s] 搜索完成，找到 %d 条结果。", plugin.name, len(results))
        return results
    except Exception as error:
        logger.error("插件 [%s] 搜索异常: %s", plugin.name, error)
        return []


def iter_upstream_search_results(keyword):
    """按单个上游完成顺序产出 API、Telegram 频道和插件的搜索结果。"""
    from src.services.system_config_service import get_search_scheduler_config

    scheduler_config = get_search_scheduler_config()
    api_config = scheduler_config["api"]
    tg_config = scheduler_config["tg"]
    plugin_config = scheduler_config["plugin"]

    api_configs = [
        config
        for config in read_all_api_configs_from_db()
        if config.get("is_enabled", False)
    ]
    api_configs.sort(key=lambda config: config.get("response_time_ms") or 9999)
    api_configs = replace_keyword_in_config(api_configs, "[[keyword]]", keyword)

    tg_channels = get_enabled_channel_names() if tg_config.get("enabled", True) else []
    tg_workers = min(max(int(tg_config.get("max_workers", 4)), 1), len(tg_channels))
    tg_timeout = max(int(tg_config.get("timeout", 10)), 1)
    tg_proxy = tg_config.get("proxy") or None

    plugins = plugin_manager.get_enabled_plugins()

    executors = []
    future_types = {}
    future_deadlines = {}
    try:
        if api_configs:
            api_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=min(api_config["max_workers"], len(api_configs)), thread_name_prefix="api-search"
            )
            executors.append(api_executor)
            for config in api_configs:
                future_types[api_executor.submit(process_config, config, keyword, api_config["timeout"])] = "API"

        if tg_channels:
            tg_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=tg_workers, thread_name_prefix="tg-search"
            )
            executors.append(tg_executor)
            for channel in tg_channels:
                future_types[
                    tg_executor.submit(
                        search_telegram_channel,
                        keyword,
                        channel,
                        proxy=tg_proxy,
                        timeout=tg_timeout,
                    )
                ] = f"Telegram @{channel}"

        if plugins:
            plugin_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=min(plugin_config["max_workers"], len(plugins)), thread_name_prefix="plugin-search"
            )
            executors.append(plugin_executor)
            for plugin in plugins:
                future = plugin_executor.submit(_search_plugin, plugin, keyword)
                future_types[future] = f"插件 {plugin.name}"
                future_deadlines[future] = time.monotonic() + plugin_config["timeout"]

        pending = set(future_types)
        while pending:
            expired = [future for future in pending if future_deadlines.get(future, float("inf")) <= time.monotonic()]
            for future in expired:
                pending.remove(future)
                future.cancel()
                logger.warning("%s 搜索超时（限制：%ss）", future_types[future], plugin_config["timeout"])
            if not pending:
                break
            next_deadline = min((future_deadlines.get(future, float("inf")) for future in pending), default=float("inf"))
            done, pending = concurrent.futures.wait(
                pending,
                timeout=None if next_deadline == float("inf") else max(next_deadline - time.monotonic(), 0),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                source_name = future_types[future]
                try:
                    yield future.result()
                except Exception as error:
                    logger.error("%s 搜索任务异常: %s", source_name, error)
    finally:
        for executor in executors:
            executor.shutdown(wait=False, cancel_futures=True)


def search_in_database(keyword):
    """
    从内部数据库搜索，并新增网盘信息。
    返回格式: [SearchResultItem, ...]
    """
    try:
        # 从数据库搜索资源
        results = search_resources_by_title_terms(parse_search_terms(keyword))

        final_results = []
        for row in results:
            name = str(row[0]) if len(row) > 0 else ""
            link = str(row[1]) if len(row) > 1 else ""
            cloud_name = str(row[2]) if len(row) > 2 and row[2] else ""
            created_at = str(row[3]) if len(row) > 3 and row[3] else None
            netdisk_name = cloud_name if cloud_name else match_netdisk_link(link)
            final_results.append(
                SearchResultItem(
                    source="hot",
                    title=name,
                    share_link=link,
                    cloud_name=netdisk_name,
                    datetime=created_at,
                )
            )

        num_results = len(final_results)
        log_message = f"内部数据库搜索到 {num_results} 条资源。"
        if num_results > 0:
            sample_results = [res[1] for res in final_results[:2]]
            log_message += f" 示例 (Title): {sample_results}"

        logger.info(log_message)

        return final_results

    except Exception as err:
        logger.error(f"数据库错误: {err}")
        return []


def generate_search_stream_events(
    keyword: str,
    client_ip: Optional[str] = None,
    action: str = "search.web",
    apply_frontend_filter: Optional[bool] = None,
    limit: Optional[int] = None,
    target_clouds: Optional[Union[List[str], Set[str]]] = None,
    scope: str = "all",
):
    """
    生成搜索结果的 SSE 事件流 (生成字符串, 不直接返回 Response)
    :param keyword: 搜索关键词
    :param client_ip: 客户端 IP (可选)
    :param action: 行为标识 (默认为 search.web, API v1 流为 search.api.v1)
    :param apply_frontend_filter: 是否应用 Web 前端网盘显示过滤配置。若未指定，仅对 search.web 默认开启
    :param limit: 条数限制 (达成即触发自动阻断)
    :param target_clouds: 过滤特定网盘类型
    :param scope: 'own' (私有库) 或 'all' (全网)
    """
    keyword = str(keyword or "").strip()
    if not client_ip:
        client_ip = get_current_client_ip()

    should_apply_frontend_filter = (
        apply_frontend_filter if apply_frontend_filter is not None
        else (action == "search.web")
    )

    def _event_generator():
        start_time = time.time()
        if not keyword:
            record_log(
                log_type="search",
                action=action,
                query_text="",
                status_code=400,
                error_message="缺少搜索关键词",
                duration_ms=0,
                result_count=0,
                client_ip=client_ip,
            )
            yield json.dumps({"type": "error", "message": "请提供有效的搜索关键词"})
            return

        is_blocked, matched_word = check_input_keyword(keyword)
        if is_blocked:
            record_log(
                log_type="search",
                action=action,
                query_text=keyword,
                status_code=400,
                error_message=f"触发敏感词拦截: {matched_word}",
                duration_ms=int((time.time() - start_time) * 1000),
                result_count=0,
                client_ip=client_ip,
            )
            yield json.dumps({"type": "error", "message": f"搜索关键词包含敏感词汇 '{matched_word}'，已禁止搜索"}, ensure_ascii=False)
            return

        def _serialize_items(items):
            return [
                item.to_list() if isinstance(item, SearchResultItem) else list(item)
                for item in items
            ]

        # 1. 优先检查高频词内存缓存
        cached_items = get_cached_search_items(keyword)
        if cached_items is not None:
            logger.info(f"关键词 '{keyword}' 流式搜索击中内存缓存 ({len(cached_items)} 条)。")
            cached_items = filter_results_by_title(filter_search_results(cached_items), keyword)
            if should_apply_frontend_filter:
                cached_items = filter_results_by_frontend_netdisks(cached_items)
            if target_clouds:
                cached_items = _filter_results_by_cloud_name(cached_items, target_clouds)
            if limit and limit > 0:
                cached_items = cached_items[:limit]
            duration_ms = int((time.time() - start_time) * 1000)
            record_log(
                log_type="search",
                action=f"{action}.cache",
                query_text=keyword,
                status_code=200,
                duration_ms=duration_ms,
                result_count=len(cached_items),
                client_ip=client_ip,
            )
            yield json.dumps({"type": "complete", "results": _serialize_items(cached_items)})
            return

        seen_items_map: Dict[str, SearchResultItem] = {}

        def _dedupe_stream_chunk(items):
            unique_items = []
            for item in items:
                try:
                    typed = SearchResultItem.from_item(item)
                except Exception:
                    continue
                url = (typed.share_link or "").strip()
                if not url:
                    continue
                key = extract_canonical_resource_key(url) or f"url:{url}"
                if key not in seen_items_map:
                    seen_items_map[key] = typed
                    unique_items.append(typed)
                else:
                    existing_item = seen_items_map[key]
                    better_item = merge_or_select_better(existing_item, typed)
                    existing_pwd = existing_item.password or extract_password_from_url(existing_item.share_link)
                    better_pwd = better_item.password or extract_password_from_url(better_item.share_link)
                    has_new_pwd = bool(better_pwd and not existing_pwd)
                    has_higher_score = calculate_completeness_score(better_item) > calculate_completeness_score(existing_item)

                    if has_new_pwd or has_higher_score:
                        seen_items_map[key] = better_item
                        unique_items.append(better_item)
            return unique_items

        db_results = search_in_database(keyword)
        if should_apply_frontend_filter:
            db_results = filter_results_by_frontend_netdisks(db_results)
        if target_clouds:
            db_results = _filter_results_by_cloud_name(db_results, target_clouds)
        db_results = filter_results_by_title(filter_search_results(db_results), keyword)
        db_results = _dedupe_stream_chunk(db_results)
        if db_results:
            yield json.dumps({"type": "initial", "results": _serialize_items(db_results)})

        if scope != "own":
            for results in iter_upstream_search_results(keyword):
                if should_apply_frontend_filter:
                    results = filter_results_by_frontend_netdisks(results)
                if target_clouds:
                    results = _filter_results_by_cloud_name(results, target_clouds)
                results = filter_results_by_title(filter_search_results(results), keyword)
                results = _dedupe_stream_chunk(results)
                if results:
                    yield json.dumps({"type": "update", "results": _serialize_items(results)})

                if limit and limit > 0 and len(seen_items_map) >= limit:
                    logger.info("流式聚合搜索满足限额 limit=%d (已查获 %d 条)，自动触发阻断中断后续源。", limit, len(seen_items_map))
                    break

        # 搜索完成，将所有去重并排序后的最终结果加入 TTL 缓存
        final_stream_items = sort_search_results(list(seen_items_map.values()), keyword=keyword)
        if limit and limit > 0:
            final_stream_items = final_stream_items[:limit]

        if final_stream_items:
            set_cached_search_items(keyword, final_stream_items)

        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="search",
            action=action,
            query_text=keyword,
            status_code=200,
            duration_ms=duration_ms,
            result_count=len(final_stream_items),
            client_ip=client_ip,
        )
        logger.info(f"关键词 '{keyword}' 所有流式搜索完成，共 {len(final_stream_items)} 条。")
        yield json.dumps({"type": "complete", "results": _serialize_items(final_stream_items)})

    return _event_generator()


QUALITY_KEYWORDS = ["合集", "系列", "全集", "全", "完结", "完", "4k", "2160p", "1080p", "高清", "原盘", "最新"]


def calculate_completeness_score(item: SearchResultItem) -> int:
    """
    计算搜索结果的完整度与质量得分：
    - 内部库收益源 (hot) 拥有绝对最高权重 (+1000)
    - 拥有提取码/密码优先 (+100)
    - 标题包含 4K/全集/完结等高质量关键词加分 (+15 each)
    - 标题长度与详细程度加分 (最大 +50)
    - 网盘平台成功识别加分 (+10)
    """
    score = 0

    # 1. 数据来源权重 (hot 收益盘优先)
    if item.source == "hot":
        score += 1000
    elif item.source == "tg":
        score += 50
    else:
        score += 30

    # 2. 密码提取码存在加分
    pwd = item.password or extract_password_from_url(item.share_link)
    if pwd:
        score += 100

    # 3. 关键词质量分
    title_lower = (item.title or "").lower()
    for kw in QUALITY_KEYWORDS:
        if kw in title_lower:
            score += 15

    # 4. 标题详细度分（惩罚通用占位标题）
    if item.title and item.title != "Telegram 频道资源":
        score += min(len(item.title), 50)
    else:
        score -= 50

    # 5. 网盘有效识别分
    if item.cloud_name and item.cloud_name != "其他":
        score += 10

    return score


def merge_or_select_better(existing: SearchResultItem, incoming: SearchResultItem) -> SearchResultItem:
    """
    当两条记录指向相同网盘真实资源时，择优合并：
    1. 选择得分更高者作为基础信息
    2. 继承并补全提取码密码，防止有效密码丢失
    """
    existing_pwd = existing.password or extract_password_from_url(existing.share_link)
    incoming_pwd = incoming.password or extract_password_from_url(incoming.share_link)
    best_pwd = existing_pwd or incoming_pwd

    existing_score = calculate_completeness_score(existing)
    incoming_score = calculate_completeness_score(incoming)

    chosen = existing if existing_score >= incoming_score else incoming

    # 确保密码保留在选出的对象上
    if best_pwd:
        if not chosen.password:
            chosen.password = best_pwd
        # 若原链接中缺少 pwd 参数，可适度拼接以保持链接直达
        if "pwd=" not in chosen.share_link and "password=" not in chosen.share_link:
            sep = "&" if "?" in chosen.share_link else "?"
            param = "password" if "115" in chosen.share_link else "pwd"
            chosen.share_link = f"{chosen.share_link}{sep}{param}={best_pwd}"

    return chosen


def dedupe_search_results(results):
    """
    对搜索结果进行精准去重与择优合并：
    - 基于网盘平台真实唯一键 (如 quark:xxx, baidu:yyy) 去重
    - 允许同名但不同资源链接并存 (彻底修复粗暴以 title|hostname 导致同名不同链被误删的问题)
    - 相同真实资源出现多次时，按完整度得分择优保留最完整、带提取码的版本
    - 保持列表初始出现顺序
    """
    if not results:
        return []

    deduped_map = {}
    order = []

    for item in results:
        if not item:
            continue
        try:
            typed_item = SearchResultItem.from_item(item)
        except Exception:
            continue

        url = (typed_item.share_link or "").strip()
        if not url:
            continue

        key = extract_canonical_resource_key(url)
        if not key:
            key = f"url:{url}"

        if key not in deduped_map:
            deduped_map[key] = typed_item
            order.append(key)
        else:
            existing_item = deduped_map[key]
            better_item = merge_or_select_better(existing_item, typed_item)
            deduped_map[key] = better_item

    return [deduped_map[k] for k in order]


# --- 智能多维综合评分与排序 (对齐 pansou) ---

def calculate_time_score(dt_str: Optional[str], title: str = "") -> float:
    """
    计算时间时效得分（最高 500 分）：
    - 1天内: 500
    - 3天内: 400
    - 7天内: 300
    - 30天内: 200
    - 90天内: 100
    - 1年内: 50
    - 1年以上: 20
    - 无时间信息但标题包含当年年份(如 2026/2025): +60 分兜底
    """
    if not dt_str:
        curr_year = time.strftime("%Y")
        if curr_year in (title or ""):
            return 80.0
        prev_year = str(int(curr_year) - 1)
        if prev_year in (title or ""):
            return 50.0
        return 0.0

    try:
        from datetime import datetime
        dt_clean = str(dt_str).replace("Z", "+00:00").split(".")[0]
        dt_clean = dt_clean.replace("T", " ")
        parsed_dt = datetime.strptime(dt_clean[:19], "%Y-%m-%d %H:%M:%S")
        days_diff = (datetime.now() - parsed_dt).total_seconds() / 86400.0

        if days_diff <= 1:
            return 500.0
        elif days_diff <= 3:
            return 400.0
        elif days_diff <= 7:
            return 300.0
        elif days_diff <= 30:
            return 200.0
        elif days_diff <= 90:
            return 100.0
        elif days_diff <= 365:
            return 50.0
        else:
            return 20.0
    except Exception:
        return 0.0


KEYWORD_RANK_WEIGHTS = [
    ("合集", 420),
    ("系列", 350),
    ("全集", 280),
    ("全", 280),
    ("完结", 210),
    ("完", 210),
    ("4k", 180),
    ("2160p", 180),
    ("原盘", 180),
    ("最新", 140),
    ("1080p", 140),
    ("高清", 140),
    ("国粤双语", 70),
    ("附", 70),
]


def calculate_keyword_score(title: str) -> float:
    if not title:
        return 0.0
    title_lower = title.lower()
    score = 0.0
    matched = set()

    for kw, weight in KEYWORD_RANK_WEIGHTS:
        if kw in title_lower and kw not in matched:
            score += weight
            matched.add(kw)
            if len(matched) >= 3:
                break
    return min(score, 600.0)


def calculate_relevance_score(title: str, keyword: str) -> float:
    if not title or not keyword:
        return 0.0
    t_clean = title.strip().casefold()
    terms = parse_search_terms(keyword)
    if len(terms) > 1:
        return float(len(get_title_matched_terms(title, keyword)) * 100)

    k_clean = terms[0].casefold() if terms else ""

    if t_clean == k_clean:
        return 300.0
    if t_clean.startswith(k_clean):
        return 150.0
    if k_clean in t_clean:
        return 80.0
    return 0.0


def calculate_rank_score(item: SearchResultItem, keyword: str = "") -> float:
    """
    计算综合排名得分：
    总分 = 数据源层级分 + 关键词分 + 时效分 + 提取码分 + 标题相关度分
    """
    score = 0.0

    # 1. 数据源层级分 (hot 自有收益盘绝对优先，已注册插件结合其 priority 动态计分)
    if item.source == "hot":
        score += 1000.0
    elif item.source == "tg":
        score += 150.0
    elif item.source:
        plugin_name = item.source.split(":", 1)[1] if item.source.startswith("plugin:") else item.source
        plugin_obj = plugin_manager.get_plugin(plugin_name)
        if plugin_obj:
            score += float(getattr(plugin_obj, "priority", 100)) * 0.5
        else:
            score += 50.0
    else:
        score += 50.0

    # 2. 特征关键词分
    score += calculate_keyword_score(item.title)

    # 3. 时效新鲜度分
    score += calculate_time_score(item.datetime, item.title)

    # 4. 提取码与完整度分
    pwd = item.password or extract_password_from_url(item.share_link)
    if pwd:
        score += 100.0

    if item.cloud_name and item.cloud_name != "其他":
        score += 20.0

    if not item.title or item.title == "Telegram 频道资源":
        score -= 300.0

    # 5. 搜索词相关度分
    if keyword:
        score += calculate_relevance_score(item.title, keyword)

    return score


def sort_search_results(results: List[SearchResultItem], keyword: str = "") -> List[SearchResultItem]:
    """
    按照综合得分对结果降序排序（稳定排序）
    """
    if not results:
        return []

    scored = []
    for item in results:
        typed = SearchResultItem.from_item(item) if not isinstance(item, SearchResultItem) else item
        s = calculate_rank_score(typed, keyword=keyword)
        matched_term_count = len(get_title_matched_terms(typed.title, keyword))
        scored.append((matched_term_count, s, typed))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item for _, _, item in scored]


def _filter_results_by_cloud_name(results, cloud_name=""):
    """按网盘名称筛选聚合搜索结果；支持单个网盘名称、逗号分隔或集合/列表；空值表示不过滤。"""
    target_clouds = parse_netdisk_names(cloud_name)
    if not target_clouds:
        return results

    return [
        item
        for item in results
        if SearchResultItem.from_item(item).cloud_name in target_clouds
    ]


def search_public_resources(keyword="", limit=100, cloud_name=""):
    start_time = time.time()
    keyword = (keyword or "").strip()
    target_clouds = parse_netdisk_names(cloud_name)
    cloud_display = ",".join(sorted(target_clouds)) if target_clouds else ""
    query_display = f"{keyword} [cloud={cloud_display}]" if cloud_display else keyword

    if not keyword:
        record_log(
            log_type="search",
            action="search.api",
            query_text=query_display,
            status_code=400,
            error_message="缺少搜索关键词",
            duration_ms=0,
            result_count=0,
        )
        return False, "请提供搜索关键词", []

    is_blocked, matched_word = check_input_keyword(keyword)
    if is_blocked:
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="search",
            action="search.api",
            query_text=query_display,
            status_code=400,
            error_message=f"触发敏感词拦截: {matched_word}",
            duration_ms=duration_ms,
            result_count=0,
        )
        return False, f"搜索关键词包含敏感词汇 '{matched_word}'，已禁止搜索", []

    cached_items = get_cached_search_items(keyword)
    if cached_items is not None:
        logger.info(f"关键词 '{keyword}' 聚合搜索击中内存缓存 ({len(cached_items)} 条)。")
        filtered_cached = filter_results_by_title(filter_search_results(cached_items), keyword)
        filtered_cached = _filter_results_by_cloud_name(filtered_cached, target_clouds)
        limited_cached = filtered_cached[: max(limit, 1)]
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="search",
            action="search.api.cache",
            query_text=query_display,
            status_code=200,
            duration_ms=duration_ms,
            result_count=len(limited_cached),
        )
        return True, "聚合搜索成功 (缓存)", [item.to_dict() for item in limited_cached]

    aggregated_results = []

    db_results = search_in_database(keyword)
    aggregated_results.extend(db_results)

    # 1. 检查数据库结果是否已直接满足 limit 需求
    filtered_db = filter_results_by_title(filter_search_results(db_results), keyword)
    filtered_db = _filter_results_by_cloud_name(filtered_db, target_clouds)
    deduped_db = dedupe_search_results(filtered_db)
    if limit and len(deduped_db) >= limit:
        logger.info("聚合搜索在数据库层已满足 limit=%d (找到 %d 条)，自动阻断后续上游网络开销", limit, len(deduped_db))
        sorted_results = sort_search_results(deduped_db, keyword=keyword)
        set_cached_search_items(keyword, sorted_results)
        limited_results = sorted_results[: max(limit, 1)]
        duration_ms = int((time.time() - start_time) * 1000)
        record_log(
            log_type="search",
            action="search.api",
            query_text=query_display,
            status_code=200,
            duration_ms=duration_ms,
            result_count=len(limited_results),
        )
        return True, "聚合搜索成功", [
            item.to_dict() if isinstance(item, SearchResultItem) else item
            for item in limited_results
        ]

    # 2. 逐个接收上游数据源，只要去重后的符合条件结果数达到 limit，立即自动 break 退出（取消后续所有请求）
    for results in iter_upstream_search_results(keyword):
        if results:
            aggregated_results.extend(results)
            if limit and limit > 0:
                temp_filtered = filter_results_by_title(filter_search_results(aggregated_results), keyword)
                temp_filtered = _filter_results_by_cloud_name(temp_filtered, target_clouds)
                temp_deduped = dedupe_search_results(temp_filtered)
                if len(temp_deduped) >= limit:
                    logger.info("聚合搜索累计数据已达限额 limit=%d (满足 %d 条)，自动阻断中断后续上游请求。", limit, len(temp_deduped))
                    break

    # 敏感词过滤、去重与排序
    aggregated_results = filter_results_by_title(filter_search_results(aggregated_results), keyword)
    deduped_results = dedupe_search_results(aggregated_results)
    sorted_results = sort_search_results(deduped_results, keyword=keyword)
    if sorted_results:
        set_cached_search_items(keyword, sorted_results)

    filtered_results = _filter_results_by_cloud_name(sorted_results, target_clouds)
    limited_results = filtered_results[: max(limit, 1)]

    duration_ms = int((time.time() - start_time) * 1000)
    record_log(
        log_type="search",
        action="search.api",
        query_text=query_display,
        status_code=200,
        duration_ms=duration_ms,
        result_count=len(limited_results),
    )

    return True, "聚合搜索成功", [
        item.to_dict()
        if isinstance(item, SearchResultItem)
        else {
            "source": item[0],
            "name": item[1],
            "share_link": item[2],
            "cloud_name": item[3],
        }
        for item in limited_results
    ]


def search_resources(name="", cloud_name="", resource_type="", limit=100, sort="default"):
    """
    通过名称、云名称或类型搜索资源
    返回: (success: bool, message: str, results: list)
    """
    try:
        success, message, results = search_resources_advanced(
            name=name,
            cloud_name=cloud_name,
            resource_type=resource_type,
            limit=limit,
            sort=sort,
        )
        if not success:
            return success, message, results

        return True, message, results
    except Exception as e:
        logger.error(f"API错误: {e}")
        return False, f"API错误: {e}", []
