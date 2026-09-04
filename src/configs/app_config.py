# configs/app_config.py

import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()


def _get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name, default, minimum=1):
    try:
        return max(int(os.getenv(name, default)), minimum)
    except (TypeError, ValueError):
        return default

# 获取项目根目录 (pan-relay/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置 SECRET_KEY，用于会话管理与 JWT 签名
SECRET_KEY = os.getenv('SECRET_KEY', 'pan-relay-secret-key-default')

# 网盘信息
QUARK_PAN_COOKIE = os.getenv('QUARK_PAN_COOKIE')
BAIDU_PAN_COOKIE = os.getenv('BAIDU_PAN_COOKIE')
DEFAULT_SAVE_DIR = os.getenv('DEFAULT_SAVE_DIR')

# 管理员账号密码（默认: admin / admin123）
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME') or 'admin'
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or 'admin123'

# Telegram 公开频道搜索
TG_SEARCH_ENABLED = _get_bool_env("TG_SEARCH_ENABLED", True)
DEFAULT_TG_CHANNELS = (
    "txtyzy,BaiduCloudDisk,tianyifc,yp123pan,PanjClub,tgsearchers7,peccxinpd,yunpanxunlei,bsbdbfjfjff,gotopan,Aliyun_4K_Movies,yunpanx,sbsbsnsqq,tgsearchers3,tgsearchers6,bdbdndn11,ysxb48,ucwpzy,MCPH086,Q66Share,zaihuayun,MCPH01,MCPH03,MCPH02,baicaoZY,bdwpzhpd,shareAliyun,jdjdn1111,yggpan,kkxlzy,dianyingshare,alyp_1,tianyirigeng,yingshifenxiang123,tyypzhpd,oneonefivewpfx,ucquark,zyfb123,yunpan189,xx123pan,Quark_Movies,hdhhd21,Lsp115,XiangxiuNBB,vip115hot,tyysypzypd,TG654TG,Channel_Shares_115,taoxgzy,cloudtianyi,yunpanuc,Q_dongman,movielover8888_film3,yydf_hzl,yeqingjie_GJG666,leoziyuan,yunpan139,wp123zy,qixingzhenren,KaiPanshare,D_wusun,pxyunpanxunlei,FLMdongtianfudi,QukanMovie,ydypzyfx,yunpanNB,newproductsourcing,rjyxfx,QQZYDAPP,xxzlzn,zdqxm,btzhi,PikPak_Share_Channel,Baidu_netdisk,solidsexydoll,cilidianying,CBduanju,WFYSFX02,jxwpzy,cctv1211,SharePanFilms,yoyokuakeduanju,guoman4K,dzsgx,duan_ju,kduanju,kuakedongman,douerpan,ciliziyuanku,domgmingapk,baidu_yppan,BooksRealm,Q_dianying,xiangnikanj,dianying4k,kkdj001,Oscar_4Kmovies,liangxingzhinan,yunpanquark,godupan,ucshare,Q_jilupian,Netdisk_Movies,jzmm_123pan,WFYSFX03,ammmziyuan,cili8888,gimy115,tgbokee,q_dianshiju,gimy115iso,wpan8,gimy100,mqte5,regengguangya,regeng123,QuarkFree,gokuapan,regeng115,yunpanguangya,peccxin,guangyapan_episode,xlwpzy,yy80986098,zyywpzy,pan_guangya,Movie888035,wydwpzy,pikpakpan,yoyokuakeduanjujiaoliuqun,AV688"
)
DEFAULT_DISABLED_TG_CHANNELS = (
    "tgsearchers6,sbsbsnsqq,kkxlzy,alyp_1,dianyingshare,yggpan,cloudtianyi,ydypzyfx,tgsearchers3,WFYSFX02,cctv1211,qixingzhenren,ammmziyuan,cili8888,q_dianshiju,liangxingzhinan,Movie888035,AV688,duan_ju,wydwpzy,yoyokuakeduanjujiaoliuqun,xlwpzy,zyywpzy,peccxin,pikpakpan"
)

