# 搜索源体系与自定义插件开发指南

`pan-relay` 拥有高度模块化、多维并发的搜索源聚合架构，支持同时从 3 种渠道并发抓取与聚合资源：
1. **第三方 JSON / REST API 接口源**
2. **Telegram 公开频道免凭证抓取源**
3. **Python 本地搜索插件（Plugins）**

2026 年 10 月对 API、Telegram 频道和插件的字段探测结果汇总在[来源字段审计报告](source-field-audit/README.md)。

---

## 🔌 渠道一：第三方 API 接口源配置

在后台 **搜索源 → API 搜索源** 中可添加任意返回 JSON 格式的第三方搜盘接口。

### 字段提取规则（基于 JMESPath 语法）

系统使用高性能的 `JMESPath` 表达式进行声明式字段映射：

| 映射配置 | 作用说明 | 常见示例表达式 |
| :--- | :--- | :--- |
| **结果列表表达式 (items_path)** | 从上游 JSON 中提取资源数组对象 | `data.list`, `results`, `list` |
| **标题表达式 (title_path)** | 提取单条资源标题 | `title`, `name`, `file_name` |
| **链接表达式 (url_path)** | 提取网盘分享链接 | `url`, `link`, `share_url` |
| **提取码表达式 (password_path)** | 提取网盘提取码/访问密码 | `password`, `pwd`, `code` |
| **时间表达式 (datetime_path)** | 提取资源更新或发布时间 | `created_at`, `time`, `pub_date` |

系统支持在后台即时发起“联调测试”，输入测试关键词可实时查看返回的 JSON 结构与字段解析提取结果。

---

## ✈️ 渠道二：Telegram 公开频道免凭证抓取

在后台 **搜索源 → Telegram 频道** 中管理抓取的频道列表：
* **免 Bot Token 原理**：通过抓取 Telegram 官方公开 Web 前端预览（`t.me/s/{channel_name}`），无需申请 Bot Token，也无需配置 Telegram 账号。
* **内置正则智能解析**：自动从推文中提取 12 种主流网盘链接与提取码（支持“密码”、“提取码”、“访问码”等多种自然语言模式）。
* **代理配置**：可在 **搜索源 → 搜索调度参数** 中配置 HTTP / SOCKS5 代理（如 `socks5://127.0.0.1:1080`），国内服务器亦可畅通抓取。

---

## 🐍 渠道三：编写自定义 Python 搜索插件

系统支持通过编写独立的 Python 插件来对接任何复杂的网页搜索、需要加密签名的爬虫或专有网盘搜索站。

将自动加载的插件放在 [`src/plugins/`](../src/plugins/) 目录下，文件名以 `_plugin.py` 结尾。

### 插件开发模板

在 `src/plugins/` 下新建 `my_custom_search_plugin.py`。插件继承 `BasePlugin` 并实现 `search(keyword)`，返回 `SearchResultItem` 列表。

```python
# src/plugins/my_custom_search_plugin.py

import logging
from typing import List

import requests

from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class MyCustomSearchPlugin(BasePlugin):
    """
    自定义搜索插件示例
    """
    name = "my_custom_search"          # 唯一插件英文标识
    display_name = "我的专属搜索源"      # 后台展示中文名称
    version = "1.0.0"                  # 插件版本号
    author = "Developer"               # 作者信息
    description = "抓取某特定影视资源站的网盘链接"

    def search(self, keyword: str) -> List[SearchResultItem]:
        try:
            response = requests.get(
                "https://example.com/api/search",
                params={"q": keyword},
                timeout=self.timeout,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        except (requests.RequestException, ValueError) as exc:
            logger.warning("插件搜索失败：%s", exc)
            return []

        return [
            SearchResultItem(
                source=f"plugin:{self.name}",
                title=item["title"],
                share_link=item["share_link"],
                cloud_name="夸克网盘",
                password=item.get("pwd"),
                datetime=item.get("create_time"),
            )
            for item in items
            if item.get("title") and item.get("share_link")
        ]
```

将示例 URL、响应字段和网盘名称替换成实际数据源的值。HTML 解析可参考[仓库中的示例插件](../src/plugins/examples/sample_scraper_plugin.py)。

### 插件加载与管理
* **自动注册**：服务启动时会加载 `src/plugins/` 下符合命名规则的插件。新增文件后重启服务即可加载。
* **后台统一管控**：可在管理后台（**搜索源 → 插件扩展**）中随时开启、停用、执行联调测试与查看响应延迟。
