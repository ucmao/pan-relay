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

# 获取当前脚本所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 设置 SECRET_KEY，用于会话管理
SECRET_KEY = os.getenv('SECRET_KEY')

# 网盘信息
QUARK_PAN_COOKIE = os.getenv('QUARK_PAN_COOKIE')
BAIDU_PAN_COOKIE = os.getenv('BAIDU_PAN_COOKIE')
DEFAULT_SAVE_DIR = os.getenv('DEFAULT_SAVE_DIR')

# 管理员账号密码
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

# Telegram 公开频道搜索
TG_SEARCH_ENABLED = _get_bool_env("TG_SEARCH_ENABLED", True)
TG_CHANNELS = [
    channel.strip().lstrip("@").strip("/")
    for channel in os.getenv("TG_CHANNELS", "tgsearchers7").split(",")
    if channel.strip()
]
TG_SEARCH_TIMEOUT = _get_int_env("TG_SEARCH_TIMEOUT", 10)
TG_SEARCH_MAX_WORKERS = _get_int_env("TG_SEARCH_MAX_WORKERS", 4)
TG_PROXY = os.getenv("TG_PROXY", "").strip()

# JWT密钥
SECRET_KEY = os.getenv('SECRET_KEY')

# 数据库配置，从环境变量获取
db_config = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST', 'localhost'),  # 提供默认值
    'database': os.getenv('DB_DATABASE'),
    'port': int(os.getenv('DB_PORT', 3306)),    # 转换为整数并提供默认值
    'charset': os.getenv('DB_CHARSET', 'utf8mb4')
}

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
