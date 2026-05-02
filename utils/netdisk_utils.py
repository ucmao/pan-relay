import re

NETDISK_RULES = [
    # 网盘
    ("百度网盘", r"(?:https?://)?(?:pan\.baidu\.com|bdpan\.com|baiduyun\.com)/"),
    ("夸克网盘", r"(?:https?://)?pan\.quark\.cn/"),
    ("迅雷网盘", r"(?:https?://)?pan\.xunlei\.com/"),
    ("UC网盘", r"(?:https?://)?(?:pan\.uc\.cn|drive\.uc\.cn)/"),
    ("悟空网盘", r"(?:https?://)?pan\.wkbrowser\.com/"),
    ("快兔网盘", r"(?:https?://)?(?:diskyun\.com|www\.diskyun\.com)/"),
    ("115网盘", r"(?:https?://)?(?:115\.com|115pan\.com|115cdn\.com|anxia\.com)/"),
    # 云盘
    ("阿里云盘", r"(?:https?://)?(?:drive\.aliyun\.com|aliyundrive\.com|alipan\.com)/"),
    ("天翼云盘", r"(?:https?://)?cloud\.189\.cn/"),
    ("移动云盘", r"(?:https?://)?(?:pan\.10086\.cn|caiyun\.139\.com|yun\.139\.com)/"),
    ("联通云盘", r"(?:https?://)?pan\.wo\.cn/"),
    ("123云盘", r"(?:https?://)?(?:123pan\.com|123\d{3}\.com)/"),
    # 其他网盘
    ("PikPak", r"(?:https?://)?(?:www\.)?pikpak\.com/"),
    # 链接类型
    ("磁力链接", r"^magnet:\?xt=urn:btih:"),
    ("迅雷链接", r"thunder://[A-Za-z0-9+/=]+"),
    ("电驴链接", r"^ed2k://"),
]

FRONTEND_DISPLAY_NETDISK_OPTIONS = [name for name, _ in NETDISK_RULES] + ["其他"]


def match_netdisk_link(link: str) -> str:
    """
    匹配网盘链接，返回对应的网盘名称，未匹配则返回"其他"
    """
    link_lower = link.strip().lower()
    for name, pattern in NETDISK_RULES:
        if re.search(pattern, link_lower, re.IGNORECASE):
            return name
    return "其他"
