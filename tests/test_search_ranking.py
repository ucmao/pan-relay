import unittest
from datetime import datetime, timedelta

from src.models.search_item import SearchResultItem
from src.services.search_service import (
    calculate_keyword_score,
    calculate_rank_score,
    calculate_relevance_score,
    calculate_time_score,
    sort_search_results,
)


class SearchRankingTest(unittest.TestCase):
    def test_calculate_time_score(self):
        now = datetime.now()

        # 1. 1天内 (500分)
        t_1day = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(500.0, calculate_time_score(t_1day))

        # 2. 3天内 (400分)
        t_2day = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(400.0, calculate_time_score(t_2day))

        # 3. 7天内 (300分)
        t_5day = (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(300.0, calculate_time_score(t_5day))

        # 4. 1年以上 (20分)
        t_old = (now - timedelta(days=400)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(20.0, calculate_time_score(t_old))

        # 5. 无时间但包含当前年份兜底 (80分)
        curr_year = str(now.year)
        self.assertEqual(80.0, calculate_time_score(None, f"繁花 {curr_year} 4K"))

    def test_calculate_keyword_score(self):
        # 1. 合集 (420分)
        self.assertEqual(420.0, calculate_keyword_score("周星驰电影合集"))

        # 2. 4K 全集完结 (180 + 280 + 210 = 600上限)
        score = calculate_keyword_score("繁花 4K 全集 完结")
        self.assertGreaterEqual(score, 600.0)

        # 3. 无特征词
        self.assertEqual(0.0, calculate_keyword_score("测试文档"))

    def test_calculate_relevance_score(self):
        # 完全匹配 (300分)
        self.assertEqual(300.0, calculate_relevance_score("繁花", "繁花"))
        # 前缀匹配 (150分)
        self.assertEqual(150.0, calculate_relevance_score("繁花 4K全集", "繁花"))
        # 包含匹配 (80分)
        self.assertEqual(80.0, calculate_relevance_score("【热播】繁花 2024", "繁花"))
        # 不匹配 (0分)
        self.assertEqual(0.0, calculate_relevance_score("大奉打更人", "繁花"))

    def test_sort_search_results_hot_priority(self):
        # 内部收益盘 (hot) 即使标题简略也必须绝对排在首位
        hot_item = SearchResultItem(
            source="hot",
            title="繁花",
            share_link="https://pan.quark.cn/s/hot1",
            cloud_name="夸克网盘",
        )
        tg_item = SearchResultItem(
            source="tg",
            title="【4K全集完结原盘合集】繁花",
            share_link="https://pan.quark.cn/s/tg1",
            cloud_name="夸克网盘",
        )

        sorted_res = sort_search_results([tg_item, hot_item], keyword="繁花")
        self.assertEqual("hot", sorted_res[0].source)
        self.assertEqual("tg", sorted_res[1].source)

    def test_sort_search_results_quality_and_freshness(self):
        now = datetime.now()
        t_recent = (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        t_old = (now - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")

        # 1. 普通低质单集、时间陈旧
        low_quality = SearchResultItem(
            source="tg",
            title="繁花 第01集",
            share_link="https://pan.quark.cn/s/low1",
            cloud_name="夸克网盘",
            datetime=t_old,
        )

        # 2. 4K全集完结、新鲜发布、带密码
        high_quality = SearchResultItem(
            source="tg",
            title="繁花 4K全集 完结",
            share_link="https://pan.quark.cn/s/high1?pwd=8888",
            cloud_name="夸克网盘",
            password="8888",
            datetime=t_recent,
        )

        # 3. 占位劣质标题
        junk_item = SearchResultItem(
            source="tg",
            title="Telegram 频道资源",
            share_link="https://pan.quark.cn/s/junk1",
            cloud_name="夸克网盘",
        )

        sorted_res = sort_search_results([low_quality, junk_item, high_quality], keyword="繁花")

        # 高质新鲜资源排第1
        self.assertEqual("https://pan.quark.cn/s/high1?pwd=8888", sorted_res[0].share_link)
        # 普通单集排第2
        self.assertEqual("https://pan.quark.cn/s/low1", sorted_res[1].share_link)
        # 劣质占位标题排最后
        self.assertEqual("https://pan.quark.cn/s/junk1", sorted_res[2].share_link)


if __name__ == "__main__":
    unittest.main()