# 插件首次初始化状态；由发布前健康检测脚本同步。
DEFAULT_PLUGIN_SETTINGS = {
    'clxiong': False,
    'duoduo': True,
    'duanjuku': True,
    'erxiao': True,
    'huban': True,
    'hunhepan': True,
    'ikantv': True,
    'javdb': False,
    'jutoushe': True,
    'kkv': True,
    'labi': True,
    'muou': False,
    'nyaa': True,
    'ouge': True,
    'pansearch': True,
    'quark4k': True,
    'quarksoo': False,
    'sample_scraper': False,
    'shandian': True,
    'ting77': True,
    'u3c3': False,
    'xb6v': False,
    'xiaokupan': True,
    'yunso': True,
    'zhizhen': True,
}
TG_CHANNELS = [
    channel.strip().lstrip("@").strip("/")
    for channel in os.getenv("TG_CHANNELS", DEFAULT_TG_CHANNELS).split(",")
    if channel.strip()
]
TG_DISABLED_CHANNELS = [
    channel.strip().lstrip("@").strip("/")
    for channel in os.getenv("TG_DISABLED_CHANNELS", DEFAULT_DISABLED_TG_CHANNELS).split(",")
    if channel.strip()
]
TG_SEARCH_TIMEOUT = _get_int_env("TG_SEARCH_TIMEOUT", 10)
TG_SEARCH_MAX_WORKERS = _get_int_env("TG_SEARCH_MAX_WORKERS", 4)
TG_PROXY = os.getenv("TG_PROXY", "").strip()

# SQLite 数据库配置
default_db_path = os.path.join(BASE_DIR, "data", "pan_relay.db")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.abspath(default_db_path))

# User-Agent 列表配置（这类静态列表可以保持不变）
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 OPR/77.0.4054.203',
    'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 OPR/77.0.4054.203',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 OPR/77.0.4054.203'
]


