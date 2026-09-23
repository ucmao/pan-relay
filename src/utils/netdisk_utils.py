import re
from typing import Optional

NETDISK_RULES = [
    # 国内主流网盘
    ("百度网盘", r"(?:https?://)?(?:pan\.baidu\.com|bdpan\.com|baiduyun\.com)/"),
    ("夸克网盘", r"(?:https?://)?pan\.quark\.cn/"),
    ("阿里云盘", r"(?:https?://)?(?:drive\.aliyun\.com|aliyundrive\.com|alipan\.com)/"),
    ("迅雷网盘", r"(?:https?://)?pan\.xunlei\.com/"),
    ("UC网盘", r"(?:https?://)?(?:pan\.uc\.cn|drive\.uc\.cn)/"),
    ("123云盘", r"(?:https?://)?(?:123pan\.(?:com|cn)|123\d{3}\.(?:com|cn))/"),
    ("115网盘", r"(?:https?://)?(?:115\.com|115pan\.com|115cdn\.com|anxia\.com)/"),
    # 运营商云盘
    ("天翼云盘", r"(?:https?://)?cloud\.189\.cn/"),
    ("移动云盘", r"(?:https?://)?(?:pan\.10086\.cn|caiyun\.139\.com|yun\.139\.com|caiyun\.feixin\.10086\.cn)/"),
    ("联通云盘", r"(?:https?://)?pan\.wo\.cn/"),
    # 国内特色/小众网盘
    ("蓝奏云", r"(?:https?://)?(?:www\.)?(?:lanzou[uixys]*|lan[zs]o[ux])\.(?:com|net|org)/"),
    ("城通网盘", r"(?:https?://)?(?:www\.)?(?:ctfile|pipipan|400gb|t004)\.(?:com|cn)/"),
    ("腾讯微云", r"(?:https?://)?(?:www\.)?weiyun\.com/"),
    ("坚果云", r"(?:https?://)?(?:www\.)?jianguoyun\.com/"),
    ("悟空网盘", r"(?:https?://)?pan\.wkbrowser\.com/"),
    ("快兔网盘", r"(?:https?://)?(?:diskyun\.com|www\.diskyun\.com)/"),
    ("光鸭云盘", r"(?:https?://)?(?:www\.)?guangyapan\.com/"),
    # 海外及跨境网盘
    ("TeraBox", r"(?:https?://)?(?:www\.)?(?:terabox|teraboxapp|1024tera|freeterabox)\.(?:com|app)/"),
    ("Google Drive", r"(?:https?://)?(?:drive|docs)\.google\.com/"),
    ("MEGA", r"(?:https?://)?mega\.(?:nz|co\.nz)/"),
    ("GoFile", r"(?:https?://)?(?:www\.)?gofile\.io/"),
    ("OneDrive", r"(?:https?://)?(?:1drv\.ms|(?:[\w-]+\.)?onedrive\.live\.com|[\w-]+\.sharepoint\.com)/"),
    ("PikPak", r"(?:https?://)?(?:www\.)?(?:pikpak|mypikpak|pikpakdrive)\.com/"),
    # P2P 下载与协议链接
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
    ("unicom", re.compile(r"pan\.wo\.cn/(?:s/|fb/|web/share/)?([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("terabox", re.compile(r"(?:terabox|teraboxapp|1024tera|freeterabox)\.(?:com|app)/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("googledrive", re.compile(r"(?:drive|docs)\.google\.com/(?:file/d/|drive/folders/|open\?id=)([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("mega", re.compile(r"mega\.(?:nz|co\.nz)/(?:file|folder)/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("gofile", re.compile(r"gofile\.io/d/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("onedrive", re.compile(r"(?:1drv\.ms/u/s!|onedrive\.live\.com/redux/\?resid=)([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("ctfile", re.compile(r"(?:ctfile|pipipan|400gb|t004)\.(?:com|cn)/(?:f|file)/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("pikpak", re.compile(r"(?:pikpak|mypikpak|pikpakdrive)\.com/s/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("lanzou", re.compile(r"(?:lanzou[uixys]*|lan[zs]o[ux])\.(?:com|net|org)/([a-zA-Z0-9_-]+)", re.IGNORECASE)),
    ("wukong", re.compile(r"(?:pan\.wkbrowser\.com|wkbrowser\.com)/(?:s/|share/)?([a-zA-Z0-9_-]+)", re.IGNORECASE)),
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



# 网盘别名、简称、常见英文及变体映射表（小写匹配）
NETDISK_ALIASES = {
    # 百度网盘
    "百度": "百度网盘",
    "百度云": "百度网盘",
    "百度网盘": "百度网盘",
    "百度云盘": "百度网盘",
    "baidu": "百度网盘",
    "baidupan": "百度网盘",
    "baiduyun": "百度网盘",
    "bdpan": "百度网盘",
    "bd": "百度网盘",

    # 夸克网盘
    "夸克": "夸克网盘",
    "夸克云": "夸克网盘",
    "夸克云盘": "夸克网盘",
    "夸克网盘": "夸克网盘",
    "quark": "夸克网盘",
    "quarkpan": "夸克网盘",
    "qk": "夸克网盘",

    # 阿里云盘
    "阿里": "阿里云盘",
    "阿里云": "阿里云盘",
    "阿里云盘": "阿里云盘",
    "阿里网盘": "阿里云盘",
    "alipan": "阿里云盘",
    "aliyun": "阿里云盘",
    "aliyundrive": "阿里云盘",
    "ali": "阿里云盘",

    # 迅雷网盘
    "迅雷": "迅雷网盘",
    "迅雷云": "迅雷网盘",
    "迅雷云盘": "迅雷网盘",
    "迅雷网盘": "迅雷网盘",
    "xunlei": "迅雷网盘",
    "xunleipan": "迅雷网盘",
    "xl": "迅雷网盘",

    # UC网盘
    "uc": "UC网盘",
    "uc网盘": "UC网盘",
    "uc云盘": "UC网盘",
    "ucpan": "UC网盘",
    "ucdrive": "UC网盘",

    # 123云盘
    "123": "123云盘",
    "123云盘": "123云盘",
    "123网盘": "123云盘",
    "123pan": "123云盘",

    # 115网盘
    "115": "115网盘",
    "115网盘": "115网盘",
    "115云盘": "115网盘",
    "115pan": "115网盘",

    # 运营商云盘
    "天翼": "天翼云盘",
    "天翼云": "天翼云盘",
    "天翼云盘": "天翼云盘",
    "天翼网盘": "天翼云盘",
    "189": "天翼云盘",
    "189云盘": "天翼云盘",
    "电信": "天翼云盘",
    "电信云盘": "天翼云盘",
    "tianyi": "天翼云盘",

    "移动": "移动云盘",
    "移动云": "移动云盘",
    "移动云盘": "移动云盘",
    "移动网盘": "移动云盘",
    "和彩云": "移动云盘",
    "彩云": "移动云盘",
    "139": "移动云盘",
    "139云盘": "移动云盘",
    "caiyun": "移动云盘",

    "联通": "联通云盘",
    "联通云": "联通云盘",
    "联通云盘": "联通云盘",
    "联通网盘": "联通云盘",
    "wo": "联通云盘",
    "wo云盘": "联通云盘",

    # 国内特色/小众网盘
    "蓝奏": "蓝奏云",
    "蓝奏云": "蓝奏云",
    "蓝奏网盘": "蓝奏云",
    "lanzou": "蓝奏云",
    "lanzoux": "蓝奏云",
    "lanzouyun": "蓝奏云",

    "城通": "城通网盘",
    "城通网盘": "城通网盘",
    "城通云盘": "城通网盘",
    "ctfile": "城通网盘",
    "pipipan": "城通网盘",

    "微云": "腾讯微云",
    "腾讯微云": "腾讯微云",
    "qq微云": "腾讯微云",
    "weiyun": "腾讯微云",

    "坚果": "坚果云",
    "坚果云": "坚果云",
    "jianguoyun": "坚果云",

    "悟空": "悟空网盘",
    "悟空网盘": "悟空网盘",
    "wkbrowser": "悟空网盘",
    "wukong": "悟空网盘",

    "快兔": "快兔网盘",
    "快兔网盘": "快兔网盘",
    "diskyun": "快兔网盘",

    "光鸭": "光鸭云盘",
    "光鸭云盘": "光鸭云盘",
    "guangya": "光鸭云盘",
    "guangyapan": "光鸭云盘",

    # 海外及跨境网盘
    "terabox": "TeraBox",
    "tera": "TeraBox",

    "google": "Google Drive",
    "googledrive": "Google Drive",
    "gdrive": "Google Drive",
    "谷歌": "Google Drive",
    "谷歌网盘": "Google Drive",
    "谷歌云盘": "Google Drive",

    "mega": "MEGA",
    "mega网盘": "MEGA",
    "mega云盘": "MEGA",

    "gofile": "GoFile",

    "onedrive": "OneDrive",
    "1drv": "OneDrive",
    "微软云盘": "OneDrive",

    "pikpak": "PikPak",

    # P2P 下载与协议链接
    "磁力": "磁力链接",
    "磁力链接": "磁力链接",
    "magnet": "磁力链接",
    "bt": "磁力链接",

    "迅雷链接": "迅雷链接",
    "thunder": "迅雷链接",

    "电驴": "电驴链接",
    "电驴链接": "电驴链接",
    "ed2k": "电驴链接",

    # 其他
    "其他": "其他",
    "other": "其他",
    "others": "其他",
}


def normalize_cloud_name(name: str) -> Optional[str]:
    """
    将输入的网盘别名、简称或全称规范化为标准网盘名称。
    若未识别到标准网盘名称，则返回 None。
    """
    if not name:
        return None
    cleaned = str(name).strip()
    if not cleaned:
        return None
    lower = cleaned.lower()
    if lower in NETDISK_ALIASES:
        return NETDISK_ALIASES[lower]
    for std_name in FRONTEND_DISPLAY_NETDISK_OPTIONS:
        if lower == std_name.lower():
            return std_name
    return None


def parse_netdisk_names(val, normalize: bool = True) -> set:
    """
    解析网盘名称入参，支持单个网盘名称、逗号/分号/竖线分隔的字符串、列表或集合。
    支持常用网盘别名/缩写（如 '百度' -> '百度网盘', 'quark' -> '夸克网盘', '阿里' -> '阿里云盘'）。
    例如:
        "夸克, 百度" -> {"夸克网盘", "百度网盘"}
        ["quark", "百度网盘"] -> {"夸克网盘", "百度网盘"}
    如果 normalize 为 True（默认），已识别的别名会被自动转换为标准网盘名称；未识别的原样保留字符串以便上层校验。
    """
    if not val:
        return set()
    if isinstance(val, (set, frozenset)):
        raw_items = [str(x).strip() for x in val if str(x).strip()]
    elif isinstance(val, (list, tuple)):
        result = set()
        for item in val:
            result.update(parse_netdisk_names(item, normalize=normalize))
        return result
    elif isinstance(val, str):
        raw_items = [part.strip() for part in re.split(r"[,;|]+", val) if part.strip()]
    else:
        clean_single = str(val).strip()
        raw_items = [clean_single] if clean_single else []

    result = set()
    for item in raw_items:
        if not item:
            continue
        if normalize:
            norm = normalize_cloud_name(item)
            result.add(norm if norm else item)
        else:
            result.add(item)
    return result

