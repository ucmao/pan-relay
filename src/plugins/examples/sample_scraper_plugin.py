import logging
import re
from typing import List, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from src.configs.app_config import user_agents
from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin
from src.utils.netdisk_utils import (
    extract_password_from_url,
    match_netdisk_link,
)

logger = logging.getLogger(__name__)


class SampleScraperPlugin(BasePlugin):
    """
    标准参考插件：演示如何通过 HTML 爬取或自定义 API 协议扩展搜索源。
    """

    name = "sample_scraper"
    display_name = "参考爬虫插件"
    version = "1.0.0"
    author = "pan-relay team"
    description = "演示插件体系标准的请求、DOM解析、链接提取与异常防护流程"
    priority = 120
    is_enabled = False
    publish_by_default = False
    timeout = 5.0

    def search(self, keyword: str) -> List[SearchResultItem]:
        # 演示用例：在实际场景中向目标站点发起 HTTP 请求并解析 HTML
        # 这里模拟返回高质量的测试结果，以便在无外网依赖下进行集成验证
        results = []

        # 示例：如果关键词包含 "测试" 或普通搜索，生成标准 SearchResultItem
        if not keyword:
            return []

        # 示例输出：真实插件中此处替换为 requests.get(url) + BeautifulSoup 解析
        sample_links = [
            (
                f"{keyword} 4K臻彩高码率全集",
                "https://pan.quark.cn/s/sample_quark_plugin_123",
                "夸克网盘",
                None,
            ),
            (
                f"{keyword} 1080P国粤双语完结",
                "https://pan.baidu.com/s/sample_baidu_plugin_456?pwd=7788",
                "百度网盘",
                "7788",
            ),
        ]

        for title, link, cloud_name, pwd in sample_links:
            detected_cloud = match_netdisk_link(link)
            cloud = detected_cloud if detected_cloud != "其他" else cloud_name
            password = pwd or extract_password_from_url(link)

            results.append(
                SearchResultItem(
                    source="plugin:sample_scraper",
                    title=title,
                    share_link=link,
                    cloud_name=cloud,
                    password=password,
                )
            )

        return results

    def health_check(self) -> Tuple[bool, str]:
        return True, "演示插件运行正常"
