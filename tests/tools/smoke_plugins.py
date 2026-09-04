#!/usr/bin/env python3
"""对指定插件执行多关键词在线烟测，并输出 JSON 报告。"""

import argparse
import concurrent.futures
import json
import time
from datetime import datetime

from src.services.plugin_manager import PluginManager


DEFAULT_KEYWORDS = ("庆余年", "三体", "阿凡达", "复仇者联盟", "哈利波特")


def run_case(plugin, keyword):
    started = time.monotonic()
    try:
        results = plugin.search(keyword)
        return {
            "plugin": plugin.name,
            "keyword": keyword,
            "status": "active" if results else "no_data",
            "result_count": len(results),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error": "",
        }
    except Exception as error:
        return {
            "plugin": plugin.name,
            "keyword": keyword,
            "status": "error",
            "result_count": 0,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error": str(error)[:500],
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plugins", nargs="+")
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()
    discovered = {plugin.name: plugin for plugin in PluginManager().get_all_plugins()}
    missing = sorted(set(args.plugins) - discovered.keys())
    if missing:
        parser.error(f"未知插件: {', '.join(missing)}")

    cases = [(discovered[name], keyword) for name in args.plugins for keyword in DEFAULT_KEYWORDS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(cases))) as executor:
        results = list(executor.map(lambda case: run_case(*case), cases))
    print(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "keywords": DEFAULT_KEYWORDS,
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
