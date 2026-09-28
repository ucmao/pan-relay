# 搜索源体系与自定义插件开发指南

`pan-relay` 拥有高度模块化、多维并发的搜索源聚合架构，支持同时从 3 种渠道并发抓取与聚合资源：
1. **第三方 JSON / REST API 接口源**
2. **Telegram 公开频道免凭证抓取源**
3. **Python 本地搜索插件（Plugins）**

---

## 🔌 渠道一：第三方 API 接口源配置

在后台 **搜索源管理 → API 接口** 中可添加任意返回 JSON 格式的第三方搜盘接口。

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

在后台 **搜索源管理 → Telegram 频道** 中管理抓取的频道列表：
* **免 Bot Token 原理**：通过抓取 Telegram 官方公开 Web 前端预览（`t.me/s/{channel_name}`），无需申请 Bot Token，也无需配置 Telegram 账号。
* **内置正则智能解析**：自动从推文中提取 12 种主流网盘链接与提取码（支持“密码”、“提取码”、“访问码”等多种自然语言模式）。
* **代理配置**：可在 **搜索源管理 → 调度与代理** 中配置 HTTP / SOCKS5 代理（如 `socks5://127.0.0.1:1080`），国内服务器亦可畅通抓取。

---

## 🐍 渠道三：编写自定义 Python 搜索插件

系统支持通过编写独立的 Python 插件来对接任何复杂的网页搜索、需要加密签名的爬虫或专有网盘搜索站。

所有插件均放置于 [`src/plugins/`](file:///Users/leo/Projects/pan-relay/src/plugins/) 目录下。

### 插件开发模板

在 `src/plugins/` 下新建一个 Python 文件，例如 `my_custom_search.py`：

```python
# src/plugins/my_custom_search.py

from typing import Any, Dict, List
import requests
from src.plugins.base import BaseSearchPlugin

class MyCustomSearchPlugin(BaseSearchPlugin):
    """
    自定义搜索插件示例
    """
    name = "my_custom_search"          # 唯一插件英文标识
    display_name = "我的专属搜索源"      # 后台展示中文名称
    version = "1.0.0"                  # 插件版本号
    author = "Developer"               # 作者信息
    description = "抓取某特定影视资源站的网盘链接"

    def search(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """
        核心搜索执行方法。
        
        返回值规范：必须返回标准字典列表，包含以下字段：
        - title (str, 必填): 资源标题
        - url (str, 必填): 网盘分享 URL
        - netdisk_name (str, 可选): 网盘名称（如 夸克网盘、百度网盘 等，不填会自动识别）
        - password (str, 可选): 提取码
        - datetime (str, 可选): 资源发布时间
        """
        results = []
        target_api = f"https://example.com/api/search?q={keyword}&p={page}"
        
        try:
            resp = requests.get(target_api, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("share_link", ""),
                        "netdisk_name": "夸克网盘",
                        "password": item.get("pwd", ""),
                        "datetime": item.get("create_time", ""),
                    })
        except Exception as exc:
            self.logger.error(f"插件搜索异常: {exc}")

        return results
```

### 插件生命周期与热加载
* **自动注册**：将写好的 `.py` 脚本放入 `src/plugins/` 目录后，服务启动或重启时会自动加载并注册。
* **后台统一管控**：可在管理后台（**搜索源管理 → 插件管理**）中随时开启、停用、执行联调测试与查看响应延迟。