DEFAULT_TG_CHANNEL_TITLES = {
    "txtyzy": "埃菲尔花园",
    "BaiduCloudDisk": "百度网盘中转&通知频道",
    "tianyifc": "天翼刮削资源分享",
    "yp123pan": "网盘资源收藏(123云盘)",
    "tgsearchers7": "资源宇宙7",
    "peccxinpd": "盘链资源频道",
    "yunpanxunlei": "网盘资源收藏(迅雷云盘)",
    "bsbdbfjfjff": "散人影视",
    "gotopan": "网盘资源分享频道🅥",
    "yunpanx": "云盘影库|4K影视网盘资源",
    "bdbdndn11": "电影网盘分享频道",
    "ysxb48": "115网盘",
    "ucwpzy": "UC网盘发布频道",
    "MCPH086": "莫愁片海🐳动画",
    "Q66Share": "阿里云盘吧",
    "zaihuayun": "🎬 阿里云盘资源 🆙 🚦",
    "MCPH01": "莫愁片海🐳综合",
    "MCPH03": "莫愁片海🐳链接直接显示",
    "MCPH02": "莫愁片海🐳擦边短剧等🥵",
    "baicaoZY": "百草网盘资源",
    "bdwpzhpd": "百度网盘综合频道",
    "shareAliyun": "阿里云盘发布频道",
    "jdjdn1111": "短剧网盘分享",
    "dianyingshare": "糖心萝莉学生妹",
    "alyp_1": "网盘(高品质)影视",
    "yingshifenxiang123": "比比追更",
    "tyypzhpd": "天翼云盘资源频道",
    "oneonefivewpfx": "115网盘资源收藏",
    "yunpan189": "网盘资源收藏(天翼云盘)",
    "xx123pan": "123云盘资源频道",
    "Quark_Movies": "夸克云盘影视资源频道",
    "hdhhd21": "影视热门更新",
    "Lsp115": "115网盘资源分享频道",
    "XiangxiuNBB": "肯德基の4K影视综合电影云盘站",
    "vip115hot": "懒狗集中营-115/阿里/百度/迅雷/夸克 影视分享 阿里云盘百度网盘115网盘光鸭云盘",
    "TG654TG": "热门影视、综艺网盘资源频道",
    "Channel_Shares_115": "Shares_115_Channel",
    "taoxgzy": "我的资源频道",
    "yunpanuc": "网盘资源收藏(UC网盘)",
    "movielover8888_film3": "绝版风月.全网绝版稀有资源点播定制",
    "yydf_hzl": "网盘资源合集频道",
    "yeqingjie_GJG666": "爷青回动画分享频道",
    "leoziyuan": "LEO网盘搜集",
    "yunpan139": "网盘资源收藏(移动云盘)",
    "wp123zy": "123网盘",
    "KaiPanshare": "电子书资源分享 📚",
    "D_wusun": "无损音乐分享频道",
    "pxyunpanxunlei": "迅雷网盘资源分享",
    "FLMdongtianfudi": "Fang的资源分享群",
    "QukanMovie": "115影视资源分享频道",
    "yunpanNB": "鹏星の4K影视综合电影云盘站",
    "newproductsourcing": "影视分享频道",
    "rjyxfx": "安卓软件游戏破解资源分享",
    "QQZYDAPP": "QQ资源岛-破解软件分享",
    "xxzlzn": "学习资料指南",
    "zdqxm": "短剧夸克网盘资源分享交流",
    "btzhi": "BT之家btzhi导航频道",
    "PikPak_Share_Channel": "PikPak磁链资源分享",
    "Baidu_netdisk": "百度网盘资源频道",
    "solidsexydoll": "电影资源分享频道",
    "cilidianying": "磁力电影分享",
    "CBduanju": "全网擦边｜电影｜资源分享",
    "jxwpzy": "精选网盘资源",
    "SharePanFilms": "网盘高分影视|资源分享",
    "yoyokuakeduanju": "YOYO资源|夸克|UC|短剧|影视",
    "guoman4K": "国漫 | 网盘频道（4K）",
    "dzsgx": "电子书|阅读|学习|课程",
    "kduanju": "热门短剧每日更新夸克网盘百度网盘资源分享",
    "kuakedongman": "夸克网盘动漫资源",
    "douerpan": "豆儿盘",
    "ciliziyuanku": "磁力资源库",
    "domgmingapk": "DM_share 🕸",
    "baidu_yppan": "百度云盘-云盘盘频道",
    "xiangnikanj": "短剧更新频道|擦边短剧|热播短剧夸克百度网盘免费分享",
    "dianying4k": "4K影视屋(分屋）-蓝光无损电影",
    "kkdj001": "夸克网盘资源俱乐部",
    "Oscar_4Kmovies": "奥斯卡4K蓝光(精品)影视磁力站🍟",
    "liangxingzhinan": "上海瑶池高端/上海spa/上海修车/上海4t/上海95/上海楼凤/女仆",
    "yunpanquark": "夸克网盘资源分享",
    "godupan": "百度网盘资源库🅥",
    "ucshare": "UC网盘资源分享",
    "Q_jilupian": "OPTE.COOL | Q_jilupian",
    "Netdisk_Movies": "海外影视资源频道(夸克、阿里、百度)",
    "jzmm_123pan": "精准猫咪网盘资源",
    "WFYSFX03": "观影视界[GyWEB]",
    "ammmziyuan": "每日资源精选",
    "cili8888": "磁力链接精选福利集",
    "gimy115": "剧迷115影视热更快频道",
    "tgbokee": "梦鱼网盘资源",
    "gimy115iso": "剧迷115影视原盘频道",
    "wpan8": "网盘吧@夸克百度迅雷光鸭网盘资源",
    "gimy100": "剧迷115影视完结频道",
    "regengguangya": "光鸭云盘影视热更频道",
    "regeng123": "123云盘影视热更频道",
    "QuarkFree": "夸克网盘资源收藏夹",
    "gokuapan": "夸克网盘资源库🅥",
    "regeng115": "115网盘影视热更频道",
    "yunpanguangya": "光鸭云盘资源分享频道",
    "peccxin": "盘链交流群",
    "guangyapan_episode": "光鸭云盘资源频道",
    "yy80986098": "影音基地",
    "pan_guangya": "光鸭云盘资源频道",
    "Movie888035": "115影音交流室",
    "yoyokuakeduanjujiaoliuqun": "YOYO资源|夸克|短剧|交流群",
    "AV688": "AV收藏|优质精选|无码破解|中文字幕|番号磁力大全"
}
