"""搜索源健康测试使用的通用关键词。"""

from typing import Iterable, List, Optional, Union


DEFAULT_TEST_KEYWORDS = ("仙逆", "逆袭", "总裁")


def build_test_keywords(
    primary: Optional[Union[str, Iterable[str]]] = None,
) -> List[str]:
    """返回去重后的测试关键词；调用方提供的关键词优先。"""
    candidates = []
    if isinstance(primary, str):
        candidates.extend(primary.split(","))
    elif primary:
        for item in primary:
            candidates.extend(str(item).split(","))
    candidates.extend(DEFAULT_TEST_KEYWORDS)

    keywords = []
    for candidate in candidates:
        keyword = str(candidate).strip()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    return keywords
