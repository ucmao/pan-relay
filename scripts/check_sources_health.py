#!/usr/bin/env python3
"""
搜索源全量健康度检测与测试脚本 (Source Health Check & Test Script)

用法 (Usage):
    python scripts/check_sources_health.py [--keyword 仙逆,逆袭,总裁] [--workers 16] [--auto-disable] [--output report.json]
"""

import argparse
import concurrent.futures
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List

# 确保全局可载入项目 src 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.connection import get_db_connection, init_sqlite_db
from src.db.telegram_channels import get_all_channels, set_channel_enabled, update_channel_health
from src.services.plugin_manager import plugin_manager
from src.services.system_config_service import (
    get_tg_search_config,
    save_plugin_status,
)
from src.services.telegram_search_service import search_telegram_channel
from src.utils.test_keywords import build_test_keywords

# 设置日志显示级别
logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s")


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def sync_api_defaults(schema_path: str, api_configs: List[Dict[str, Any]]) -> None:
    """把当前数据库中的 API 配置和健康状态写回首次初始化 SQL。"""
    with open(schema_path, "r", encoding="utf-8") as file:
        content = file.read()

    rows = []
    for config in sorted(api_configs, key=lambda item: int(item.get("id") or 0)):
        values = (
            _sql_literal(config.get("name")),
            _sql_literal(config.get("url")),
            _sql_literal(str(config.get("method") or "get").lower()),
            _sql_literal(config.get("request") or ""),
            _sql_literal(config.get("response") or ""),
            "1" if config.get("status") else "0",
            str(int(config.get("response_time_ms") or 0)),
            "1" if config.get("is_enabled") else "0",
        )
        rows.append("(" + ", ".join(values) + ")")

    if not rows:
        raise RuntimeError("没有可同步的 API 配置")

    replacement = (
        "INSERT OR IGNORE INTO api_config "
        "(name, url, method, request, response, status, response_time_ms, is_enabled) VALUES\n"
        + ",\n".join(rows)
        + ";"
    )
    pattern = re.compile(
        r"INSERT OR IGNORE INTO api_config "
        r"\(name, url, method, request, response, status, response_time_ms, is_enabled\) VALUES\n"
        r".*?;(?=\n\n-- ----------------------------\n-- Default data for `resources`)",
        re.DOTALL,
    )
    updated, count = pattern.subn(replacement, content, count=1)
    if count != 1:
        raise RuntimeError("未找到 schema_sqlite.sql 中的 API 默认数据块")

    with open(schema_path, "w", encoding="utf-8") as file:
        file.write(updated)


