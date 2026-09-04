from src.plugins.detail_page_adapter import DetailPagePlugin


class JavdbPlugin(DetailPagePlugin):
    name = "javdb"
    display_name = "JavDB 磁力"
    description = "成人内容磁力源；独立标记并默认关闭"
    priority = 60
    is_enabled = False
    publish_by_default = True
    timeout = 9.0
    base_url = "https://javdb.com"
    search_selector = ".movie-list .item"
    detail_link_selector = "a.box[href], a[href*='/v/']"
    title_selector = ".video-title"
    resource_selector = ".magnet-links .item .magnet-name a[href^='magnet:'], a[href^='magnet:']"
    max_details = 8

    def search_records(self, keyword):
        response = self.request("GET", self.base_url + "/search", params={"q": keyword, "f": "all"}, headers={"Referer": self.base_url + "/"})
        return self.records_from_html(response.text, ".meta")
