import re

from src.plugins.detail_page_adapter import DetailPagePlugin
from src.plugins.http_plugin import PluginRequestError


class ClxiongPlugin(DetailPagePlugin):
    name = "clxiong"
    display_name = "磁力熊"
    description = "磁力熊搜索重定向与详情页磁力资源"
    priority = 105
    is_enabled = False
    publish_by_default = False
    timeout = 9.0
    base_url = "https://www.cilixiong.org"
    search_selector = ".row.row-cols-2.row-cols-lg-4 .col"
    detail_link_selector = "a[href*='/drama/'], a[href*='/movie/']"
    title_selector = "h2.h4"
    resource_selector = ".mv_down a[href^='magnet:'], a[href^='magnet:']"

    def search_records(self, keyword):
        response = self.request(
            "POST", self.base_url + "/e/search/index.php",
            data={"classid": "1,2", "show": "title", "tempid": "1", "keyboard": keyword},
            headers={"Referer": self.base_url + "/", "Content-Type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
        )
        match = re.search(r"searchid=(\d+)", response.headers.get("Location", ""))
        if not match:
            raise PluginRequestError("[clxiong] 搜索响应缺少 searchid")
        page = self.request("GET", self.base_url + "/e/search/result/", params={"searchid": match.group(1)})
        return self.records_from_html(page.text)
