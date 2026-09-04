import unittest

from src.models.search_item import SearchResultItem
from src.services.search_service import (
    calculate_completeness_score,
    dedupe_search_results,
    merge_or_select_better,
)
from src.utils.netdisk_utils import (
    extract_canonical_resource_key,
    extract_password_from_url,
)


class SearchDeduplicationTest(unittest.TestCase):
    def test_canonical_resource_key_extraction(self):
        # 1. 夸克网盘
        self.assertEqual(
            "quark:c502b66a87c5",
            extract_canonical_resource_key("https://pan.quark.cn/s/c502b66a87c5#/list/share"),
        )
        self.assertEqual(
            "quark:c502b66a87c5",
            extract_canonical_resource_key("https://pan.quark.cn/s/c502b66a87c5?from=feed"),
        )

        # 2. 百度网盘
        self.assertEqual(
            "baidu:1abcdefg",
            extract_canonical_resource_key("https://pan.baidu.com/s/1abcdefg?pwd=1234"),
        )
        self.assertEqual(
            "baidu:1abcdefg",
            extract_canonical_resource_key("https://bdpan.com/s/1abcdefg"),
        )

        # 3. 阿里云盘 (alipan.com 和 aliyundrive.com 归一化为同一个 key)
        self.assertEqual(
            "aliyun:xyz123",
            extract_canonical_resource_key("https://www.alipan.com/s/xyz123"),
        )
        self.assertEqual(
            "aliyun:xyz123",
            extract_canonical_resource_key("https://www.aliyundrive.com/s/xyz123?spm=123"),
        )

        # 4. UC网盘
        self.assertEqual(
            "uc:abc123",
            extract_canonical_resource_key("https://drive.uc.cn/s/abc123?public=1"),
        )
        self.assertEqual(
            "uc:abc123",
            extract_canonical_resource_key("https://pan.uc.cn/s/abc123"),
        )

        # 5. 迅雷网盘
        self.assertEqual(
            "xunlei:VM-12345",
            extract_canonical_resource_key("https://pan.xunlei.com/s/VM-12345"),
        )

        # 6. 123云盘
        self.assertEqual(
            "123pan:abcd-1234",
            extract_canonical_resource_key("https://www.123pan.com/s/abcd-1234"),
        )
        self.assertEqual(
            "123pan:abcd-1234",
            extract_canonical_resource_key("https://www.123pan.cn/s/abcd-1234"),
        )
        self.assertEqual(
            "123pan:abcd-1234",
            extract_canonical_resource_key("https://123684.com/s/abcd-1234"),
        )

        # 7. 天翼云盘
        self.assertEqual(
            "tianyi:xyz789",
            extract_canonical_resource_key("https://cloud.189.cn/t/xyz789"),
        )

        # 8. 115网盘
        self.assertEqual(
            "115:sw34567",
            extract_canonical_resource_key("https://115.com/s/sw34567?password=abcd"),
        )

        # 9. 移动云盘
        self.assertEqual(
            "mobile:mob123",
            extract_canonical_resource_key("https://caiyun.139.com/w/i/mob123"),
        )
        self.assertEqual(
            "mobile:mob123",
            extract_canonical_resource_key("https://caiyun.feixin.10086.cn/mob123"),
        )

        # 10. PikPak
        self.assertEqual(
            "pikpak:pk123",
            extract_canonical_resource_key("https://mypikpak.com/s/pk123"),
        )

        # 11. 新增网盘类型 (蓝奏云, 光鸭云盘, 腾讯微云, 坚果云)
        self.assertEqual(
            "lanzou:lz123",
            extract_canonical_resource_key("https://wwa.lanzoui.com/lz123"),
        )
        self.assertEqual(
            "guangya:gy123",
            extract_canonical_resource_key("https://guangyapan.com/s/gy123"),
        )
        self.assertEqual(
            "weiyun:wy123",
            extract_canonical_resource_key("https://weiyun.com/wy123"),
        )
        self.assertEqual(
            "jianguoyun:jgy123",
            extract_canonical_resource_key("https://jianguoyun.com/p/jgy123"),
        )

        # 12. 磁力与电驴
        self.assertEqual(
            "magnet:a1b2c3d4e5f6",
            extract_canonical_resource_key("magnet:?xt=urn:btih:A1B2C3D4E5F6&dn=Ubuntu"),
        )

    def test_match_netdisk_link(self):
        from src.utils.netdisk_utils import match_netdisk_link, FRONTEND_DISPLAY_NETDISK_OPTIONS

        self.assertEqual("蓝奏云", match_netdisk_link("https://wwa.lanzoui.com/b123456"))
        self.assertEqual("蓝奏云", match_netdisk_link("https://www.lanzoux.com/b123456"))
        self.assertEqual("光鸭云盘", match_netdisk_link("https://guangyapan.com/s/abc"))
        self.assertEqual("腾讯微云", match_netdisk_link("https://weiyun.com/abc"))
        self.assertEqual("坚果云", match_netdisk_link("https://jianguoyun.com/p/abc"))
        self.assertEqual("123云盘", match_netdisk_link("https://123pan.cn/s/abc"))
        self.assertEqual("PikPak", match_netdisk_link("https://mypikpak.com/s/abc"))
        self.assertEqual("移动云盘", match_netdisk_link("https://caiyun.feixin.10086.cn/abc"))

        self.assertEqual(20, len(FRONTEND_DISPLAY_NETDISK_OPTIONS) - 1)  # 不算"其他"共20种

    def test_extract_password_from_url(self):
        self.assertEqual("1234", extract_password_from_url("https://pan.baidu.com/s/xxx?pwd=1234"))
        self.assertEqual("abcd", extract_password_from_url("https://115.com/s/xxx?password=abcd"))
        self.assertEqual("8888", extract_password_from_url("https://pan.quark.cn/s/xxx?code=8888"))
        self.assertEqual("6666", extract_password_from_url("https://pan.baidu.com/s/xxx 提取码: 6666"))
        self.assertIsNone(extract_password_from_url("https://pan.quark.cn/s/xxx"))

    def test_different_links_with_same_title_are_not_deduped(self):
        # 核心验证：同名（如“繁花”）不同有效分享链必须全部保留！
        results = [
            SearchResultItem(source="tg", title="繁花", share_link="https://pan.quark.cn/s/share_aaa", cloud_name="夸克网盘"),
            SearchResultItem(source="tg", title="繁花", share_link="https://pan.quark.cn/s/share_bbb", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="繁花", share_link="https://pan.quark.cn/s/share_ccc", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="繁花", share_link="https://pan.baidu.com/s/share_ddd", cloud_name="百度网盘"),
        ]

        deduped = dedupe_search_results(results)

        # 4 个不同的网盘分享链接都应该被保留下来
        self.assertEqual(4, len(deduped))
        links = [item.share_link for item in deduped]
        self.assertIn("https://pan.quark.cn/s/share_aaa", links)
        self.assertIn("https://pan.quark.cn/s/share_bbb", links)
        self.assertIn("https://pan.quark.cn/s/share_ccc", links)
        self.assertIn("https://pan.baidu.com/s/share_ddd", links)

    def test_same_link_different_titles_dedupes_and_selects_better(self):
        # 相同网盘分享链接在多个爬虫/渠道出现时，成功去重并保留信息更丰富、标题更优质的条目
        results = [
            SearchResultItem(source="tg", title="繁花", share_link="https://pan.quark.cn/s/same_quark_id", cloud_name="夸克网盘"),
            SearchResultItem(source="other", title="【4K全集完结】繁花 国粤双语 2023", share_link="https://pan.quark.cn/s/same_quark_id?from=other", cloud_name="夸克网盘"),
        ]

        deduped = dedupe_search_results(results)

        self.assertEqual(1, len(deduped))
        # 质量更高的标题被选中
        self.assertEqual("【4K全集完结】繁花 国粤双语 2023", deduped[0].title)

    def test_same_link_preserves_password(self):
        # 如果先到的没有密码，后到的有密码，择优合并必须继承密码
        results = [
            SearchResultItem(source="tg", title="流浪地球2", share_link="https://pan.baidu.com/s/earth2_share", cloud_name="百度网盘"),
            SearchResultItem(source="other", title="流浪地球2", share_link="https://pan.baidu.com/s/earth2_share?pwd=8888", cloud_name="百度网盘", password="8888"),
        ]

        deduped = dedupe_search_results(results)

        self.assertEqual(1, len(deduped))
        self.assertEqual("8888", deduped[0].password)
        self.assertIn("pwd=8888", deduped[0].share_link)

    def test_hot_source_takes_highest_priority(self):
        # 内部库 (hot) 收益链接无论标题是否更短，必须优先胜出以保障变现收益
        results = [
            SearchResultItem(source="tg", title="【4K全网独播】庆余年2 超长标题", share_link="https://pan.quark.cn/s/qingyunian2", cloud_name="夸克网盘"),
            SearchResultItem(source="hot", title="庆余年2", share_link="https://pan.quark.cn/s/qingyunian2", cloud_name="夸克网盘"),
        ]

        deduped = dedupe_search_results(results)

        self.assertEqual(1, len(deduped))
        self.assertEqual("hot", deduped[0].source)


if __name__ == "__main__":
    unittest.main()
