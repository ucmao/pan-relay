#!/usr/bin/env python3
"""
搜索源全量健康度检测与测试脚本 (Source Health Check & Test Script)

用法 (Usage):
    python scripts/check_sources_health.py [--keyword 仙逆] [--workers 16] [--auto-disable] [--output report.json]
"""

import argparse
import concurrent.futures
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Tuple

# 确保全局可载入项目 src 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.connection import get_db_connection, init_sqlite_db
from src.services.plugin_manager import plugin_manager
from src.services.system_config_service import (
    get_tg_search_config,
    save_tg_search_config,
    get_plugin_settings,
    save_plugin_status,
)
from src.services.telegram_search_service import search_telegram_channel

# 设置日志显示级别
logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s")


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def check_single_api(api_info: Dict[str, Any], keyword: str) -> Dict[str, Any]:
    name = api_info["name"]
    url = api_info["url"]
    start_time = time.time()
    result = {
        "type": "API",
        "name": name,
        "url": url,
        "status": "FAIL",
        "count": 0,
        "elapsed_ms": 0,
        "error": None,
    }

    try:
        from src.services.search_service import process_config, replace_keyword_in_config
        cfg = replace_keyword_in_config([api_info], "[[keyword]]", keyword)[0]
        items = process_config(cfg, keyword)
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms
        if items is not None:
            result["status"] = "PASS" if len(items) > 0 else "NO_DATA"
            result["count"] = len(items)
        else:
            result["error"] = "接口请求失败或解析为空"
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms
        result["error"] = str(e)

    return result


def check_single_tg(channel: str, keyword: str, proxy: str, timeout: int) -> Dict[str, Any]:
    start_time = time.time()
    result = {
        "type": "TG",
        "name": f"@{channel}",
        "url": f"https://t.me/s/{channel}?q={keyword}",
        "status": "FAIL",
        "count": 0,
        "elapsed_ms": 0,
        "error": None,
    }

    try:
        items = search_telegram_channel(keyword, channel, proxy=proxy, timeout=timeout)
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms

        if items and len(items) > 0:
            result["status"] = "PASS"
            result["count"] = len(items)
        else:
            result["status"] = "NO_DATA"
            result["error"] = "未搜索到资源或公开预览页不可用"
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms
        result["error"] = str(e)

    return result


def check_single_plugin(plugin: Any, keyword: str) -> Dict[str, Any]:
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
    }

    try:
        items = plugin.search(keyword)
        elapsed_ms = int((time.time() - start_time) * 1000)
        result["elapsed_ms"] = elapsed_ms
        if items and len(items) > 0:
            result["status"] = "PASS"
            result["count"] = len(items)
        else:
            result["status"] = "NO_DATA"
            result["error"] = "无匹配结果"
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
    parser.add_argument("--keyword", "-k", default="仙逆", help="测试关键词 (默认: 仙逆)")
    parser.add_argument("--workers", "-w", type=int, default=16, help="测试并发线程数 (默认: 16)")
    parser.add_argument("--auto-disable", action="store_true", help="是否自动禁用测试失败/无法连接的搜索源")
    parser.add_argument("--sync-defaults", action="store_true", help="同步健康的 API 和 TG 频道至默认初始化文件 (app_config.py 与 schema_sqlite.sql)")
    parser.add_argument("--output", "-o", help="导出 JSON 格式测试报告路径")
    args = parser.parse_args()

    # 如果指定了 --sync-defaults，自动包含 --auto-disable
    if args.sync_defaults:
        args.auto_disable = True

    print(f"\n{Color.BOLD}{Color.BLUE}======================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}   pan-relay 搜索源健康度全量检测 (测试关键词: '{args.keyword}'){Color.RESET}")
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
    tg_channels = tg_config.get("channels", [])
    tg_proxy = tg_config.get("proxy", "")
    tg_timeout = tg_config.get("timeout", 10)

    # 3. 提取全量 Plugins
    plugins = plugin_manager.get_all_plugins()

    print(f"📦 载入检测对象: API 接口 ({len(apis)} 个), TG 频道 ({len(tg_channels)} 个), 插件 ({len(plugins)} 个)\n")

    api_results = []
    tg_results = []
    plugin_results = []

    # 并发测试 API
    print(f"🚀 开始测试 API 接口...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(apis) or 1)) as executor:
        futures = {executor.submit(check_single_api, api, args.keyword): api for api in apis}
        for future in concurrent.futures.as_completed(futures):
            api_results.append(future.result())

    # 并发测试 TG 频道
    print(f"🚀 开始测试 TG 频道 ({len(tg_channels)} 个)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(tg_channels) or 1)) as executor:
        futures = {executor.submit(check_single_tg, ch, args.keyword, tg_proxy, tg_timeout): ch for ch in tg_channels}
        for future in concurrent.futures.as_completed(futures):
            tg_results.append(future.result())

    # 并发测试 Plugins
    print(f"🚀 开始测试 插件 ({len(plugins)} 个)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(plugins) or 1)) as executor:
        futures = {executor.submit(check_single_plugin, p, args.keyword): p for p in plugins}
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
    print_section("Telegram 频道", tg_results)
    print_section("第三方网站插件", plugin_results)

    # 自动禁用处理
    if args.auto_disable:
        print(f"\n{Color.BOLD}{Color.YELLOW}⚡ 正在执行自动禁用选项 (--auto-disable)...{Color.RESET}")
        # 1. 禁用失败 API
        conn = get_db_connection()
        cursor = conn.cursor()
        for r in api_results:
            if r["status"] == "FAIL":
                cursor.execute("UPDATE api_config SET is_enabled = 0 WHERE name = ?", (r["name"],))
        conn.commit()
        conn.close()

        # 2. 移除失败的 TG 频道
        valid_tg = [r["name"].lstrip("@") for r in tg_results if r["status"] in ("PASS", "NO_DATA")]
        save_tg_search_config({**tg_config, "channels": valid_tg})

        # 3. 禁用失败插件
        for r in plugin_results:
            p_name = r["name"].split(" (")[0]
            if r["status"] == "FAIL":
                save_plugin_status(p_name, False)

        print(f"{Color.GREEN}✔ 数据库持久化禁用完成！{Color.RESET}")

    # 同步代码/SQL默认值
    if args.sync_defaults:
        print(f"\n{Color.BOLD}{Color.YELLOW}🛠 正在同步健康源至 GitHub 默认模版代码 (--sync-defaults)...{Color.RESET}")
        
        # 1. 同步更新 src/configs/app_config.py 中的 DEFAULT_TG_CHANNELS
        valid_tg_channels = [r["name"].lstrip("@") for r in tg_results if r["status"] in ("PASS", "NO_DATA")]
        app_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "configs", "app_config.py"))
        
        if os.path.exists(app_config_path):
            with open(app_config_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            tg_str = ",".join(valid_tg_channels)
            pattern = re.compile(r'DEFAULT_TG_CHANNELS\s*=\s*\([\s\S]*?\)', re.MULTILINE)
            new_tg_decl = f'DEFAULT_TG_CHANNELS = (\n    "{tg_str}"\n)'
            if pattern.search(content):
                new_content = pattern.sub(new_tg_decl, content)
                with open(app_config_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"{Color.GREEN}✔ 已同步更新 app_config.py 中 DEFAULT_TG_CHANNELS (包含 {len(valid_tg_channels)} 个健康频道){Color.RESET}")

    # 导出报告
    if args.output:
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "keyword": args.keyword,
            "api_results": api_results,
            "tg_results": tg_results,
            "plugin_results": plugin_results,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(f"\n📄 完整报告已保存至: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
