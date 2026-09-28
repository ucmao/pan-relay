#!/usr/bin/env python3
"""
迅雷网盘本地客户端凭证一键提取工具
支持跨平台（Windows / macOS / Linux）从已登录的迅雷客户端中自动读取认证凭证，并支持一键写入系统配置数据库。
"""

import argparse
import glob
import json
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
from typing import Dict, List, Optional

# 导入项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def _get_candidate_db_paths() -> List[str]:
    """获取不同操作系统下迅雷客户端 credentials.db 的潜在路径列表"""
    candidates = []
    system = platform.system()

    # 1. macOS 路径
    if system == "Darwin" or not system:
        candidates.append(
            os.path.expanduser("~/Library/Application Support/Thunder/Account/account/credentials.db")
        )
        candidates.extend(
            glob.glob(
                os.path.expanduser("~/Library/Application Support/Thunder*/Account/**/credentials.db"),
                recursive=True,
            )
        )

    # 2. Windows 路径
    if system == "Windows" or not system:
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")
        userprofile = os.environ.get("USERPROFILE")
        win_bases = [p for p in (appdata, localappdata, userprofile) if p and os.path.exists(p)]

        for base in win_bases:
            candidates.extend([
                os.path.join(base, "ThunderNetwork", "Thunder", "UserData", "Account", "account", "credentials.db"),
                os.path.join(base, "ThunderNetwork", "Thunder", "UserData", "Account", "credentials.db"),
                os.path.join(base, "ThunderNetwork", "Thunder", "Account", "account", "credentials.db"),
                os.path.join(base, "Thunder", "Account", "account", "credentials.db"),
                os.path.join(base, "Thunder", "UserData", "Account", "credentials.db"),
            ])
            # 通配模糊搜索常见目录
            candidates.extend(
                glob.glob(os.path.join(base, "Thunder*", "UserData", "Account", "**", "credentials.db"), recursive=True)
            )
            candidates.extend(
                glob.glob(os.path.join(base, "Thunder*", "Account", "**", "credentials.db"), recursive=True)
            )

    # 3. Linux 路径
    if system == "Linux" or not system:
        candidates.extend([
            os.path.expanduser("~/.config/Thunder/Account/account/credentials.db"),
            os.path.expanduser("~/.local/share/Thunder/Account/account/credentials.db"),
            os.path.expanduser("~/.config/ThunderNetwork/Account/account/credentials.db"),
        ])

    # 去重且仅保留已存在的路径
    unique_existing = []
    seen = set()
    for p in candidates:
        if p and p not in seen and os.path.isfile(p):
            seen.add(p)
            unique_existing.append(p)

    return unique_existing


def _find_device_id_near_path(db_path: str) -> str:
    """尝试在 credentials.db 同级或父级查找关联的 captcha 数据库以获取 device_id"""
    base_dir = os.path.dirname(db_path)
    search_dirs = [
        os.path.abspath(os.path.join(base_dir, "..", "captcha")),
        os.path.abspath(os.path.join(base_dir, "..", "..", "captcha")),
        os.path.abspath(os.path.join(base_dir, "captcha")),
    ]

    for s_dir in search_dirs:
        if os.path.exists(s_dir):
            cap_dbs = glob.glob(os.path.join(s_dir, "*", "*", "data.db"))
            if not cap_dbs:
                cap_dbs = glob.glob(os.path.join(s_dir, "**", "*.db"), recursive=True)
            if cap_dbs:
                parts = cap_dbs[0].split(os.sep)
                if len(parts) >= 3:
                    # 路径结构一般形如 .../captcha/{device_id}/{client_id}/data.db
                    return parts[-3]

    return ""


