from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.models.search_item import SearchResultItem

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """
    pan-relay 统一搜索插件抽象基类。
    所有自定义数据源插件（HTML 爬虫、复杂加密 API、多步鉴权源等）均继承此类。
    """

    # 插件唯一英文标识符（如 'panwiki', 'qupanshe', 'xb6v'）
    name: str = "base_plugin"

    # 插件人类可读的中文显示名称
    display_name: str = "基础插件"

    # 插件版本号
    version: str = "1.0.0"

    # 插件作者
    author: str = "pan-relay"

    # 插件描述与数据源说明
    description: str = ""

    # 插件层级与打分权重（默认 100 分，高质量源可设为 150~200 分）
    priority: int = 100

    # 默认是否启用
    is_enabled: bool = True

    # 健康检测通过后是否允许进入新安装的默认启用列表；演示插件可关闭此项。
    publish_by_default: bool = True

    # 搜索超时时间（秒）
    timeout: float = 6.0

    def __init__(self):
        pass

    @abstractmethod
    def search(self, keyword: str) -> List[SearchResultItem]:
        """
        根据关键词执行搜索，返回标准领域模型 SearchResultItem 列表。
        必须保证在发生异常时内部捕获或由上层捕获，不影响其他插件。
        """
        pass

    def health_check(self) -> Tuple[bool, str]:
        """
        插件健康度与连通性检查。
        子类可重写此方法发起轻量探测，默认返回 True。
        """
        return True, "OK"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为管理 API 接口所需的元数据字典"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "priority": self.priority,
            "is_enabled": self.is_enabled,
            "publish_by_default": self.publish_by_default,
            "timeout": self.timeout,
        }
