from src.plugins.maccms_adapter import MacCmsPlugin


class ZhizhenPlugin(MacCmsPlugin):
    name = "zhizhen"
    display_name = "指针资源"
    description = "指针 MacCMS 影视资源"
    priority = 115
    is_enabled = False
    publish_by_default = True
    timeout = 8.0
    base_urls = ("http://www.miqk.cc", "https://mihdr.top", "https://www.mihdr.top")
