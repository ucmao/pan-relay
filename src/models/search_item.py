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
    datetime: Optional[str] = None  # 发布时间/创建时间 (可选)
    description: Optional[str] = None  # 资源简介/内容描述 (可选)
    cover_url: Optional[str] = None  # 封面图片/缩略图 (可选)

    @property
    def url(self) -> str:
        """向后兼容 share_link 的别名"""
        return self.share_link

    @property
    def netdisk_name(self) -> str:
        """向后兼容 cloud_name 的别名"""
        return self.cloud_name

    @property
    def drive_type(self) -> str:
        """推导统一的英文驱动代号 (quark, baidu, ali, uc, xunlei, seed 等)"""
        from src.utils.netdisk_utils import get_netdisk_drive_type
        return get_netdisk_drive_type(self.cloud_name, self.share_link)

    def to_list(self) -> List[str]:
        """
        转换为传统 4 项元组列表形式:
        [source, title, url, netdisk_name]
        保持精准的 4 项元组解包兼容性。
        """
        return [self.source, self.title, self.share_link, self.cloud_name]

    def to_front_list(self) -> List[str]:
        """
        转换为前端卡片渲染与 SSE 流使用的完整序列:
        [source, title, url, netdisk_name, datetime, description, cover_url]
        """
        return [
            self.source,
            self.title,
            self.share_link,
            self.cloud_name,
            self.datetime or "",
            self.description or "",
            self.cover_url or "",
        ]

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为公开 REST API JSON 格式 (包含丰富的 drive_type 字段)
        """
        res = {
            "source": self.source,
            "title": self.title,
            "name": self.title,
            "share_link": self.share_link,
            "url": self.share_link,
            "cloud_name": self.cloud_name,
            "drive_type": self.drive_type,
        }
        if self.password:
            res["password"] = self.password
        if self.datetime:
            res["datetime"] = self.datetime
        if self.description:
            res["description"] = self.description
        if self.cover_url:
            res["cover_url"] = self.cover_url
            res["image"] = self.cover_url
            res["cover"] = self.cover_url
        return res

    def __getitem__(self, index: int) -> str:
        """支持 item[0]..item[3] 下标访问与元素解包，同时兼容访问扩展字段"""
        if index < 4:
            return self.to_list()[index]
        return self.to_front_list()[index]

    def __iter__(self):
        """保证元组解包 (source, title, url, netdisk = item) 时始终解包核心 4 项，100% 兼容旧代码"""
        return iter(self.to_list())

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
            dt = str(item[4]) if len(item) > 4 and item[4] else None
            desc = str(item[5]) if len(item) > 5 and item[5] else None
            cover = str(item[6]) if len(item) > 6 and item[6] else None
            return cls(
                source=source,
                title=title,
                share_link=url,
                cloud_name=netdisk,
                datetime=dt,
                description=desc,
                cover_url=cover,
            )
        if isinstance(item, dict):
            source = item.get("source", "other")
            title = item.get("name") or item.get("title", "")
            url = item.get("share_link") or item.get("url", "")
            netdisk = item.get("cloud_name") or item.get("netdisk_name", "")
            pwd = item.get("password") or item.get("pwd") or item.get("disk_pass")
            dt = item.get("datetime") or item.get("created_at") or item.get("time") or item.get("shared_time")
            desc = (
                item.get("description")
                or item.get("remarks")
                or item.get("summary")
                or item.get("intro")
                or item.get("content")
                or item.get("desc")
            )
            cover = (
                item.get("cover_url")
                or item.get("cover")
                or item.get("image_url")
                or item.get("image")
                or item.get("thumb")
                or item.get("thumbnail")
                or item.get("poster")
                or item.get("pic")
            )
            return cls(
                source=source,
                title=title,
                share_link=url,
                cloud_name=netdisk,
                password=pwd,
                datetime=dt,
                description=desc,
                cover_url=cover,
            )
        raise ValueError(f"无法转换为 SearchResultItem: {item}")
