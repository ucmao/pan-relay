import logging
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Tuple

from src.plugins.base_plugin import BasePlugin
from src.models.search_item import SearchResultItem
from src.configs.app_config import user_agents
from src.utils.netdisk_utils import match_netdisk_link, extract_password_from_url

logger = logging.getLogger(__name__)


class XdyhPlugin(BasePlugin):
    name = "xdyh"
    display_name = "现代影影院"
    version = "1.0.0"
    author = "pan-relay"
    description = "现代影影院 数据源搜索插件"
    priority = 130
    is_enabled = True
    timeout = 5.0

    def search(self, keyword: str) -> List[SearchResultItem]:
        results = []
        if not keyword:
            return results
        url = "https://ys.66ds.de/search?q=%s" % keyword
        headers = {"User-Agent": user_agents[0], "Referer": "https://ys.66ds.de"}
        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                return results

            ct = resp.headers.get("Content-Type", "")
            if "json" in ct or resp.text.strip().startswith(("{", "[")):
                try:
                    data = resp.json()
                    items = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    if isinstance(items, dict) and "list" in items:
                        items = items["list"]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        title = item.get("title") or item.get("name") or item.get("heading") or item.get("vod_name") or ""
                        link = item.get("url") or item.get("link") or item.get("share_link") or item.get("pan_url") or item.get("vod_play_url") or ""
                        if title and link:
                            cloud = match_netdisk_link(link)
                            pwd = item.get("password") or item.get("pwd") or extract_password_from_url(link)
                            results.append(
                                SearchResultItem(
                                    source=f"plugin:{self.name}",
                                    title=str(title).strip(),
                                    share_link=str(link).strip(),
                                    cloud_name=cloud,
                                    password=pwd,
                                )
                            )
                except Exception as je:
                    logger.debug(f"[{self.name}] JSON 解析跳过: {je}")
            else:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    title = a_tag.get_text(strip=True) or a_tag.get("title", "").strip()
                    cloud = match_netdisk_link(href)
                    if cloud != "其他" and title:
                        pwd = extract_password_from_url(href)
                        results.append(
                            SearchResultItem(
                                source=f"plugin:{self.name}",
                                title=title,
                                share_link=href,
                                cloud_name=cloud,
                                password=pwd,
                            )
                        )
        except Exception as e:
            logger.error(f"[{self.name}] 搜索异常: {e}")
        return results

    def health_check(self) -> Tuple[bool, str]:
        try:
            r = requests.get("https://ys.66ds.de", headers={"User-Agent": user_agents[0]}, timeout=3.0)
            return r.status_code == 200, f"HTTP {r.status_code}"
        except Exception as e:
            return False, str(e)
