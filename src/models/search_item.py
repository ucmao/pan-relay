from dataclasses import dataclass, field
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
    source_type: Optional[str] = None  # 统一来源类别: internal / telegram / plugin / api
    source_id: Optional[str] = None  # 具体来源标识: 频道用户名、插件 ID 或 API ID
    source_name: Optional[str] = None  # 来源的人类可读名称
    metadata: Dict[str, Any] = field(default_factory=dict)  # 经清洗的来源扩展字段

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

    @property
    def source_display(self) -> str:
        """前端来源类别显示名；具体来源由 source_id/source_name 独立承载。"""
        labels = {
            "internal": "站长自建",
            "telegram": "TG",
            "plugin": "插件",
            "api": "API",
        }
        return labels.get(self.normalized_source_type, "网络聚合")

    @property
    def normalized_source_type(self) -> str:
        value = str(self.source_type or self.source or "").strip().lower()
        if value == "hot":
            return "internal"
        if value in ("tg", "telegram") or value.startswith("tg:") or value.startswith("telegram:"):
            return "telegram"
        if value == "plugin" or value.startswith("plugin:"):
            return "plugin"
        if value in ("other", "api") or value.startswith("api:"):
            return "api"
        if value in ("internal", "telegram", "plugin", "api"):
            return value
        return ""

    def to_list(self) -> List[str]:
        """
        转换为传统 4 项元组列表形式:
        [source, title, url, netdisk_name]
        保持精准的 4 项元组解包兼容性。
        """
        return [self.source, self.title, self.share_link, self.cloud_name]

    def to_front_list(self) -> List[str]:
        """返回兼容旧版前端字段的完整序列，并附带来源与扩展信息。"""
        return [
            self.source,
            self.title,
            self.share_link,
            self.cloud_name,
            self.datetime or "",
            self.description or "",
            self.cover_url or "",
            self.normalized_source_type,
            self.source_id or "",
            self.source_name or "",
            _sanitize_metadata(self.metadata),
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
            "source_type": self.normalized_source_type or "unknown",
            "source_display": self.source_display,
        }
        if self.source_id:
            res["source_id"] = self.source_id
        if self.source_name:
            res["source_name"] = self.source_name
        if self.metadata:
            res["metadata"] = _sanitize_metadata(self.metadata)
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
            source_type = str(item[7]) if len(item) > 7 and item[7] else None
            source_id = str(item[8]) if len(item) > 8 and item[8] else None
            source_name = str(item[9]) if len(item) > 9 and item[9] else None
            metadata = item[10] if len(item) > 10 and isinstance(item[10], dict) else {}
            if not source_id and ":" in source:
                source_id = source.split(":", 1)[1]
            return cls(
                source=source,
                title=title,
                share_link=url,
                cloud_name=netdisk,
                datetime=dt,
                description=desc,
                cover_url=cover,
                source_type=source_type,
                source_id=source_id,
                source_name=source_name,
                metadata=metadata,
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
            source_type = item.get("source_type")
            source_id = item.get("source_id")
            source_name = item.get("source_name")
            known_fields = {
                "source", "source_type", "source_id", "source_name", "source_display",
                "title", "name", "share_link", "url", "cloud_name", "netdisk_name",
                "password", "pwd", "disk_pass", "datetime", "created_at", "time",
                "shared_time", "description", "remarks", "summary", "intro", "content",
                "desc", "cover_url", "cover", "image_url", "image", "thumb",
                "thumbnail", "poster", "pic", "metadata", "extra",
            }
            metadata = item.get("metadata") or item.get("extra") or {
                key: value for key, value in item.items()
                if key not in known_fields and not _is_sensitive_metadata_key(key)
            }
            if not source_id:
                raw_source = str(source or "")
                if ":" in raw_source:
                    source_id = raw_source.split(":", 1)[1]
            return cls(
                source=source,
                title=title,
                share_link=url,
                cloud_name=netdisk,
                password=pwd,
                datetime=dt,
                description=desc,
                cover_url=cover,
                source_type=source_type,
                source_id=str(source_id) if source_id else None,
                source_name=str(source_name) if source_name else None,
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        raise ValueError(f"无法转换为 SearchResultItem: {item}")


def _is_sensitive_metadata_key(key: Any) -> bool:
    value = str(key or "").lower().replace("-", "_")
    return any(part in value for part in ("token", "secret", "authorization", "cookie", "credential", "api_key", "password", "passwd"))


def _sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_metadata(item)
            for key, item in value.items()
            if not _is_sensitive_metadata_key(key)
        }
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    return value
