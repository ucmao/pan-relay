---
name: panrelay-plugin-dev
description: >-
  Comprehensive guide and generator for creating, developing, testing, and debugging pan-relay
  search plugins and JMESPath extraction rules. Use when adding new cloud disk search sources,
  converting cURL/API/websites into Python plugins, or reversing JSON API extraction expressions.
---

# pan-relay 插件化体系与数据源接入指南

本指南为开发者与 AI 助理提供在 `pan-relay` 项目中扩展全新网盘搜索源的标准规范与自动化生成方法。

---

## 接入模式决策树：JMESPath vs Python 插件

在接入新数据源时，优先根据目标数据源的特征选择接入方式：

```
目标数据源类型
   │
   ├─► 标准公开 JSON API (单次 GET/POST 直接返回数据列表)
   │     └─► 【使用 JMESPath 动态配置】(推荐，Web 后台直接配置，无需代码)
   │
   └─► 复杂数据源：
         ├─ HTML 网页 / 论坛 (需 DOM 解析，如 BeautifulSoup)
         ├─ 多步请求 (如需先获取 Token / Session，再带参数检索)
         ├─ 请求/响应包含加密 (如 AES、MD5 签名、时间戳防篡改)
         ├─ 动态 Cookie / 特殊 User-Agent / 自定义防盗链 Referer
         └─► 【使用 Python 扩展插件体系】(在 src/plugins/ 编写插件类)
```

---

## 一、编写 Python 扩展插件 (`src/plugins/`)

### 1. 插件基础契约

所有扩展插件必须存放于 `src/plugins/` 目录下（文件名推荐以 `_plugin.py` 结尾），并继承 `src.plugins.base_plugin.BasePlugin`。
系统启动时由 `PluginManager` 自动扫描、动态加载并注册。

### 2. 标准插件代码骨架模板

```python
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Tuple

from src.configs.app_config import user_agents
from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin
from src.utils.netdisk_utils import match_netdisk_link, extract_password_from_url

logger = logging.getLogger(__name__)


class MyCustomPlugin(BasePlugin):
    # 插件全局唯一标识（建议全小写，避免空格）
    name = "my_custom_source"

    # 显示在前端或管理接口的人类可读名称
    display_name = "我的自定义数据源"

    version = "1.0.0"
    author = "developer"
    description = "抓取某某网盘资源站"

    # 插件优先级权重（影响 P1 综合评分，默认 100，优质源可设 150~200）
    priority = 130

    # 默认启用状态
    is_enabled = True

    # 每次搜索请求的独立超时熔断上限（秒）
    timeout = 6.0

    def search(self, keyword: str) -> List[SearchResultItem]:
        """
        核心检索方法：根据关键词抓取并返回标准 SearchResultItem 对象列表。
        必须做好异常捕获，确保即使发生网络异常也不抛出未捕获崩溃。
        """
        results = []
        if not keyword:
            return results

        target_url = f"https://example.com/search?q={keyword}"
        headers = {
            "User-Agent": user_agents[0],
            "Referer": "https://example.com/",
        }

        try:
            resp = requests.get(target_url, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning(f"[{self.name}] 请求失败: HTTP {resp.status_code}")
                return results

            # 示例：网页 DOM 解析
            soup = BeautifulSoup(resp.text, "html.parser")
            for item_node in soup.select(".resource-item"):
                title_elem = item_node.select_one(".title")
                link_elem = item_node.select_one("a.pan-link")
                if not title_elem or not link_elem:
                    continue

                raw_title = title_elem.get_text(strip=True)
                share_url = link_elem.get("href", "").strip()

                # 识别网盘类型与提取码
                cloud_name = match_netdisk_link(share_url)
                if cloud_name == "其他":
                    continue

                pwd = extract_password_from_url(share_url)

                results.append(
                    SearchResultItem(
                        source=f"plugin:{self.name}",
                        title=raw_title,
                        share_link=share_url,
                        cloud_name=cloud_name,
                        password=pwd,
                    )
                )

        except Exception as e:
            logger.error(f"[{self.name}] 搜索异常: {e}")

        return results

    def health_check(self) -> Tuple[bool, str]:
        """连通性轻量心跳检查"""
        try:
            r = requests.get("https://example.com/ping", timeout=3.0)
            return (r.status_code == 200), f"HTTP {r.status_code}"
        except Exception as e:
            return False, str(e)
```

---

## 二、自动推导 JMESPath 规则指南

当目标是标准 JSON API 时，无需写插件，只需在后台输入 URL 与 JMESPath 提取规则：

1. **确定数组列表路径**：
   - 若返回：`{"code": 0, "data": {"list": [{"name": "繁花", "url": "https://..."}]}}`
   - 提取规则：`data.list[*].[name, url]`
2. **处理带提取码的字段**：
   - 若提取码在单独字段：`[name, url, pwd]` 或 `[title, link]`
3. **测试连通性**：
   - 可在管理后台 `/api_configs` 页面直接点击“测试”按钮，验证前 2 条预览提取数据。

---

## 三、调试与验证规范

每次新增插件后，执行以下命令进行自动化校验：

```bash
# 1. 运行插件系统单元测试
python3 -m unittest tests/test_plugin_system.py

# 2. 运行全工程回归测试
python3 -m unittest discover -s tests

# 3. 检查插件是否被自动发现
curl http://localhost:5000/api/plugins
```
