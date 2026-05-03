import json
import time
import logging
import concurrent.futures

import jmespath
import requests

from src.db.api_config_dao import (
    get_all_configs,
    get_config_by_id,
    get_config_status,
    insert_config,
    copy_config,
    update_config,
    delete_config,
    update_status,
    update_enabled_status,
    set_enabled,
    enable_all_normal,
    disable_all,
)

logger = logging.getLogger(__name__)


def read_api_configs_from_db():
    """从数据库中读取所有 API 配置，包括新的字段"""
    return get_all_configs(order_by_created=True)


def get_api_status_from_db(api_id):
    """从数据库中获取单个 API 的 status 和 is_enabled 状态"""
    return get_config_status(api_id)


def update_api_status_in_db(api_id, new_status, response_time_ms=0):
    """更新 API 配置的状态和响应时间 (不修改 is_enabled)"""
    update_status(api_id, new_status, response_time_ms)


def update_api_enabled_status_in_db(api_id, is_enabled, new_status=None, response_time_ms=None):
    """
    更新 API 配置的启用状态，可同时更新 status 和 response_time_ms。
    用于测试失败后，强制禁用 API。
    """
    update_enabled_status(api_id, is_enabled, new_status, response_time_ms)


def extract_from_json(json_data, rule):
    """从 JSON 字符串中提取数据"""
    if json_data is None:
        return None
    try:
        data = json.loads(json_data)
        result = jmespath.search(rule, data)
        return result
    except Exception:
        return None


def add_api_config_to_db(new_config):
    """向数据库中添加一条 API 配置记录"""
    return insert_config(new_config)


def copy_api_config_in_db(api_id):
    """在数据库中复制一条 API 配置记录"""
    return copy_config(api_id)


def update_api_config_in_db(api_id, updated_config):
    """更新一条 API 配置记录"""
    return update_config(api_id, updated_config)


def delete_api_config_in_db(api_id):
    """删除一条 API 配置记录"""
    return delete_config(api_id)


def set_api_enabled_in_db(api_id, is_enabled):
    """切换单个 API 的启用状态，限制异常状态下启用"""
    return set_enabled(api_id, is_enabled)


def enable_all_apis_in_db():
    """一键启用所有【状态正常 (status=1)】的 API"""
    return enable_all_normal()


def disable_all_apis_in_db():
    """一键禁用所有 API"""
    return disable_all()


def update_config_with_keyword(config, placeholder, keyword):
    """ 用实际关键词更新 API 配置中的占位符'[[keyword]]' """
    placeholder = str(placeholder)
    keyword = str(keyword)
    # 创建配置的副本
    new_config = config.copy()
    # 替换 URL
    if "url" in new_config and isinstance(new_config["url"], str):
        new_config["url"] = new_config["url"].replace(placeholder, keyword)
    # 替换 Request Body (JSON 字符串)
    if "request" in new_config and isinstance(new_config["request"], str):
        new_config["request"] = new_config["request"].replace(placeholder, keyword)

    return new_config


def test_single_api(api_id, api_config=None, update_status=False):
    """测试单个 API 并更新数据库状态、响应时间和is_enabled"""
    if api_config is None:
        api_config = get_config_by_id(api_id)
        if not api_config:
            logger.error(f"测试 API ID:{api_id} 失败: API 配置不存在")
            return "未知 URL", False, None, False, 0

    # 使用传入的api_id参数，确保是字符串或整数类型
    if isinstance(api_id, dict):
        api_id = api_id.get("id", "未知ID")
    api_id = str(api_id)
    url = api_config.get("url", "未知 URL")

    # 检查 is_enabled 状态 (仅用于日志和跳过，测试路由不应跳过已禁用的)
    if not api_config.get("is_enabled", True):
        logger.info(f"API {url} (ID:{api_id}) 当前处于禁用状态，但仍执行测试。")

    start_time = time.time()
    response_time_ms = 0
    new_status = False  # 默认失败

    try:
        method = api_config["method"].lower()
        request_body = api_config.get("request", "{}")
        response_rule = api_config.get("response", "{}")

        # 执行请求 (代码逻辑与之前保持一致)
        if method == "get":
            try:
                request_params = json.loads(request_body)
                response = requests.get(url, params=request_params, verify=False, timeout=5)
            except json.JSONDecodeError:
                response = requests.get(url, verify=False, timeout=5)
        elif method == "post":
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, data=request_body, headers=headers, verify=False, timeout=5)
        else:
            logger.warning(f"API {url} (ID:{api_id}) 不支持的 HTTP 方法: {method}，更新状态为不可用")
            # **核心修改：测试失败，强制禁止**
            if api_id != "未知ID" and api_id.isdigit():
                update_api_enabled_status_in_db(api_id, is_enabled=False, new_status=False, response_time_ms=0)
            return url, False, response.status_code if "response" in locals() else None, False, 0

        # 计算响应时间（毫秒）
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)

        # 检查响应状态码和规则匹配
        response_rule_status = bool(extract_from_json(response.text, response_rule))
        new_status = 200 <= response.status_code < 300 and response_rule_status

        if api_id != "未知ID" and api_id.isdigit():
            if new_status:
                # 正常情况：只更新 status 和 time
                update_api_status_in_db(api_id, new_status, response_time_ms)
            else:
                # **核心修改：测试失败，强制禁止 (is_enabled=False)**
                update_api_enabled_status_in_db(
                    api_id,
                    is_enabled=False,
                    new_status=False,
                    response_time_ms=response_time_ms,
                )
                logger.warning(f"API {url} (ID:{api_id}) 测试失败，已自动禁止。")

        logger.info(
            f"API {url} (ID:{api_id}) 测试完毕，状态码: {response.status_code}，耗时: {response_time_ms}ms，是否有效: {new_status}"
        )
        return url, new_status, response.status_code, response_rule_status, response_time_ms

    except Exception as e:
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        new_status = False
        if api_id != "未知ID" and api_id.isdigit():
            # **核心修改：测试失败，强制禁止 (is_enabled=False)**
            update_api_enabled_status_in_db(
                api_id,
                is_enabled=False,
                new_status=False,
                response_time_ms=response_time_ms,
            )
        logger.error(f"API {url} (ID:{api_id}) 测试出错: {e}，更新状态为不可用，并自动禁止。")
        return url, new_status, None, False, response_time_ms


def test_all_apis_and_update_status():
    """测试所有API配置并更新其状态"""
    api_configs = read_api_configs_from_db()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # 提交所有 API 配置进行测试
        futures = [executor.submit(test_single_api, config.get("id"), config) for config in api_configs]
        for _ in concurrent.futures.as_completed(futures):
            pass

    logger.info("所有 API 测试并更新状态完毕 (失败的 API 已自动禁止)")
    return True, "所有 API 测试并更新状态成功 (异常的已自动禁止)"

