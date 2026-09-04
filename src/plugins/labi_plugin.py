from src.plugins.maccms_adapter import MacCmsPlugin


class LabiPlugin(MacCmsPlugin):
    name = "labi"
    display_name = "蜡笔资源"
    description = "蜡笔 MacCMS 影视资源"
    priority = 115
    is_enabled = False
    publish_by_default = True
    timeout = 10.0
    base_urls = ("http://www.xiaocgege.shop", "http://feimo.fun", "http://xiaocgege.shop")
