import unittest

from src.services.telegram_search_service import (
    clean_telegram_title,
    extract_title_from_link_line,
    is_cloud_disk_label,
    parse_telegram_search_html,
)

MULTI_RESOURCE_HTML = """
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="tgchannel/101">
    <div class="tgme_widget_message_date">
      <time datetime="2026-03-01T10:00:00+00:00"></time>
    </div>
    <div class="tgme_widget_message_text">
      🎬 【片名】：庆余年 第二季 (2024) 4K | @tgsearchers #国剧<br>
      夸克网盘：https://pan.quark.cn/s/qingyunian_quark<br>
      阿里云盘：https://www.alipan.com/s/qingyunian_ali<br>
      <br>
      🎬 剧名：繁花 (2023) 4K 杜比视界<br>
      夸克网盘：https://pan.quark.cn/s/fanhua_quark<br>
      百度网盘：https://pan.baidu.com/s/fanhua_baidu<br>
      提取码：7788<br>
    </div>
  </div>
</div>
"""

COMPOUND_LINE_HTML = """
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="tgchannel/102">
    <div class="tgme_widget_message_text">
      【热播短剧大合集】<br>
      重生之都市修仙：https://pan.quark.cn/s/duxiu123<br>
      绝世武神 4K：https://pan.baidu.com/s/wushen456 提取码: ab12<br>
    </div>
  </div>
</div>
"""


class TelegramParserTest(unittest.TestCase):
    def test_clean_telegram_title(self):
        # 1. 片名前缀、表情与频道水印清理
        dirty1 = "🎬 【片名】：繁花 (2023) 4K | 关注频道 @pansearch #国剧 #王家卫"
        self.assertEqual("繁花 (2023) 4K", clean_telegram_title(dirty1))

        # 2. 纯前缀冒号清理
        dirty2 = "名称：周星驰电影合集"
        self.assertEqual("周星驰电影合集", clean_telegram_title(dirty2))

        # 3. 剧名前缀与 Emoji 清理
        dirty3 = "🏷️ 剧名: 庆余年 第二季"
        self.assertEqual("庆余年 第二季", clean_telegram_title(dirty3))

        # 4. 短剧名称前缀清理
        dirty4 = "【短剧名称】 重生之我在古代当首富"
        self.assertEqual("重生之我在古代当首富", clean_telegram_title(dirty4))

    def test_is_cloud_disk_label(self):
        self.assertTrue(is_cloud_disk_label("夸克网盘"))
        self.assertTrue(is_cloud_disk_label("百度云"))
        self.assertTrue(is_cloud_disk_label("资源地址"))
        self.assertTrue(is_cloud_disk_label("【网盘链接】"))
        self.assertFalse(is_cloud_disk_label("繁花"))
        self.assertFalse(is_cloud_disk_label("周星驰电影合集"))

    def test_extract_title_from_link_line(self):
        # 1. 复合行标题拆解
        line1 = "重生之都市修仙：https://pan.quark.cn/s/111"
        self.assertEqual("重生之都市修仙", extract_title_from_link_line(line1))

        # 2. 纯网盘前缀行不应作为标题
        line2 = "夸克网盘：https://pan.quark.cn/s/111"
        self.assertIsNone(extract_title_from_link_line(line2))

        # 3. 空格直接跟链接
        line3 = "绝世武神 4K https://pan.quark.cn/s/222"
        self.assertEqual("绝世武神 4K", extract_title_from_link_line(line3))

    def test_multi_resource_message_pairing(self):
        """测试长帖中包含多个不同影视资源时，标题不串味，密码各自精确绑定"""
        results = parse_telegram_search_html(MULTI_RESOURCE_HTML, "tgchannel")
        self.assertEqual(4, len(results))

        # 验证前两个资源属于《庆余年 第二季 (2024) 4K》
        qyn_quark = results[0]
        self.assertEqual("庆余年 第二季 (2024) 4K", qyn_quark.title)
        self.assertEqual("https://pan.quark.cn/s/qingyunian_quark", qyn_quark.share_link)
        self.assertEqual("夸克网盘", qyn_quark.cloud_name)
        self.assertEqual("2026-03-01T10:00:00+00:00", qyn_quark.datetime)

        qyn_ali = results[1]
        self.assertEqual("庆余年 第二季 (2024) 4K", qyn_ali.title)
        self.assertEqual("https://www.alipan.com/s/qingyunian_ali", qyn_ali.share_link)
        self.assertEqual("阿里云盘", qyn_ali.cloud_name)

        # 验证后两个资源属于《繁花 (2023) 4K 杜比视界》，且百度网盘精准绑定提取码 7788
        fh_quark = results[2]
        self.assertEqual("繁花 (2023) 4K 杜比视界", fh_quark.title)
        self.assertEqual("https://pan.quark.cn/s/fanhua_quark", fh_quark.share_link)

        fh_baidu = results[3]
        self.assertEqual("繁花 (2023) 4K 杜比视界", fh_baidu.title)
        self.assertEqual("https://pan.baidu.com/s/fanhua_baidu?pwd=7788", fh_baidu.share_link)
        self.assertEqual("7788", fh_baidu.password)

    def test_compound_line_list_pairing(self):
        """测试单行复合排版短剧列表"""
        results = parse_telegram_search_html(COMPOUND_LINE_HTML, "tgchannel")
        self.assertEqual(2, len(results))

        item1 = results[0]
        self.assertEqual("重生之都市修仙", item1.title)
        self.assertEqual("https://pan.quark.cn/s/duxiu123", item1.share_link)

        item2 = results[1]
        self.assertEqual("绝世武神 4K", item2.title)
        self.assertEqual("https://pan.baidu.com/s/wushen456?pwd=ab12", item2.share_link)
        self.assertEqual("ab12", item2.password)


if __name__ == "__main__":
    unittest.main()
