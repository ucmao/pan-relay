from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SearchResultItem:
    """
    搜索结果领域模型。
    支持强类型属性访问，同时实现序列协议以保证 100% 向后兼容：
    - item[0]: source
    - item[1]: title
    - item[2]: share_link (url)
    - item[3]: cloud_name (netdisk_name)
    """

    source: str  # 来源: "hot" (内部库) / "tg" (Telegram) / "other" (第三方 API)
    title: str  # 资源标题
    share_link: str  # 网盘分享链接
    cloud_name: str  # 网盘平台名称 (如: "夸克网盘", "百度网盘")
    password: Optional[str] = None  # 提取码 (可选)

    @property
    def url(self) -> str:
        """向后兼容 share_link 的别名"""
        return self.share_link

    @property
    def netdisk_name(self) -> str:
        """向后兼容 cloud_name 的别名"""
        return self.cloud_name

    def to_list(self) -> List[str]:
        """
        转换为前端 SSE 流及传统列表形式:
        [source, title, url, netdisk_name]
        """
        return [self.source, self.title, self.share_link, self.cloud_name]

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为公开 REST API JSON 格式:
        {"source": ..., "name": ..., "share_link": ..., "cloud_name": ...}
        """
        res = {
            "source": self.source,
            "name": self.title,
            "share_link": self.share_link,
            "cloud_name": self.cloud_name,
        }
        if self.password:
            res["password"] = self.password
        return res

    def __getitem__(self, index: int) -> str:
        """支持 item[0]..item[3] 下标访问与元素解包"""
        return self.to_list()[index]

    def __len__(self) -> int:
        return 4

    @classmethod
    def from_item(cls, item: Any) -> "SearchResultItem":
        """
        自适应转换：从 tuple/list/dict 或已有实例安全构造 SearchResultItem
        """
        if isinstance(item, cls):
            return item
        if isinstance(item, (list, tuple)):
            source = str(item[0]) if len(item) > 0 else "other"
            title = str(item[1]) if len(item) > 1 else ""
            url = str(item[2]) if len(item) > 2 else ""
            netdisk = str(item[3]) if len(item) > 3 else ""
            return cls(source=source, title=title, share_link=url, cloud_name=netdisk)
        if isinstance(item, dict):
            source = item.get("source", "other")
            title = item.get("name") or item.get("title", "")
            url = item.get("share_link") or item.get("url", "")
            netdisk = item.get("cloud_name") or item.get("netdisk_name", "")
            return cls(source=source, title=title, share_link=url, cloud_name=netdisk)
        raise ValueError(f"无法转换为 SearchResultItem: {item}")
