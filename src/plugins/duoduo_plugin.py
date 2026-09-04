from src.plugins.maccms_adapter import MacCmsPlugin


class DuoduoPlugin(MacCmsPlugin):
    name = "duoduo"
    display_name = "多多资源"
    description = "多多 MacCMS 影视资源"
    priority = 115
    is_enabled = False
    publish_by_default = True
    timeout = 8.0
    base_urls = ("https://tv.yydsys.top",)
