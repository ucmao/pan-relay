from src.plugins.maccms_adapter import MacCmsPlugin


class MuouPlugin(MacCmsPlugin):
    name = "muou"
    display_name = "木偶资源"
    description = "木偶 MacCMS 影视资源"
    priority = 110
    is_enabled = False
    publish_by_default = True
    timeout = 8.0
    base_urls = (
        "https://www.muoua.top", "http://www.muoua.top", "https://333.333291.xyz",
        "http://333.333291.xyz", "https://666.666291.xyz", "http://666.666291.xyz",
    )
