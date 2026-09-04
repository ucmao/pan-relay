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
    "tgsearchers3,sbsbsnsqq,tgsearchers6,yggpan,kkxlzy,dianyingshare,alyp_1,cloudtianyi,qixingzhenren,ydypzyfx,WFYSFX02,cctv1211,duan_ju,liangxingzhinan,ammmziyuan,cili8888,q_dianshiju,peccxin,xlwpzy,zyywpzy,Movie888035,wydwpzy,yoyokuakeduanjujiaoliuqun,AV688,pikpakpan"
)

# 插件首次初始化状态；由发布前健康检测脚本同步。
DEFAULT_PLUGIN_SETTINGS = {
    'sample_scraper': False,
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
