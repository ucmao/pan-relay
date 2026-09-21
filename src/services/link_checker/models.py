# src/services/link_checker/models.py

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class CheckResult:
    """
    网盘健康检测结构化结果
    """
    state: str                 # ok | bad | locked | uncertain | unsupported
    summary: str               # 状态文字说明
    url: str                   # 待检测的原始链接
    disk_type: str             # 网盘平台分类 (如 "quark", "baidu", "aliyun")
    canonical_key: str         # 规范化资源唯一指纹 (如 "quark:c502b66a87c5")
    file_count: Optional[int] = None   # 探测到的文件数量 (若可解析)
    checked_at: int = 0        # 探测时间戳 (秒)
    cache_hit: bool = False    # 是否命中缓存

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d
