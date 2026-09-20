import logging
import re
from typing import Any, Dict, List, Optional

from src.services.system_config_service import get_ad_filter_config

logger = logging.getLogger(__name__)


def is_ad_filename(filename: str, extra_keywords: Optional[List[str]] = None) -> bool:
    """
    判断文件名是否命中广告/引流关键词。
    若系统配置启用了广告过滤，则使用配置中的词库进行比对；
    也可传入 extra_keywords 进行额外追加匹配。
    """
    if not filename:
        return False

    clean_name = str(filename).strip().lower()
    if not clean_name:
        return False

    config = get_ad_filter_config()
    if not config.get("enabled", True):
        return False

    keywords = set(config.get("keywords", []))
    if extra_keywords:
        keywords.update(str(k).strip().lower() for k in extra_keywords if str(k).strip())

    for kw in keywords:
        if kw and kw in clean_name:
            logger.debug(f"文件名 '{filename}' 命中广告关键词: {kw}")
            return True

    return False
