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
    "tgsearchers7,tgsearchers3,tgsearchers6,Aliyun_4K_Movies,bdbdndn11,yunpanx,"
    "bsbdbfjfjff,yp123pan,sbsbsnsqq,yunpanxunlei,tianyifc,BaiduCloudDisk,txtyzy,"
    "peccxinpd,gotopan,PanjClub,kkxlzy,baicaoZY,MCPH01,MCPH02,MCPH03,bdwpzhpd,"
    "ysxb48,jdjdn1111,yggpan,MCPH086,zaihuayun,Q66Share,ucwpzy,shareAliyun,alyp_1,"
    "dianyingshare,Quark_Movies,XiangxiuNBB,ydypzyfx,ucquark,xx123pan,"
    "yingshifenxiang123,zyfb123,tyypzhpd,tianyirigeng,cloudtianyi,hdhhd21,Lsp115,"
    "oneonefivewpfx,qixingzhenren,taoxgzy,Channel_Shares_115,tyysypzypd,vip115hot,"
    "wp123zy,yunpan139,yunpan189,yunpanuc,yydf_hzl,leoziyuan,Q_dongman,"
    "yoyokuakeduanju,TG654TG,WFYSFX02,QukanMovie,yeqingjie_GJG666,"
    "movielover8888_film3,Baidu_netdisk,D_wusun,FLMdongtianfudi,KaiPanshare,"
    "QQZYDAPP,rjyxfx,PikPak_Share_Channel,btzhi,newproductsourcing,cctv1211,"
    "duan_ju,QuarkFree,yunpanNB,kkdj001,xxzlzn,pxyunpanxunlei,jxwpzy,kuakedongman,"
    "liangxingzhinan,xiangnikanj,solidsexydoll,guoman4K,zdqxm,kduanju,cilidianying,"
    "CBduanju,SharePanFilms,dzsgx,BooksRealm,Oscar_4Kmovies,douerpan,baidu_yppan,"
    "Q_jilupian,Netdisk_Movies,yunpanquark,ammmziyuan,ciliziyuanku,cili8888,"
    "jzmm_123pan,Q_dianying,domgmingapk,dianying4k,q_dianshiju,tgbokee,ucshare,"
    "godupan,gokuapan,gimy115,WFYSFX03,peccxin,Movie888035,xlwpzy,zyywpzy,wydwpzy,"
    "gimy100,gimy115iso,wpan8,mqte5,regengguangya,yunpanguangya,regeng115,regeng123,"
    "yoyokuakeduanjujiaoliuqun,yy80986098,pan_guangya,guangyapan_episode,AV688,pikpakpan"
)
TG_CHANNELS = [
    channel.strip().lstrip("@").strip("/")
    for channel in os.getenv("TG_CHANNELS", DEFAULT_TG_CHANNELS).split(",")
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
