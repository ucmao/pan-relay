from src.plugins.maccms_adapter import MacCmsPlugin


class ShandianPlugin(MacCmsPlugin):
    name = "shandian"
    display_name = "闪电资源"
    description = "闪电 MacCMS 影视资源"
    priority = 110
    is_enabled = False
    publish_by_default = True
    timeout = 10.0
    base_urls = ("http://sduc.cloud", "http://shandian.blog", "http://sd.sduc.site")