def extract_thunder_credentials() -> Optional[Dict[str, str]]:
    """跨平台（Windows / macOS / Linux）提取本地迅雷客户端凭证"""
    candidate_paths = _get_candidate_db_paths()
    if not candidate_paths:
        return None

    temp_dir = tempfile.gettempdir()

    for db_path in candidate_paths:
        # 为防止 Windows 上因客户端独占访问导致文件锁异常，优先复制临时副本进行读取
        temp_file = os.path.join(temp_dir, f"xl_cred_temp_{os.getpid()}.db")
        used_path = db_path
        copied = False
        try:
            shutil.copy2(db_path, temp_file)
            used_path = temp_file
            copied = True
        except Exception:
            used_path = db_path

        try:
            conn = sqlite3.connect(used_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]

            rows = []
            if "storage" in tables:
                cur.execute("SELECT key, value FROM storage WHERE key LIKE 'credentials_%'")
                rows = cur.fetchall()
            elif "credentials" in tables:
                cur.execute("SELECT key, value FROM credentials WHERE key LIKE 'credentials_%'")
                rows = cur.fetchall()
            conn.close()

            for key, val in rows:
                try:
                    data = json.loads(val)
                    rf = data.get("refresh_token")
                    uid = data.get("user_id") or data.get("sub") or ""
                    client_id = data.get("client_id") or "YBJdb1UyFQJwh_nS"
                    device_id = data.get("device_id") or _find_device_id_near_path(db_path)

                    if rf:
                        return {
                            "refresh_token": rf,
                            "user_id": str(uid),
                            "client_id": client_id,
                            "device_id": device_id or "08c6b0f4b0a64c4f8901413d917eb64c",
                            "_source_file": db_path,
                        }
                except Exception:
                    continue
        except Exception as exc:
            pass
        finally:
            if copied and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    return None


def main():
    parser = argparse.ArgumentParser(description="迅雷网盘登录凭证跨平台提取助手")
    parser.add_argument(
        "--save",
        action="store_true",
        help="直接将提取到的凭证自动保存到系统云盘配置数据库中",
    )
    args = parser.parse_args()

    current_os = platform.system()
    os_name_map = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}
    os_display = os_name_map.get(current_os, current_os)

    print("=" * 60)
    print(f"   迅雷网盘客户端凭证一键提取工具 (当前系统: {os_display})")
    print("=" * 60)

    cred = extract_thunder_credentials()
    if not cred:
        print(f"❌ 未在 {os_display} 系统中检测到已登录的官方迅雷客户端数据。")
        print("\n💡 建议获取方式：")
        print(f"1. 请确认当前 {os_display} 电脑已安装官方迅雷并已完成账号扫码登录，然后重新执行本命令；")
        print("2. 或使用手机迅雷 APP 抓包获取 xluser-ssl.xunlei.com/v1/auth/token 请求响应中的 refresh_token。")
        return

    source_file = cred.pop("_source_file", "")
    cred_json = json.dumps(cred, ensure_ascii=False)

    print(f"\n✅ 成功从本地迅雷客户端提取到认证凭证！(来源: {source_file})")
    print(f"账号 UID : {cred.get('user_id')}")
    print(f"客户端 ID: {cred.get('client_id')}")
    print(f"设备 ID  : {cred.get('device_id')}")
    print("\n📋 凭证内容 (可直接复制并粘贴至后台「云盘凭证」配置面板)：")
    print("-" * 60)
    print(cred_json)
    print("-" * 60)

    if args.save:
        try:
            from src.db.credentials import save_cookie
            ok, msg = save_cookie("迅雷网盘", cred_json)
            if ok:
                print("\n🎉 已成功自动保存到系统数据库 (cloud_name='迅雷网盘')！无需手动复制。")
            else:
                print(f"\n❌ 保存至数据库失败: {msg}")
        except Exception as exc:
            print(f"\n❌ 导入数据库异常: {exc}")
    else:
        print("\n💡 提示: 重新执行 `python3 scripts/extract_xunlei_token.py --save` 可直接存入数据库。")


if __name__ == "__main__":
    main()
