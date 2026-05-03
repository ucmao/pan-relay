import concurrent.futures
import json
import logging
import random
import re
import time
from urllib.parse import urlparse

import jmespath
import requests

from configs.app_config import user_agents
from src.db.resources_dao import search_resources_by_keyword, search_resources_advanced
from src.services.system_config_service import get_allowed_frontend_netdisks
from utils.netdisk_utils import match_netdisk_link

logger = logging.getLogger(__name__)


def filter_results_by_frontend_netdisks(results):
    """按后台配置过滤前端可见网盘。"""
    allowed_netdisks = get_allowed_frontend_netdisks()
    if not allowed_netdisks:
        return results

    filtered_results = []
    for item in results:
        if isinstance(item, (list, tuple)) and len(item) >= 4:
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
    from src.db.api_config_dao import get_all_configs
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

        cleaned_data.append([source, title, url, netdisk_name])

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
    返回格式: [[source, title, url, netdisk_name], ...]
    """
    try:
        # 使用 DAO 搜索资源
        results = search_resources_by_keyword(keyword)

        final_results = []
        for name, link, cloud_name in results:
            netdisk_name = cloud_name if cloud_name else match_netdisk_link(link)
            final_results.append(["hot", name, link, netdisk_name])

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
        db_results = search_in_database(keyword)
        db_results = filter_results_by_frontend_netdisks(db_results)
        if db_results:
            yield json.dumps({"type": "initial", "results": db_results})

        urls_config = read_all_api_configs_from_db()
        enabled_configs = [c for c in urls_config if c.get("status", False) and c.get("is_enabled", False)]

        enabled_configs.sort(key=lambda x: x.get("response_time_ms", 9999))

        enabled_urls = [c["url"] for c in enabled_configs]
        logger.info(f"本次搜索启用的 API 数量: {len(enabled_urls)} 个。")
        logger.info(f"启用的 API URL 列表: {enabled_urls}")

        urls_config_search = replace_keyword_in_config(enabled_configs, "[[keyword]]", keyword)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_config, config, keyword) for config in urls_config_search]
            pending_futures = set(futures)

            while pending_futures:
                done, pending_futures = concurrent.futures.wait(
                    pending_futures, timeout=None, return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    try:
                        results = future.result()
                        results = filter_results_by_frontend_netdisks(results)
                        if results:
                            yield json.dumps({"type": "update", "results": results})
                    except Exception as e:
                        logger.error(f"SSE 收集结果时发生异常: {e}")

                time.sleep(0.01)

        logger.info(f"关键词 '{keyword}' 所有流式搜索完成。")
        yield json.dumps({"type": "end"})

    return _event_generator()


def dedupe_search_results(results):
    deduped = []
    seen = set()

    for item in results:
        if not isinstance(item, (list, tuple)) or len(item) < 4:
            continue

        title = str(item[1]).strip()
        url = str(item[2]).strip()
        hostname = url

        try:
            parsed = urlparse(url)
            if parsed.hostname:
                hostname = parsed.hostname
        except Exception:
            hostname = url

        key = f"{title}|{hostname}"
        if key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped


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

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_config, config, keyword) for config in urls_config_search]
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
        {
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
