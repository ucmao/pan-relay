import datetime
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple
from werkzeug.security import check_password_hash, generate_password_hash

from src.configs.app_config import ADMIN_PASSWORD, ADMIN_USERNAME
from src.db.system_configs import get_config_value, set_config_value

logger = logging.getLogger(__name__)

ADMIN_AUTH_CONFIG_KEY = "admin_auth_config"
DEFAULT_PASSWORD_SEED = "admin123"


def _build_default_config(username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    user = (username or ADMIN_USERNAME or "admin").strip()
    raw_pwd = password if password is not None else (ADMIN_PASSWORD or DEFAULT_PASSWORD_SEED)
    return {
        "username": user,
        "password_hash": generate_password_hash(raw_pwd),
        "is_default_password": (raw_pwd == DEFAULT_PASSWORD_SEED),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def get_admin_auth_config() -> Dict[str, Any]:
    """
    获取管理员凭据配置。
    若数据库中尚无配置，则从环境变量/默认配置进行初始化落库。
    同时支持通过环境变量 ADMIN_RESET_PASSWORD 或 FORCE_RESET_PASSWORD 进行强制重置。
    """
    raw_value = get_config_value(ADMIN_AUTH_CONFIG_KEY)
    cfg: Optional[Dict[str, Any]] = None

    if raw_value:
        try:
            cfg = json.loads(raw_value)
            if not isinstance(cfg, dict):
                cfg = None
        except (TypeError, json.JSONDecodeError):
            logger.warning("管理员认证配置解析失败，重新生成默认配置")
            cfg = None

    if not cfg:
        cfg = _build_default_config()
        set_config_value(ADMIN_AUTH_CONFIG_KEY, cfg)
        logger.info(f"系统首次初始化管理员账号: {cfg['username']}")

    # 检查环境变量强制重置机制
    force_reset_pwd = os.getenv("ADMIN_RESET_PASSWORD") or os.getenv("FORCE_RESET_PASSWORD")
    if force_reset_pwd and force_reset_pwd.strip():
        new_pwd = force_reset_pwd.strip()
        # 避免每次都重复写库，仅当当前哈希无法匹配新密码时才更新
        stored_hash = cfg.get("password_hash", "")
        need_update = True
        if stored_hash:
            try:
                if check_password_hash(stored_hash, new_pwd):
                    need_update = False
            except Exception:
                pass

        if need_update:
            cfg["password_hash"] = generate_password_hash(new_pwd)
            cfg["is_default_password"] = (new_pwd == DEFAULT_PASSWORD_SEED)
            cfg["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            set_config_value(ADMIN_AUTH_CONFIG_KEY, cfg)
            logger.warning("已通过环境变量 ADMIN_RESET_PASSWORD/FORCE_RESET_PASSWORD 强制重置管理员密码")

    return cfg


def init_admin_auth() -> None:
    """系统启动时的管理员认证初始化钩子"""
    try:
        get_admin_auth_config()
    except Exception as e:
        logger.error(f"初始化管理员认证配置异常: {e}")


def get_admin_username() -> str:
    """获取当前管理员用户名"""
    cfg = get_admin_auth_config()
    return cfg.get("username", ADMIN_USERNAME or "admin")


def is_using_default_password() -> bool:
    """检查管理员是否仍在使用系统默认弱口令 (admin123)"""
    cfg = get_admin_auth_config()
    if cfg.get("is_default_password") is True:
        return True

    stored_hash = cfg.get("password_hash")
    if stored_hash:
        try:
            return check_password_hash(stored_hash, DEFAULT_PASSWORD_SEED)
        except Exception:
            pass
    return False


def verify_admin_credentials(username: str, password: str) -> Tuple[bool, str]:
    """
    验证管理员账号与密码
    """
    if not username or not password:
        return False, "账号或密码不能为空"

    cfg = get_admin_auth_config()
    expected_username = cfg.get("username", ADMIN_USERNAME or "admin")

    if username.strip() != expected_username:
        return False, "账号或密码错误"

    stored_hash = cfg.get("password_hash")
    if not stored_hash:
        if password == (ADMIN_PASSWORD or DEFAULT_PASSWORD_SEED):
            return True, "验证成功"
        return False, "账号或密码错误"

    try:
        is_valid = check_password_hash(stored_hash, password)
    except Exception as e:
        logger.warning(f"密码哈希比对发生异常: {e}")
        is_valid = False

    # 平滑过渡兼容：若旧配置是明文，则自动升级为哈希存储
    if not is_valid and password == stored_hash:
        cfg["password_hash"] = generate_password_hash(password)
        cfg["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        set_config_value(ADMIN_AUTH_CONFIG_KEY, cfg)
        logger.info("已自动将旧明文管理员密码迁移升级为加盐哈希")
        is_valid = True

    if is_valid:
        return True, "验证成功"
    return False, "账号或密码错误"


def change_admin_password(
    old_password: str,
    new_password: str,
    new_username: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    管理员在后台修改密码（必须先验证旧密码）
    """
    cfg = get_admin_auth_config()
    current_username = cfg.get("username", ADMIN_USERNAME or "admin")

    # 1. 验证旧密码
    is_valid, _ = verify_admin_credentials(current_username, old_password)
    if not is_valid:
        return False, "当前原密码输入错误"

    # 2. 校验新密码格式
    clean_new_pwd = (new_password or "").strip()
    if not clean_new_pwd:
        return False, "新密码不能为空"
    if len(clean_new_pwd) < 6:
        return False, "新密码长度至少需要 6 个字符"

    clean_new_user = (new_username or "").strip()
    if old_password == clean_new_pwd and (not clean_new_user or clean_new_user == current_username):
        return False, "新密码不能与当前原密码相同"

    # 3. 更新配置
    if clean_new_user:
        cfg["username"] = clean_new_user
    cfg["password_hash"] = generate_password_hash(clean_new_pwd)
    cfg["is_default_password"] = (clean_new_pwd == DEFAULT_PASSWORD_SEED)
    cfg["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    success = set_config_value(ADMIN_AUTH_CONFIG_KEY, cfg)
    if success:
        logger.info(f"管理员账号/密码已成功更新，用户名: {cfg['username']}")
        return True, "密码修改成功"
    return False, "数据库保存失败，请稍后重试"


def reset_admin_password(
    new_password: str,
    new_username: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    命令行或系统紧急重置管理员密码（无需提供旧密码）
    """
    clean_new_pwd = (new_password or "").strip()
    if not clean_new_pwd:
        return False, "新密码不能为空"
    if len(clean_new_pwd) < 6:
        return False, "新密码长度至少需要 6 个字符"

    cfg = get_admin_auth_config()
    clean_new_user = (new_username or "").strip()
    if clean_new_user:
        cfg["username"] = clean_new_user

    cfg["password_hash"] = generate_password_hash(clean_new_pwd)
    cfg["is_default_password"] = (clean_new_pwd == DEFAULT_PASSWORD_SEED)
    cfg["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    success = set_config_value(ADMIN_AUTH_CONFIG_KEY, cfg)
    if success:
        logger.info(f"管理员密码已通过重置接口更新，用户名: {cfg['username']}")
        return True, "管理员密码重置成功"
    return False, "数据库保存失败，请稍后重试"