def sync_app_defaults(
    app_config_path: str,
    tg_channels: List[str],
    disabled_tg_channels: List[str],
    plugin_statuses: Dict[str, bool],
) -> None:
    """同步 TG 频道和插件的首次初始化状态。"""
    with open(app_config_path, "r", encoding="utf-8") as file:
        content = file.read()

    tg_value = ",".join(tg_channels)
    tg_replacement = f'DEFAULT_TG_CHANNELS = (\n    "{tg_value}"\n)'
    content, tg_count = re.subn(
        r"DEFAULT_TG_CHANNELS\s*=\s*\([\s\S]*?^\)",
        tg_replacement,
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if tg_count != 1:
        raise RuntimeError("未找到 app_config.py 中的 DEFAULT_TG_CHANNELS")

    disabled_tg_value = ",".join(disabled_tg_channels)
    disabled_tg_replacement = f'DEFAULT_DISABLED_TG_CHANNELS = (\n    "{disabled_tg_value}"\n)'
    content, disabled_tg_count = re.subn(
        r"DEFAULT_DISABLED_TG_CHANNELS\s*=\s*(?:\([\s\S]*?^\)|\(\))",
        disabled_tg_replacement,
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if disabled_tg_count != 1:
        raise RuntimeError("未找到 app_config.py 中的 DEFAULT_DISABLED_TG_CHANNELS")

    plugin_lines = ["DEFAULT_PLUGIN_SETTINGS = {"]
    for name in sorted(plugin_statuses):
        plugin_lines.append(f"    {name!r}: {bool(plugin_statuses[name])},")
    plugin_lines.append("}")
    plugin_replacement = "\n".join(plugin_lines)
    content, plugin_count = re.subn(
        r"DEFAULT_PLUGIN_SETTINGS\s*=\s*\{[\s\S]*?^\}",
        plugin_replacement,
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if plugin_count != 1:
        raise RuntimeError("未找到 app_config.py 中的 DEFAULT_PLUGIN_SETTINGS")

    with open(app_config_path, "w", encoding="utf-8") as file:
        file.write(content)


def check_single_api(api_info: Dict[str, Any], keywords: List[str]) -> Dict[str, Any]:
    name = api_info["name"]
    url = api_info["url"]
    start_time = time.time()
    result = {
        "type": "API",
        "id": api_info.get("id"),
        "name": name,
        "url": url,
        "status": "FAIL",
        "count": 0,
        "elapsed_ms": 0,
        "error": None,
    }

    try:
        from src.services.api_config_service import test_single_api

        (
            _tested_url,
            _healthy,
            _status_code,
            _rule_status,
            elapsed_ms,
            outcome,
            count,
            matched_keyword,
        ) = test_single_api(
            str(api_info.get("id") or name),
            api_info,
            return_details=True,
            keywords=keywords,
        )
        result["elapsed_ms"] = elapsed_ms
        result["count"] = count
        result["keyword"] = matched_keyword
        if outcome == "success":
            result["status"] = "PASS"
        elif outcome == "no_data":
            result["status"] = "NO_DATA"
            result["error"] = "接口连通正常，但轮询关键词均无结果"
        else:
            result["status"] = "FAIL"
            result["error"] = "多关键词请求或响应解析均失败"
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms
        result["error"] = str(e)

    return result


def check_single_tg(channel: str, keywords: List[str], proxy: str, timeout: int) -> Dict[str, Any]:
    start_time = time.time()
    result = {
        "type": "TG",
        "name": f"@{channel}",
        "url": f"https://t.me/s/{channel}?q={keywords[0] if keywords else ''}",
        "status": "FAIL",
        "count": 0,
        "elapsed_ms": 0,
        "error": None,
    }

    try:
        items = []
        matched_keyword = None
        saw_empty_response = False
        last_error = None
        for keyword in keywords:
            try:
                items = search_telegram_channel(
                    keyword,
                    channel,
                    proxy=proxy,
                    timeout=timeout,
                    raise_on_error=True,
                )
            except Exception as e:
                last_error = str(e)
                continue
            if not items:
                saw_empty_response = True
                continue
            matched_keyword = keyword
            break
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms

        if items and len(items) > 0:
            result["status"] = "PASS"
            result["count"] = len(items)
            result["keyword"] = matched_keyword
        elif saw_empty_response:
            result["status"] = "NO_DATA"
            result["error"] = "未搜索到资源或公开预览页不可用"
        else:
            raise RuntimeError(last_error or "所有关键词测试均失败")
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms
        result["error"] = str(e)

    return result


def check_single_plugin(plugin: Any, keywords: List[str]) -> Dict[str, Any]:
    start_time = time.time()
    disp_name = getattr(plugin, "display_name", plugin.name)
    result = {
        "type": "PLUGIN",
        "name": f"{plugin.name} ({disp_name})",
        "url": getattr(plugin, "base_url", "N/A"),
        "status": "FAIL",
        "count": 0,
        "elapsed_ms": 0,
        "error": None,
        "publish_by_default": bool(getattr(plugin, "publish_by_default", True)),
    }

    try:
        if hasattr(plugin, "health_check"):
            healthy, health_message = plugin.health_check()
            if not healthy:
                raise RuntimeError(f"插件连通性检查失败: {health_message}")

        items = []
        matched_keyword = None
        saw_empty_response = False
        last_error = None
        for keyword in keywords:
            try:
                items = plugin.search(keyword)
            except Exception as e:
                last_error = str(e)
                continue
            if not items:
                saw_empty_response = True
                continue
            matched_keyword = keyword
            break
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms
        if items and len(items) > 0:
            result["status"] = "PASS"
            result["count"] = len(items)
            result["keyword"] = matched_keyword
        elif saw_empty_response:
            result["status"] = "NO_DATA"
            result["error"] = "无匹配结果"
        else:
            raise RuntimeError(last_error or "所有关键词测试均失败")
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms
        err_msg = str(e)
        if "NameResolutionError" in err_msg or "Failed to resolve" in err_msg:
            result["error"] = "DNS域名失联/已闭站"
        elif "SSLCertVerificationError" in err_msg or "SSLEOFError" in err_msg or "SSL" in err_msg:
            result["error"] = "SSL证书异常"
        elif "ConnectionRefused" in err_msg or "111" in err_msg:
            result["error"] = "服务器拒绝连接"
        elif "timed out" in err_msg:
            result["error"] = "请求超时"
        else:
            result["error"] = err_msg[:60]

    return result


def main():
    parser = argparse.ArgumentParser(description="pan-relay 搜索源健康度全量检测工具")
    parser.add_argument(
        "--keyword",
        "-k",
        action="append",
        help="优先测试关键词，可重复传入或用逗号分隔；默认轮询：仙逆、逆袭、总裁",
    )
    parser.add_argument("--workers", "-w", type=int, default=16, help="测试并发线程数 (默认: 16)")
    parser.add_argument("--auto-disable", action="store_true", help="根据全量检测结果更新所有搜索源的启用状态")
    parser.add_argument(
        "--sync-defaults",
        action="store_true",
        help="发布前同步 API、TG、插件健康状态至首次初始化配置",
    )
    parser.add_argument("--output", "-o", help="导出 JSON 格式测试报告路径")
    args = parser.parse_args()

    # 如果指定了 --sync-defaults，自动包含 --auto-disable
    if args.sync_defaults:
        args.auto_disable = True

    test_keywords = build_test_keywords(args.keyword)
    keyword_text = "、".join(test_keywords)
    print(f"\n{Color.BOLD}{Color.BLUE}======================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}   pan-relay 搜索源健康度全量检测 (轮询关键词: {keyword_text}){Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}======================================================{Color.RESET}\n")

    init_sqlite_db()

    # 1. 提取全量 API
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute("SELECT * FROM api_config")
    apis = cursor.fetchall()
    conn.close()

    # 2. 提取全量 TG 频道
    tg_config = get_tg_search_config()
    tg_channels = [item["channel"] for item in get_all_channels()]
    tg_proxy = tg_config.get("proxy", "")
    tg_timeout = tg_config.get("timeout", 10)

    # 3. 提取全量 Plugins
    # wanou 与 ouge 使用同一个上游 API，保留 ouge、删除 wanou，避免重复请求和重复结果。
    plugins = plugin_manager.get_all_plugins()

    print(f"📦 载入检测对象: API 接口 ({len(apis)} 个), TG 频道 ({len(tg_channels)} 个), 插件 ({len(plugins)} 个)\n")

    api_results = []
    tg_results = []
    plugin_results = []

    # 并发测试 API
    print(f"🚀 开始测试 API 接口...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(apis) or 1)) as executor:
        futures = {executor.submit(check_single_api, api, test_keywords): api for api in apis}
        for future in concurrent.futures.as_completed(futures):
            api_results.append(future.result())

    # 并发测试 TG 频道
    print(f"🚀 开始测试 TG 频道 ({len(tg_channels)} 个)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(tg_channels) or 1)) as executor:
        futures = {executor.submit(check_single_tg, ch, test_keywords, tg_proxy, tg_timeout): ch for ch in tg_channels}
        for future in concurrent.futures.as_completed(futures):
            tg_results.append(future.result())

    # 并发测试 Plugins
    print(f"🚀 开始测试 插件 ({len(plugins)} 个)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(plugins) or 1)) as executor:
        futures = {executor.submit(check_single_plugin, p, test_keywords): p for p in plugins}
        for future in concurrent.futures.as_completed(futures):
            plugin_results.append(future.result())

    # 输出统计报告
    def print_section(title: str, results: List[Dict[str, Any]]):
        print(f"\n{Color.BOLD}--- {title} 测试结果 ---{Color.RESET}")
        pass_count = sum(1 for r in results if r["status"] == "PASS")
        nodata_count = sum(1 for r in results if r["status"] == "NO_DATA")
        fail_count = sum(1 for r in results if r["status"] == "FAIL")
        total = len(results)
        rate = (pass_count / total * 100) if total > 0 else 0

        print(f"总数: {total} | {Color.GREEN}有效/可用: {pass_count}{Color.RESET} | {Color.YELLOW}无数据: {nodata_count}{Color.RESET} | {Color.RED}失败/断链: {fail_count}{Color.RESET} | 可用率: {rate:.1f}%")

        print(f"\n{'名称':<35} | {'状态':<8} | {'资源数':<6} | {'耗时(ms)':<8} | {'错误信息'}")
        print("-" * 85)
        for r in sorted(results, key=lambda x: (x["status"] != "PASS", -x["count"])):
            status_str = (
                f"{Color.GREEN}PASS{Color.RESET}"
                if r["status"] == "PASS"
                else (f"{Color.YELLOW}NO_DATA{Color.RESET}" if r["status"] == "NO_DATA" else f"{Color.RED}FAIL{Color.RESET}")
            )
            err_str = r["error"] or ""
            print(f"{r['name'][:33]:<35} | {status_str:<17} | {r['count']:<6} | {r['elapsed_ms']:<8} | {err_str[:30]}")

    print_section("聚合 API 接口", api_results)
    print("\n说明：下方 TG 的总数/有效/失败是频道数量；表格中的资源数是该频道命中的网盘资源条数。")
    print_section("Telegram 频道", tg_results)
    print_section("第三方网站插件", plugin_results)

    # 自动禁用处理
    if args.auto_disable:
        print(f"\n{Color.BOLD}{Color.YELLOW}⚡ 正在执行自动禁用选项 (--auto-disable)...{Color.RESET}")
        # 1. 按检测结果统一更新 API；NO_DATA 表示可连通，不做误杀。
        conn = get_db_connection()
        cursor = conn.cursor()
        for r in api_results:
            is_healthy = r["status"] in ("PASS", "NO_DATA")
            cursor.execute(
                "UPDATE api_config SET status = ?, is_enabled = ?, response_time_ms = ? WHERE name = ?",
                (1 if is_healthy else 0, 1 if is_healthy else 0, r["elapsed_ms"], r["name"]),
            )
        conn.commit()
        conn.close()

        # 2. 更新逐频道启用状态与健康检测结果。
        for result in tg_results:
            channel = result["name"].lstrip("@")
            is_healthy = result["status"] in ("PASS", "NO_DATA")
            set_channel_enabled(channel, is_healthy)
            update_channel_health(
                channel=channel,
                health_status=("healthy" if result["status"] == "PASS" else "no_data" if result["status"] == "NO_DATA" else "error"),
                latency_ms=result["elapsed_ms"],
                result_count=result["count"],
                health_message=result.get("error") or "",
            )

        # 3. 按检测结果统一更新插件状态
        for r in plugin_results:
            p_name = r["name"].split(" (")[0]
            should_enable = (
                r["status"] in ("PASS", "NO_DATA")
                and r.get("publish_by_default", True)
            )
            save_plugin_status(p_name, should_enable)

        print(f"{Color.GREEN}✔ 数据库搜索源启用状态同步完成！{Color.RESET}")

    # 同步代码/SQL默认值
    if args.sync_defaults:
        print(f"\n{Color.BOLD}{Color.YELLOW}🛠 正在同步健康源至 GitHub 首次初始化配置 (--sync-defaults)...{Color.RESET}")

        disabled_tg_channels = [r["name"].lstrip("@") for r in tg_results if r["status"] == "FAIL"]
        plugin_statuses = {
            r["name"].split(" (")[0]: (
                r["status"] in ("PASS", "NO_DATA")
                and r.get("publish_by_default", True)
            )
            for r in plugin_results
        }
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        app_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "configs", "app_config.py"))
        schema_path = os.path.join(project_root, "schema_sqlite.sql")

        conn = get_db_connection()
        cursor = conn.cursor(as_dict=True)
        cursor.execute("SELECT * FROM api_config ORDER BY id")
        synced_apis = cursor.fetchall()
        conn.close()

        sync_api_defaults(schema_path, synced_apis)
        sync_app_defaults(app_config_path, tg_channels, disabled_tg_channels, plugin_statuses)
        enabled_apis = sum(1 for item in synced_apis if item.get("is_enabled"))
        enabled_plugins = sum(1 for enabled in plugin_statuses.values() if enabled)
        print(f"{Color.GREEN}✔ API 默认状态已同步：{enabled_apis}/{len(synced_apis)} 个启用{Color.RESET}")
        enabled_tg = len(tg_channels) - len(disabled_tg_channels)
        print(f"{Color.GREEN}✔ TG 默认状态已同步：{enabled_tg}/{len(tg_channels)} 个启用（总表未删减）{Color.RESET}")
        print(f"{Color.GREEN}✔ 插件默认状态已同步：{enabled_plugins}/{len(plugin_statuses)} 个启用{Color.RESET}")

    # 导出报告
    if args.output:
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "keywords": test_keywords,
            "api_results": api_results,
            "tg_results": tg_results,
            "plugin_results": plugin_results,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(f"\n📄 完整报告已保存至: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
