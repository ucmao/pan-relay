import concurrent.futures
import json
import logging
import random
import re
import time
from urllib.parse import urlparse

import jmespath
import requests

from src.configs.app_config import user_agents
from src.db.resources import search_resources_by_keyword, search_resources_advanced
from src.models.search_item import SearchResultItem
from src.services.system_config_service import get_allowed_frontend_netdisks
from src.services.telegram_search_service import search_telegram_resources
from src.utils.netdisk_utils import (
    match_netdisk_link,
    extract_canonical_resource_key,
    extract_password_from_url,
)

logger = logging.getLogger(__name__)


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
        for name, link, cloud_name in results:
            netdisk_name = cloud_name if cloud_name else match_netdisk_link(link)
            final_results.append(
                SearchResultItem(source="hot", title=name, share_link=link, cloud_name=netdisk_name)
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

    def _event_generator():
        def _serialize_items(items):
            return [
                item.to_list() if isinstance(item, SearchResultItem) else list(item)
                for item in items
            ]

        seen_keys = set()

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
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                unique_items.append(typed)
            return unique_items

        db_results = search_in_database(keyword)
        db_results = filter_results_by_frontend_netdisks(db_results)
        db_results = _dedupe_stream_chunk(db_results)
        if db_results:
            yield json.dumps({"type": "initial", "results": _serialize_items(db_results)})

        urls_config = read_all_api_configs_from_db()
        enabled_configs = [c for c in urls_config if c.get("status", False) and c.get("is_enabled", False)]

        enabled_configs.sort(key=lambda x: x.get("response_time_ms", 9999))

        enabled_urls = [c["url"] for c in enabled_configs]
        logger.info(f"本次搜索启用的 API 数量: {len(enabled_urls)} 个。")
        logger.info(f"启用的 API URL 列表: {enabled_urls}")

        urls_config_search = replace_keyword_in_config(enabled_configs, "[[keyword]]", keyword)

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(process_config, config, keyword) for config in urls_config_search]
            futures.append(executor.submit(search_telegram_resources, keyword))
            pending_futures = set(futures)

            while pending_futures:
                done, pending_futures = concurrent.futures.wait(
                    pending_futures, timeout=None, return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    try:
                        results = future.result()
                        results = filter_results_by_frontend_netdisks(results)
                        results = _dedupe_stream_chunk(results)
                        if results:
                            yield json.dumps({"type": "update", "results": _serialize_items(results)})
                    except Exception as e:
                        logger.error(f"SSE 收集结果时发生异常: {e}")

                time.sleep(0.01)

        logger.info(f"关键词 '{keyword}' 所有流式搜索完成。")
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


def search_public_resources(keyword="", limit=100):
    keyword = (keyword or "").strip()
    if not keyword:
        return False, "请提供搜索关键词", []

    aggregated_results = []

    db_results = search_in_database(keyword)
    aggregated_results.extend(filter_results_by_frontend_netdisks(db_results))

    urls_config = read_all_api_configs_from_db()
    enabled_configs = [c for c in urls_config if c.get("status", False) and c.get("is_enabled", False)]
    enabled_configs.sort(key=lambda x: x.get("response_time_ms", 9999))
    urls_config_search = replace_keyword_in_config(enabled_configs, "[[keyword]]", keyword)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(process_config, config, keyword) for config in urls_config_search]
        futures.append(executor.submit(search_telegram_resources, keyword))
        for future in concurrent.futures.as_completed(futures):
            try:
                results = future.result()
                if results:
                    aggregated_results.extend(filter_results_by_frontend_netdisks(results))
            except Exception as err:
                logger.error(f"公开聚合接口收集结果时发生异常: {err}")

    deduped_results = dedupe_search_results(aggregated_results)
    limited_results = deduped_results[: max(limit, 1)]

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
