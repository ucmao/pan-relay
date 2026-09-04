from src.plugins.detail_page_adapter import DetailPagePlugin


class KkvPlugin(DetailPagePlugin):
    name = "kkv"
    display_name = "KKV 资源"
    description = "KKV WordPress 详情页网盘资源"
    priority = 110
    is_enabled = False
    publish_by_default = True
    timeout = 8.0
    base_url = "http://kkv.q-23.cn"
    search_selector = "article.post"
    detail_link_selector = ".entry-header h2.entry-title a[href]"
    resource_selector = ".entry-content p a[href]"
    max_details = 10

    def search_records(self, keyword):
        response = self.request("GET", self.base_url + "/", params={"s": keyword})
        return self.records_from_html(response.text)
