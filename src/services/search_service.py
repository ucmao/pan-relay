import concurrent.futures
import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import jmespath
import requests

from src.configs.app_config import user_agents
from src.db.resources import search_resources_by_keyword, search_resources_advanced
from src.models.search_item import SearchResultItem
from src.services.plugin_manager import plugin_manager
from src.services.sensitive_word_service import check_input_keyword, filter_search_results
from src.services.system_config_service import get_allowed_frontend_netdisks
from src.services.telegram_search_service import search_telegram_resources
from src.utils.netdisk_utils import (
    match_netdisk_link,
    extract_canonical_resource_key,
    extract_password_from_url,
)

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


def filter_output(extracted_data, keyword):
    """根据关键词过滤结果，实现模糊匹配。"""
    separator_pattern = r"[,、|;+\-/	\n*#\s]"
    processed_keyword = re.sub(separator_pattern, " ", keyword)

    keyword_list = [kw.strip() for kw in processed_keyword.split() if kw.strip()]

    filtered_list = []

    for item in extracted_data:
        title = item[0]

        for kw in keyword_list:
            if kw in title:
                filtered_list.append(item)
                break

    return filtered_list


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


def process_config(config, keyword):
    """
    处理单个 API 配置，获取、筛选数据，并返回包含网盘名称的结果。
    """
    config_name = config.get("name", "未知 API")
    final_results = []

    try:
        response_data = fetch_data(config["url"], config["method"], config["request"], timeout=10)

        if response_data:
            extracted_data = extract_from_json(response_data, config["response"])

            if extracted_data and isinstance(extracted_data, list):
                filtered_data = filter_output(extracted_data, keyword)

                if filtered_data:
                    filtered_data_with_keyword = [["other", item[0], item[1]] for item in filtered_data]
                    final_results = clean_and_extract_data(filtered_data_with_keyword)

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


def search_in_database(keyword):
    """
    从内部数据库搜索，并新增网盘信息。
    返回格式: [SearchResultItem, ...]
    """
    try:
        # 从数据库搜索资源
        results = search_resources_by_keyword(keyword)

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


def generate_search_stream_events(keyword):
    """
    生成搜索结果的 SSE 事件流 (生成字符串, 不直接返回 Response)
    """
    keyword = str(keyword or "").strip()

    def _event_generator():
        if not keyword:
            yield json.dumps({"type": "error", "message": "请提供有效的搜索关键词"})
            return

        is_blocked, matched_word = check_input_keyword(keyword)
        if is_blocked:
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
            cached_items = filter_search_results(cached_items)
            if cached_items:
                yield json.dumps({"type": "initial", "results": _serialize_items(cached_items)})
            yield json.dumps({"type": "end"})
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
        db_results = filter_results_by_frontend_netdisks(db_results)
        db_results = filter_search_results(db_results)
        db_results = _dedupe_stream_chunk(db_results)
        if db_results:
            yield json.dumps({"type": "initial", "results": _serialize_items(db_results)})

        urls_config = read_all_api_configs_from_db()
        enabled_configs = [c for c in urls_config if c.get("is_enabled", False)]

        enabled_configs.sort(key=lambda x: x.get("response_time_ms") or 9999)

        enabled_urls = [c["url"] for c in enabled_configs]
        logger.info(f"本次搜索启用的 API 数量: {len(enabled_urls)} 个。")
        logger.info(f"启用的 API URL 列表: {enabled_urls}")

        urls_config_search = replace_keyword_in_config(enabled_configs, "[[keyword]]", keyword)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(process_config, config, keyword) for config in urls_config_search]
            futures.append(executor.submit(search_telegram_resources, keyword))
            futures.append(executor.submit(plugin_manager.search_all, keyword))
            pending_futures = set(futures)

            while pending_futures:
                done, pending_futures = concurrent.futures.wait(
                    pending_futures, timeout=None, return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    try:
                        results = future.result()
                        results = filter_results_by_frontend_netdisks(results)
                        results = filter_search_results(results)
                        results = _dedupe_stream_chunk(results)
                        if results:
                            yield json.dumps({"type": "update", "results": _serialize_items(results)})
                    except Exception as e:
                        logger.error(f"SSE 收集结果时发生异常: {e}")

                time.sleep(0.01)

        # 搜索完成，将所有去重并排序后的最终结果加入 TTL 缓存
        final_stream_items = sort_search_results(list(seen_items_map.values()), keyword=keyword)
        if final_stream_items:
            set_cached_search_items(keyword, final_stream_items)

        logger.info(f"关键词 '{keyword}' 所有流式搜索完成，共 {len(final_stream_items)} 条。")
        yield json.dumps({"type": "end"})

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
    t_clean = title.strip().lower()
    k_clean = keyword.strip().lower()

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
        scored.append((s, typed))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


def search_public_resources(keyword="", limit=100):
    keyword = (keyword or "").strip()
    if not keyword:
        return False, "请提供搜索关键词", []

    is_blocked, matched_word = check_input_keyword(keyword)
    if is_blocked:
        return False, f"搜索关键词包含敏感词汇 '{matched_word}'，已禁止搜索", []

    cached_items = get_cached_search_items(keyword)
    if cached_items is not None:
        logger.info(f"关键词 '{keyword}' 聚合搜索击中内存缓存 ({len(cached_items)} 条)。")
        filtered_cached = filter_search_results(cached_items)
        limited_cached = filtered_cached[: max(limit, 1)]
        return True, "聚合搜索成功 (缓存)", [item.to_dict() for item in limited_cached]

    aggregated_results = []

    db_results = search_in_database(keyword)
    aggregated_results.extend(filter_results_by_frontend_netdisks(db_results))

    urls_config = read_all_api_configs_from_db()
    enabled_configs = [c for c in urls_config if c.get("status", False) and c.get("is_enabled", False)]
    enabled_configs.sort(key=lambda x: x.get("response_time_ms", 9999))
    urls_config_search = replace_keyword_in_config(enabled_configs, "[[keyword]]", keyword)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_config, config, keyword) for config in urls_config_search]
        futures.append(executor.submit(search_telegram_resources, keyword))
        futures.append(executor.submit(plugin_manager.search_all, keyword))
        for future in concurrent.futures.as_completed(futures):
            try:
                results = future.result()
                if results:
                    aggregated_results.extend(filter_results_by_frontend_netdisks(results))
            except Exception as err:
                logger.error(f"公开聚合接口收集结果时发生异常: {err}")

    # 敏感词过滤、去重与排序
    aggregated_results = filter_search_results(aggregated_results)
    deduped_results = dedupe_search_results(aggregated_results)
    sorted_results = sort_search_results(deduped_results, keyword=keyword)
    if sorted_results:
        set_cached_search_items(keyword, sorted_results)

    limited_results = sorted_results[: max(limit, 1)]

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

        return True, message, filter_results_by_frontend_netdisks(results)
    except Exception as e:
        logger.error(f"API错误: {e}")
        return False, f"API错误: {e}", []
