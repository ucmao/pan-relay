import unittest
from unittest.mock import MagicMock

from src.clients import (
    AliyunPanClient,
    BaiduPanClient,
    BasePanClient,
    QuarkPanClient,
    UcPanClient,
    XunleiPanClient,
)
from src.models.search_item import SearchResultItem
from src.services import search_service


class Phase3ModelsAndClientsTest(unittest.TestCase):
    def test_client_inheritance(self):
        # 验证所有网盘客户端均继承自 BasePanClient
        clients = [
            BaiduPanClient,
            QuarkPanClient,
            AliyunPanClient,
            UcPanClient,
            XunleiPanClient,
        ]
        for client_cls in clients:
            self.assertTrue(
                issubclass(client_cls, BasePanClient),
                f"{client_cls.__name__} 应该继承自 BasePanClient",
            )

    def test_base_client_alias_methods(self):
        # 验证 delete_file 和 transfer_and_share 别名方法
        class MockClient(BasePanClient):
            def store(self, share_url, to_pdir_path="/"):
                return ("fid", "name", "new_url")

            def del_file(self, file_ids):
                return True

        client = MockClient()
        self.assertEqual(("fid", "name", "new_url"), client.transfer_and_share("http://url"))
        self.assertTrue(client.delete_file(["fid"]))

    def test_search_result_item_attributes_and_sequence_protocol(self):
        item = SearchResultItem(
            source="hot",
            title="流浪地球2",
            share_link="https://pan.quark.cn/s/test1234",
            cloud_name="夸克网盘",
            password="abcd",
        )

        # 1. 属性访问
        self.assertEqual("hot", item.source)
        self.assertEqual("流浪地球2", item.title)
        self.assertEqual("https://pan.quark.cn/s/test1234", item.share_link)
        self.assertEqual("夸克网盘", item.cloud_name)
        self.assertEqual("abcd", item.password)

        # 2. 兼容属性别名
        self.assertEqual(item.share_link, item.url)
        self.assertEqual(item.cloud_name, item.netdisk_name)

        # 3. 序列下标解包协议
        self.assertEqual("hot", item[0])
        self.assertEqual("流浪地球2", item[1])
        self.assertEqual("https://pan.quark.cn/s/test1234", item[2])
        self.assertEqual("夸克网盘", item[3])
        self.assertEqual(4, len(item))

        # 4. 支持元组解包
        source, title, url, netdisk = item
        self.assertEqual("hot", source)
        self.assertEqual("流浪地球2", title)
        self.assertEqual("https://pan.quark.cn/s/test1234", url)
        self.assertEqual("夸克网盘", netdisk)

        # 5. to_list (供前端 SSE 流序列化)
        lst = item.to_list()
        self.assertEqual(["hot", "流浪地球2", "https://pan.quark.cn/s/test1234", "夸克网盘"], lst)

        # 6. to_dict (供公开 REST API /api 序列化)
        dct = item.to_dict()
        self.assertEqual("hot", dct["source"])
        self.assertEqual("流浪地球2", dct["name"])
        self.assertEqual("https://pan.quark.cn/s/test1234", dct["share_link"])
        self.assertEqual("夸克网盘", dct["cloud_name"])
        self.assertEqual("abcd", dct["password"])

    def test_search_result_item_from_item(self):
        # 从 tuple 构造
        item_from_tuple = SearchResultItem.from_item(
            ["tg", "大奉打更人", "https://pan.baidu.com/s/xyz", "百度网盘"]
        )
        self.assertIsInstance(item_from_tuple, SearchResultItem)
        self.assertEqual("tg", item_from_tuple.source)
        self.assertEqual("大奉打更人", item_from_tuple.title)

        # 从 dict 构造
        item_from_dict = SearchResultItem.from_item(
            {"source": "api", "name": "庆余年", "share_link": "https://pan.uc.cn/s/uc123", "cloud_name": "UC网盘"}
        )
        self.assertIsInstance(item_from_dict, SearchResultItem)
        self.assertEqual("api", item_from_dict.source)
        self.assertEqual("庆余年", item_from_dict.title)
        self.assertEqual("https://pan.uc.cn/s/uc123", item_from_dict.share_link)

    def test_clean_and_extract_data_returns_search_result_items(self):
        raw_data = [
            ["other", "<b>凡人修仙传</b> 4K", "https://pan.quark.cn/s/qk1234"],
        ]
        cleaned = search_service.clean_and_extract_data(raw_data)
        self.assertEqual(1, len(cleaned))
        item = cleaned[0]
        self.assertIsInstance(item, SearchResultItem)
        self.assertEqual("other", item.source)
        self.assertEqual("凡人修仙传 4K", item.title)
        self.assertEqual("夸克网盘", item.cloud_name)


if __name__ == "__main__":
    unittest.main()
