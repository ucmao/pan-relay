import json
import time
import logging
import concurrent.futures

import jmespath
import requests

from src.utils.test_keywords import build_test_keywords

from src.db.api_configs import (
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


def _response_indicates_no_data(response_text, extracted_data):
    """识别“请求成功但关键词无结果”，避免把它当成接口故障。"""
    if extracted_data == []:
        return True

    try:
        data = json.loads(response_text)
    except (TypeError, json.JSONDecodeError):
        return False

    no_data_markers = (
        "未找到",
        "无结果",
        "暂无",
        "没有找到",
        "没有相关",
        "no data",
        "not found",
        "no result",
    )

    def contains_marker(value):
        if isinstance(value, dict):
            return any(contains_marker(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_marker(item) for item in value)
        if isinstance(value, str):
            lowered = value.lower()
            return any(marker in lowered for marker in no_data_markers)
        return False

    return extracted_data is None and contains_marker(data)


def _request_api(api_config):
    """按配置发起一次测试请求。"""
    method = api_config["method"].lower()
    url = api_config.get("url", "未知 URL")
    request_body = api_config.get("request", "{}")

    if method == "get":
        try:
            request_params = json.loads(request_body)
            return requests.get(url, params=request_params, verify=False, timeout=5)
        except json.JSONDecodeError:
            return requests.get(url, verify=False, timeout=5)
    if method == "post":
        headers = {"Content-Type": "application/json"}
        return requests.post(url, data=request_body, headers=headers, verify=False, timeout=5)
    raise ValueError(f"不支持的 HTTP 方法: {method}")


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


def _test_result(values, return_details, outcome, count=0, keyword=None):
    """兼容原有五元组，并为健康检测脚本提供详细判定。"""
    if return_details:
        return (*values, outcome, count, keyword)
    return values


def test_single_api(
    api_id,
    api_config=None,
    update_status=False,
    return_details=False,
    keywords=None,
):
    """使用多个关键词测试 API；任一关键词有效即判定正常。"""
    if api_config is None:
        api_config = get_config_by_id(api_id)
        if not api_config:
            logger.error(f"测试 API ID:{api_id} 失败: API 配置不存在")
            return _test_result(
                ("未知 URL", False, None, False, 0),
                return_details,
                "error",
            )

    # 使用传入的api_id参数，确保是字符串或整数类型
    if isinstance(api_id, dict):
        api_id = api_id.get("id", "未知ID")
    api_id = str(api_id)
    url = api_config.get("url", "未知 URL")

    # 检查 is_enabled 状态 (仅用于日志和跳过，测试路由不应跳过已禁用的)
    if not api_config.get("is_enabled", True):
        logger.info(f"API {url} (ID:{api_id}) 当前处于禁用状态，但仍执行测试。")

    start_time = time.time()
    response_rule = api_config.get("response", "{}")
    last_status_code = None
    no_data_status_code = None
    saw_no_data = False
    last_error = None

    for keyword in build_test_keywords(keywords):
        candidate_config = update_config_with_keyword(api_config, "[[keyword]]", keyword)
        candidate_url = candidate_config.get("url", url)
        try:
            response = _request_api(candidate_config)
            last_status_code = response.status_code
            if not 200 <= response.status_code < 300:
                last_error = f"关键词“{keyword}”返回 HTTP {response.status_code}"
                continue

            extracted_data = extract_from_json(response.text, response_rule)
            if bool(extracted_data):
                response_time_ms = int((time.time() - start_time) * 1000)
                if api_id != "未知ID" and api_id.isdigit():
                    update_api_status_in_db(api_id, True, response_time_ms)
                logger.info(
                    "API %s (ID:%s) 使用关键词“%s”测试成功，耗时: %sms",
                    candidate_url,
                    api_id,
                    keyword,
                    response_time_ms,
                )
                result_count = len(extracted_data) if hasattr(extracted_data, "__len__") else 1
                return _test_result(
                    (candidate_url, True, response.status_code, True, response_time_ms),
                    return_details,
                    "success",
                    result_count,
                    keyword,
                )

            if _response_indicates_no_data(response.text, extracted_data):
                saw_no_data = True
                no_data_status_code = response.status_code
                logger.info("API %s 使用关键词“%s”无结果，继续轮询。", candidate_url, keyword)
            else:
                last_error = f"关键词“{keyword}”的响应不符合提取规则"
        except Exception as e:
            last_error = f"关键词“{keyword}”测试异常: {e}"
            logger.warning("API %s (ID:%s) %s，继续轮询。", candidate_url, api_id, last_error)

    response_time_ms = int((time.time() - start_time) * 1000)

    if saw_no_data:
        # 接口可访问且明确表示无搜索结果，不应误判为故障或自动禁用。
        if api_id != "未知ID" and api_id.isdigit():
            update_api_status_in_db(api_id, True, response_time_ms)
        logger.info("API %s (ID:%s) 所有测试关键词均无结果，保留为正常状态。", url, api_id)
        return _test_result(
            (url, True, no_data_status_code, True, response_time_ms),
            return_details,
            "no_data",
        )

    if api_id != "未知ID" and api_id.isdigit():
        update_api_status_in_db(api_id, False, response_time_ms)
    logger.error("API %s (ID:%s) 多关键词测试均失败: %s，健康状态已标记为异常。", url, api_id, last_error)
    return _test_result(
        (url, False, last_status_code, False, response_time_ms),
        return_details,
        "error",
    )


def test_all_apis_and_update_status():
    """测试所有API配置并更新其状态"""
    api_configs = read_api_configs_from_db()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # 提交所有 API 配置进行测试
        futures = [executor.submit(test_single_api, config.get("id"), config) for config in api_configs]
        for _ in concurrent.futures.as_completed(futures):
            pass

    logger.info("所有 API 测试并更新健康状态完毕")
    return True, "所有 API 测试并更新健康状态成功"
