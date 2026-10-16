import unittest
from src.models.search_item import SearchResultItem
from src.services.search_service import calculate_completeness_score, merge_or_select_better
from src.services.telegram_search_service import _extract_telegram_cover
from bs4 import BeautifulSoup


class UIPaginationAndMetaFieldsTestCase(unittest.TestCase):
    def test_search_item_serialization_with_cover(self):
        item = SearchResultItem(
            source="test_plugin",
            title="测试电影 4K",
            share_link="https://pan.quark.cn/s/test123456",
            cloud_name="夸克网盘",
            datetime="2026-10-16 20:30",
            description="这是一部高清测试影片的剧情简介",
            cover_url="https://img.example.com/poster.jpg",
        )
        # Test to_front_list 7-element format
        front_list = item.to_front_list()
        self.assertEqual(len(front_list), 7)
        self.assertEqual(front_list[0], "test_plugin")
        self.assertEqual(front_list[1], "测试电影 4K")
        self.assertEqual(front_list[2], "https://pan.quark.cn/s/test123456")
        self.assertEqual(front_list[3], "夸克网盘")
        self.assertEqual(front_list[4], "2026-10-16 20:30")
        self.assertEqual(front_list[5], "这是一部高清测试影片的剧情简介")
        self.assertEqual(front_list[6], "https://img.example.com/poster.jpg")

        # Test from_item tuple reconstruction
        reconstructed = SearchResultItem.from_item(front_list)
        self.assertEqual(reconstructed.cover_url, "https://img.example.com/poster.jpg")
        self.assertEqual(reconstructed.description, "这是一部高清测试影片的剧情简介")
        self.assertEqual(reconstructed.datetime, "2026-10-16 20:30")

    def test_completeness_score_with_cover_and_desc(self):
        item_rich = SearchResultItem(
            source="rich",
            title="电影 4K 原盘",
            share_link="https://pan.quark.cn/s/rich",
            cloud_name="夸克网盘",
            datetime="2026-10-16",
            description="详细电影剧情简介",
            cover_url="https://img.example.com/cover.jpg",
        )
        item_plain = SearchResultItem(
            source="plain",
            title="电影 4K 原盘",
            share_link="https://pan.quark.cn/s/plain",
            cloud_name="夸克网盘",
        )
        score_rich = calculate_completeness_score(item_rich)
        score_plain = calculate_completeness_score(item_plain)
        # Rich item must have higher score due to cover_url, description, datetime
        self.assertGreater(score_rich, score_plain)

    def test_merge_or_select_better_inherits_fields(self):
        item1 = SearchResultItem(
            source="source1",
            title="长津湖 2021",
            share_link="https://pan.quark.cn/s/same_link",
            cloud_name="夸克网盘",
            datetime="2026-10-16",
            description="",
            cover_url="",
        )
        item2 = SearchResultItem(
            source="source2",
            title="长津湖 2021 4K HDR",
            share_link="https://pan.quark.cn/s/same_link",
            cloud_name="夸克网盘",
            datetime="",
            description="抗美援朝史诗大片",
            cover_url="https://example.com/changjinhu.jpg",
        )
        merged = merge_or_select_better(item1, item2)
        # Inherits datetime from item1 and description + cover_url from item2
        self.assertEqual(merged.datetime, "2026-10-16")
        self.assertEqual(merged.description, "抗美援朝史诗大片")
        self.assertEqual(merged.cover_url, "https://example.com/changjinhu.jpg")

    def test_telegram_cover_extractor(self):
        html = """
        <div class="tgme_widget_message">
            <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn.telegram.org/file/poster123.jpg')"></a>
            <div class="tgme_widget_message_text">
                【影片名称】: 凡人修仙传<br>
                【剧情简介】: 普通山村少年韩立，偶然之下跨入修仙门派...<br>
                https://pan.quark.cn/s/fanren123
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        msg_el = soup.find("div", class_="tgme_widget_message")
        cover = _extract_telegram_cover(msg_el)
        self.assertEqual(cover, "https://cdn.telegram.org/file/poster123.jpg")


if __name__ == "__main__":
    unittest.main()
