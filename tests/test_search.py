import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app import app
from src.models.search_item import SearchResultItem
from src.pan_operator import create_share
from src.services.link_checker import (
    STATE_BAD,
    STATE_LOCKED,
    STATE_OK,
    STATE_UNSUPPORTED,
    LinkChecker,
    check_link,
    check_links_batch,
)
from src.services.search_service import (
    calculate_completeness_score,
    calculate_keyword_score,
    calculate_rank_score,
    calculate_relevance_score,
    calculate_time_score,
    clear_search_cache,
    dedupe_search_results,
    filter_results_by_title,
    get_title_matched_terms,
    merge_or_select_better,
    search_public_resources,
    set_cached_search_items,
    sort_search_results,
)
from src.utils.netdisk_utils import (
    FRONTEND_DISPLAY_NETDISK_OPTIONS,
    extract_canonical_resource_key,
    extract_password_from_url,
    match_netdisk_link,
)


class SearchDeduplicationTest(unittest.TestCase):
    def test_canonical_resource_key_extraction(self):
        self.assertEqual("quark:c502b66a87c5", extract_canonical_resource_key("https://pan.quark.cn/s/c502b66a87c5#/list/share"))
        self.assertEqual("baidu:1abcdefg", extract_canonical_resource_key("https://pan.baidu.com/s/1abcdefg?pwd=1234"))
        self.assertEqual("aliyun:xyz123", extract_canonical_resource_key("https://www.alipan.com/s/xyz123"))
        self.assertEqual("uc:abc123", extract_canonical_resource_key("https://drive.uc.cn/s/abc123?public=1"))
        self.assertEqual("xunlei:VM-12345", extract_canonical_resource_key("https://pan.xunlei.com/s/VM-12345"))
        self.assertEqual("123pan:abcd-1234", extract_canonical_resource_key("https://www.123pan.com/s/abcd-1234"))
        self.assertEqual("tianyi:xyz789", extract_canonical_resource_key("https://cloud.189.cn/t/xyz789"))
        self.assertEqual("115:sw34567", extract_canonical_resource_key("https://115.com/s/sw34567?password=abcd"))

    def test_extract_password_from_url(self):
        self.assertEqual("1234", extract_password_from_url("https://pan.baidu.com/s/xxx?pwd=1234"))
        self.assertEqual("abcd", extract_password_from_url("https://115.com/s/xxx?password=abcd"))
        self.assertEqual("8888", extract_password_from_url("https://pan.quark.cn/s/xxx?code=8888"))
        self.assertIsNone(extract_password_from_url("https://pan.quark.cn/s/xxx"))

    def test_different_links_with_same_title_are_not_deduped(self):
        results = [
            SearchResultItem(source="tg", title="繁花", share_link="https://pan.quark.cn/s/share_aaa", cloud_name="夸克网盘"),
            SearchResultItem(source="tg", title="繁花", share_link="https://pan.quark.cn/s/share_bbb", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="繁花", share_link="https://pan.quark.cn/s/share_ccc", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="繁花", share_link="https://pan.baidu.com/s/share_ddd", cloud_name="百度网盘"),
        ]
        deduped = dedupe_search_results(results)
        self.assertEqual(4, len(deduped))

    def test_same_link_different_titles_dedupes_and_selects_better(self):
        results = [
            SearchResultItem(source="tg", title="繁花", share_link="https://pan.quark.cn/s/same_quark_id", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="【4K全集完结】繁花 国粤双语 2023", share_link="https://pan.quark.cn/s/same_quark_id?from=other", cloud_name="夸克网盘"),
        ]
        deduped = dedupe_search_results(results)
        self.assertEqual(1, len(deduped))
        self.assertEqual("【4K全集完结】繁花 国粤双语 2023", deduped[0].title)


