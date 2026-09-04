import re
from typing import Optional

NETDISK_RULES = [
    # 网盘
    ("百度网盘", r"(?:https?://)?(?:pan\.baidu\.com|bdpan\.com|baiduyun\.com)/"),
    ("夸克网盘", r"(?:https?://)?pan\.quark\.cn/"),
    ("迅雷网盘", r"(?:https?://)?pan\.xunlei\.com/"),
    ("UC网盘", r"(?:https?://)?(?:pan\.uc\.cn|drive\.uc\.cn)/"),
    ("悟空网盘", r"(?:https?://)?pan\.wkbrowser\.com/"),
    ("快兔网盘", r"(?:https?://)?(?:diskyun\.com|www\.diskyun\.com)/"),
    ("115网盘", r"(?:https?://)?(?:115\.com|115pan\.com|115cdn\.com|anxia\.com)/"),
    ("蓝奏云", r"(?:https?://)?(?:www\.)?(?:lanzou[uixys]*|lan[zs]o[ux])\.(?:com|net|org)/"),
    ("光鸭云盘", r"(?:https?://)?(?:www\.)?guangyapan\.com/"),
    ("腾讯微云", r"(?:https?://)?(?:www\.)?weiyun\.com/"),
    ("坚果云", r"(?:https?://)?(?:www\.)?jianguoyun\.com/"),
    # 云盘
    ("阿里云盘", r"(?:https?://)?(?:drive\.aliyun\.com|aliyundrive\.com|alipan\.com)/"),
    ("天翼云盘", r"(?:https?://)?cloud\.189\.cn/"),
    ("移动云盘", r"(?:https?://)?(?:pan\.10086\.cn|caiyun\.139\.com|yun\.139\.com|caiyun\.feixin\.10086\.cn)/"),
    ("联通云盘", r"(?:https?://)?pan\.wo\.cn/"),
    ("123云盘", r"(?:https?://)?(?:123pan\.(?:com|cn)|123\d{3}\.(?:com|cn))/"),
    # 其他网盘
    ("PikPak", r"(?:https?://)?(?:www\.)?(?:pikpak|mypikpak|pikpakdrive)\.com/"),
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


CANONICAL_ID_PATTERNS = [
    ("quark", re.compile(r"pan\.quark\.cn/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("baidu", re.compile(r"(?:pan\.baidu\.com|bdpan\.com|baiduyun\.com)/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("aliyun", re.compile(r"(?:alipan\.com|aliyundrive\.com|drive\.aliyun\.com)/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("uc", re.compile(r"(?:drive\.uc\.cn|pan\.uc\.cn)/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("xunlei", re.compile(r"pan\.xunlei\.com/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("123pan", re.compile(r"(?:123pan\.(?:com|cn)|123\d{3}\.(?:com|cn))/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("tianyi", re.compile(r"cloud\.189\.cn/(?:t/|web/share\?code=)([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("115", re.compile(r"(?:115\.com|115pan\.com|115cdn\.com|anxia\.com)/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("mobile", re.compile(r"(?:yun\.139\.com/shareweb/#/w/i/|caiyun\.139\.com/w/i/|caiyun\.139\.com/m/i\?|caiyun\.feixin\.10086\.cn/|pan\.10086\.cn/s/)([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("pikpak", re.compile(r"(?:pikpak|mypikpak|pikpakdrive)\.com/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("lanzou", re.compile(r"(?:lanzou[uixys]*|lan[zs]o[ux])\.(?:com|net|org)/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("guangya", re.compile(r"guangyapan\.com/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("weiyun", re.compile(r"weiyun\.com/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("jianguoyun", re.compile(r"jianguoyun\.com/p/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("magnet", re.compile(r"magnet:\?xt=urn:btih:([a-zA-Z0-9]+)", re.IGNORECASE)),
    ("ed2k", re.compile(r"ed2k://\|file\|[^|]+\|\d+\|([a-fA-F0-9]+)\|", re.IGNORECASE)),
]

URL_PASSWORD_PATTERN = re.compile(
    r"(?:[?&](?:pwd|password|code)=|(?:提取码|访问码|密码)[:：=\s]*)([a-zA-Z0-9]{4,6})",
    re.IGNORECASE,
)


def extract_password_from_url(url: str) -> Optional[str]:
    """从 URL 中提取 4-6 位提取码/密码。"""
    if not url:
        return None
    match = URL_PASSWORD_PATTERN.search(str(url))
    if match:
        return match.group(1)
    return None


def extract_canonical_resource_key(url: str) -> str:
    """
    提取规范化的网盘资源唯一键，用于跨渠道精准去重。
    - 同一真实分享链接（无论附带何种 query 或处于哪个域名别名）返回相同的 key
    - 不同分享链接（即使标题相同）返回不同的 key
    """
    if not url:
        return ""

    raw = str(url).strip()

    # 1. 尝试网盘特征提取
    for prefix, pattern in CANONICAL_ID_PATTERNS:
        match = pattern.search(raw)
        if match:
            resource_id = match.group(1)
            if prefix in ("magnet", "ed2k"):
                return f"{prefix}:{resource_id.lower()}"
            return f"{prefix}:{resource_id}"

    # 2. 通用 URL 兜底
    try:
        from urllib.parse import urlparse, parse_qs, urlencode
        parsed = urlparse(raw)
        if parsed.scheme and parsed.netloc:
            netloc = parsed.netloc.lower()
            path = parsed.path.rstrip("/")
            # 去除常见追踪参数
            if parsed.query:
                query_dict = parse_qs(parsed.query)
                tracking_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "spm", "from", "ref", "_t"}
                clean_query = {k: v for k, v in query_dict.items() if k.lower() not in tracking_keys and not k.lower().startswith("utm_")}
                if clean_query:
                    sorted_query = urlencode(sorted((k, v[0] if len(v) == 1 else v) for k, v in clean_query.items()))
                    return f"url:{netloc}{path}?{sorted_query}"
            return f"url:{netloc}{path}"
    except Exception:
        pass

    return f"raw:{raw}"

