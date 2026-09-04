import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from src.models.search_item import SearchResultItem
from src.services.system_config_service import get_sensitive_words_config

logger = logging.getLogger(__name__)


class DFAMatcher:
    """
    基于 DFA (确定有向自动机) 的敏感词匹配器。
    搜索时间复杂度接近 O(N)，适合高并发高频搜索文本检测。
    """

    def __init__(self, words: Optional[List[str]] = None):
        self.trie: Dict[str, Any] = {}
        self.end_key = "\x00"
        if words:
            for word in words:
                self.add_word(word)

    def add_word(self, word: str):
        clean_word = str(word or "").strip().lower()
        if not clean_word:
            return
        node = self.trie
        for char in clean_word:
            if char not in node:
                node[char] = {}
            node = node[char]
        node[self.end_key] = True

    def find_sensitive_word(self, text: str) -> Optional[str]:
        """
        检测文本中是否包含敏感词。
        若包含，返回第一个匹配到的敏感词；否则返回 None。
        """
        clean_text = str(text or "").lower()
        length = len(clean_text)
        if length == 0 or not self.trie:
            return None

        for i in range(length):
            node = self.trie
            j = i
            matched_chars = []
            while j < length and clean_text[j] in node:
                node = node[clean_text[j]]
                matched_chars.append(clean_text[j])
                if self.end_key in node:
                    return "".join(matched_chars)
                j += 1
        return None


# DFA 匹配器单例缓存与锁
_DFA_MATCHER_CACHE: Optional[DFAMatcher] = None
_DFA_LOCK = threading.Lock()


def reload_sensitive_words_cache():
    """重置/重新载入敏感词匹配器缓存"""
    global _DFA_MATCHER_CACHE
    with _DFA_LOCK:
        _DFA_MATCHER_CACHE = None
    logger.info("敏感词 DFA 匹配器缓存已重置。")


def get_dfa_matcher() -> DFAMatcher:
    """获取当前的 DFA 匹配器实例（延迟初始化）"""
    global _DFA_MATCHER_CACHE
    with _DFA_LOCK:
        if _DFA_MATCHER_CACHE is None:
            config = get_sensitive_words_config()
            words = config.get("words", []) if config.get("enabled", True) else []
            _DFA_MATCHER_CACHE = DFAMatcher(words)
        return _DFA_MATCHER_CACHE


def check_input_keyword(keyword: str) -> Tuple[bool, Optional[str]]:
    """
    检查搜索关键词是否违法违规。
    返回: (is_blocked: bool, matched_word: Optional[str])
    """
    config = get_sensitive_words_config()
    if not config.get("enabled", True) or not config.get("input_enabled", True):
        return False, None

    matcher = get_dfa_matcher()
    matched = matcher.find_sensitive_word(keyword)
    if matched:
        logger.warning(f"搜索关键词 '{keyword}' 命中敏感词: {matched}")
        return True, matched
    return False, None


def is_text_sensitive(text: str) -> bool:
    """辅助判断文本是否包含敏感词"""
    if not text:
        return False
    matcher = get_dfa_matcher()
    return matcher.find_sensitive_word(text) is not None


def filter_search_results(results: List[Any]) -> List[Any]:
    """
    对搜索结果中的标题和链接进行敏感词过滤，直接剔除违规结果。
    支持 SearchResultItem, dict, list/tuple 数据类型。
    """
    config = get_sensitive_words_config()
    if not config.get("enabled", True) or not config.get("output_enabled", True):
        return results

    if not results:
        return []

    matcher = get_dfa_matcher()
    if not matcher.trie:
        return results

    filtered = []
    for item in results:
        title = ""
        share_link = ""

        if isinstance(item, SearchResultItem):
            title = item.title
            share_link = item.share_link
        elif isinstance(item, dict):
            title = item.get("title", "")
            share_link = item.get("share_link", "")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            title = str(item[0])
            share_link = str(item[1])

        # 检查标题或链接是否包含敏感词
        if matcher.find_sensitive_word(title) or matcher.find_sensitive_word(share_link):
            logger.info(f"敏感词过滤丢弃违规结果: 标题='{title}', 链接='{share_link}'")
            continue

        filtered.append(item)

    return filtered