class SearchRankingTest(unittest.TestCase):
    def tearDown(self):
        clear_search_cache()

    def test_single_term_requires_contiguous_title_match(self):
        results = [
            SearchResultItem(source="other", title="先例汇编", share_link="https://pan.quark.cn/s/one", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="先 行案例", share_link="https://pan.quark.cn/s/two", cloud_name="夸克网盘"),
        ]
        self.assertEqual(["先例汇编"], [item.title for item in filter_results_by_title(results, "先例")])

    def test_multiple_terms_match_any_whitespace_separated_term_and_rank_by_count(self):
        results = [
            SearchResultItem(source="hot", title="只含 A", share_link="https://pan.quark.cn/s/one", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="A 与 B 和 C", share_link="https://pan.quark.cn/s/two", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="无关结果", share_link="https://pan.quark.cn/s/three", cloud_name="夸克网盘"),
        ]
        filtered = filter_results_by_title(results, "A\tB C")
        self.assertEqual(["A", "B", "C"], get_title_matched_terms("A 与 B 和 C", "A\tB C"))
        self.assertEqual(["A 与 B 和 C", "只含 A"], [item.title for item in sort_search_results(filtered, keyword="A\tB C")])

    def test_calculate_time_score(self):
        now = datetime.now()
        t_1day = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(500.0, calculate_time_score(t_1day))

    def test_calculate_keyword_score(self):
        self.assertEqual(420.0, calculate_keyword_score("周星驰电影合集"))
        score = calculate_keyword_score("繁花 4K 全集 完结")
        self.assertGreaterEqual(score, 600.0)

    def test_calculate_relevance_score(self):
        self.assertEqual(300.0, calculate_relevance_score("繁花", "繁花"))
        self.assertEqual(150.0, calculate_relevance_score("繁花 4K全集", "繁花"))
        self.assertEqual(80.0, calculate_relevance_score("【热播】繁花 2024", "繁花"))

    def test_sort_search_results_hot_priority(self):
        hot_item = SearchResultItem(source="hot", title="繁花", share_link="https://pan.quark.cn/s/hot1", cloud_name="夸克网盘")
        tg_item = SearchResultItem(source="tg", title="【4K全集完结原盘合集】繁花", share_link="https://pan.quark.cn/s/tg1", cloud_name="夸克网盘")
        sorted_res = sort_search_results([tg_item, hot_item], keyword="繁花")
        self.assertEqual("hot", sorted_res[0].source)

    def test_public_search_filters_cached_results_before_limit(self):
        set_cached_search_items("繁花", [
            SearchResultItem(source="hot", title="繁花 夸克一", share_link="https://pan.quark.cn/s/one", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="繁花 百度", share_link="https://pan.baidu.com/s/two", cloud_name="百度网盘"),
            SearchResultItem(source="other", title="繁花 夸克二", share_link="https://pan.quark.cn/s/three", cloud_name="夸克网盘"),
        ])

        success, _, results = search_public_resources(
            "繁花", limit=1, cloud_name="夸克网盘"
        )

        self.assertTrue(success)
        self.assertEqual(1, len(results))
        self.assertEqual("夸克网盘", results[0]["cloud_name"])


class LinkCheckerTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.checker = LinkChecker()
        with self.checker._cache_lock:
            self.checker._cache.clear()

    @patch("src.services.link_checker.requests.Session.post")
    @patch("src.services.link_checker.requests.Session.get")
    def test_check_quark_valid_and_invalid(self, mock_get, mock_post):
        token_resp = MagicMock()
        token_resp.json.return_value = {"code": 0, "data": {"stoken": "mock_token"}}
        mock_post.return_value = token_resp

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "code": 0, "data": {"list": [{"file_name": "test.mp4"}], "share": {"status": 1, "partial_violation": False}, "is_expire": False},
        }
        mock_get.return_value = detail_resp

        res = self.checker.check_link("https://pan.quark.cn/s/validquark123")
        self.assertEqual(STATE_OK, res["state"])

    @patch("src.services.link_checker.requests.Session.post")
    def test_check_aliyun(self, mock_post):
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"share_name": "流浪地球", "file_count": 2, "share_status": "enabled"}
        mock_post.return_value = ok_resp

        res = self.checker.check_link("https://www.alipan.com/s/alivalid123")
        self.assertEqual(STATE_OK, res["state"])


if __name__ == "__main__":
    unittest.main()
