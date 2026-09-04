from src.plugins.detail_page_adapter import DetailPagePlugin


class JutoushePlugin(DetailPagePlugin):
    name = "jutoushe"
    display_name = "剧透社"
    description = "剧透社详情页网盘资源"
    priority = 110
    is_enabled = False
    publish_by_default = True
    timeout = 8.0
    base_url = "https://1.star2.cn"
    search_selector = "ul.erx-list li.item"
    detail_link_selector = ".a a.main"
    resource_selector = ".dlipp-cont-bd a.dlipp-dl-btn[href]"

    def search_records(self, keyword):
        response = self.request("GET", self.base_url + "/search/", params={"keyword": keyword})
        return self.records_from_html(response.text, ".i span.time")
