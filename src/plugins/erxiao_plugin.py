from src.plugins.maccms_adapter import MacCmsPlugin


class ErxiaoPlugin(MacCmsPlugin):
    name = "erxiao"
    display_name = "二小资源"
    description = "二小 MacCMS 影视资源"
    priority = 110
    is_enabled = False
    publish_by_default = True
    timeout = 8.0
    base_urls = ("https://www.wexwp.cc", "https://www.2xiaopan.top")
