from src.plugins.maccms_adapter import MacCmsPlugin


class HubanPlugin(MacCmsPlugin):
    name = "huban"
    display_name = "虎斑资源"
    description = "虎斑备用网址轮询资源"
    priority = 120
    is_enabled = False
    publish_by_default = True
    timeout = 8.0
    base_urls = (
        "http://121.205.88.174:16969", "http://38.76.197.172:16969", "http://xhban.xyz:20720",
    )
