import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.search_item import SearchResultItem
from src.services.sensitive_word_service import (
    DFAMatcher,
    check_input_keyword,
    filter_search_results,
    reload_sensitive_words_cache,
)
from src.services.system_config_service import (
    get_sensitive_words_config,
    save_sensitive_words_config,
)
from src.services.search_service import search_public_resources, generate_search_stream_events


def test_dfa_performance():
    print("[1/5] 测试 DFA 敏感词匹配性能与准确度...")
    words = ["外挂", "博彩", "破解", "卡密"]
    matcher = DFAMatcher(words)

    assert matcher.find_sensitive_word("英雄联盟外挂下载") == "外挂"
    assert matcher.find_sensitive_word("在线博彩平台") == "博彩"
    assert matcher.find_sensitive_word("正常电影4k高清") is None

    # 高并发性能检测：测试 50,000 次匹配耗时
    start_time = time.time()
    for _ in range(50000):
        matcher.find_sensitive_word("这是一个高清复仇者联盟电影下载无任何违规")
    elapsed = (time.time() - start_time) * 1000
    print(f"  ✓ 50,000 次匹配测试通过，总耗时: {elapsed:.2f} ms")
    assert elapsed < 500, "匹配耗时过长，不符合预期"


def test_input_keyword_blocking():
    print("[2/5] 测试输入关键词拦截...")
    # 保存配置
    save_sensitive_words_config({
        "enabled": True,
        "input_enabled": True,
        "output_enabled": True,
        "words": ["外挂", "博彩", "色情"],
    })

    # 命中敏感词
    blocked, matched = check_input_keyword("绝地求生外挂免费版")
    assert blocked is True
    assert matched == "外挂"
    print(f"  ✓ 成功拦截搜索词 '绝地求生外挂免费版'，命中敏感词: '{matched}'")

    # 未命中敏感词
    blocked, matched = check_input_keyword("复仇者联盟 1080P")
    assert blocked is False
    assert matched is None
    print("  ✓ 正常搜索词 '复仇者联盟 1080P' 校验通过")


def test_output_result_filtering():
    print("[3/5] 测试输出搜索结果剔除...")
    items = [
        SearchResultItem(source="test", title="正常资源 - 钢铁侠.mkv", share_link="https://pan.quark.cn/s/111", cloud_name="夸克网盘"),
        SearchResultItem(source="test", title="全网独家游戏外挂工具.exe", share_link="https://pan.baidu.com/s/222", cloud_name="百度网盘"),
        SearchResultItem(source="test", title="澳门在线博彩入口", share_link="https://drive.uc.cn/s/333", cloud_name="UC网盘"),
        SearchResultItem(source="test", title="合规电影", share_link="https://pan.quark.cn/s/博彩_link", cloud_name="夸克网盘"),
    ]

    filtered = filter_search_results(items)
    print(f"  ✓ 过滤前 {len(items)} 条，过滤后 {len(filtered)} 条")
    assert len(filtered) == 1
    assert filtered[0].title == "正常资源 - 钢铁侠.mkv"
    print("  ✓ 成功精准剔除包含标题/链接敏感词的 3 条违规数据")


def test_search_service_integration():
    print("[4/5] 测试 search_service 模块集成...")
    # 模拟违规关键词搜索
    success, message, results = search_public_resources("全网独家外挂", limit=10)
    assert success is False
    assert "已禁止搜索" in message
    print(f"  ✓ search_public_resources 阻断返回: {message}")

    # 模拟 SSE 流事件
    import json
    stream_events = list(generate_search_stream_events("英雄联盟外挂"))
    assert len(stream_events) >= 1
    event_data = json.loads(stream_events[0])
    assert "已禁止搜索" in event_data.get("message", "")
    print(f"  ✓ generate_search_stream_events 流阻断返回: {event_data['message']}")


def test_dynamic_config_reload():
    print("[5/5] 测试后台配置更新与动态重载...")
    # 移除 '外挂'，新增 '自动刷课'
    save_sensitive_words_config({
        "enabled": True,
        "input_enabled": True,
        "output_enabled": True,
        "words": ["自动刷课"],
    })

    # '外挂' 不再被阻断
    blocked, matched = check_input_keyword("绝地求生外挂")
    assert blocked is False

    # '自动刷课' 被阻断
    blocked, matched = check_input_keyword("大学自动刷课脚本")
    assert blocked is True
    assert matched == "自动刷课"
    print("  ✓ 后台修改敏感词库后，DFA 模型实时动态更新成功！")


if __name__ == "__main__":
    print("====== 开始敏感词过滤单元与集成测试 ======")
    test_dfa_performance()
    test_input_keyword_blocking()
    test_output_result_filtering()
    test_search_service_integration()
    test_dynamic_config_reload()
    print("====== 所有测试用例无误通过！ ======")
