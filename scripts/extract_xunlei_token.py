#!/usr/bin/env python3
"""
迅雷网盘本地客户端凭证一键提取工具
支持跨平台（macOS / Windows / Linux）自动读取本地官方迅雷客户端凭据。
统一输出结构、集成跨平台剪贴板复制，并针对 Windows 新版客户端安全机制提供清晰指引。
"""

import argparse
import glob
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple

# 导入项目路径（如果在项目内运行则支持直接与后台数据库互通）
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def _get_platform_info() -> Tuple[str, str]:
    """获取规范化的系统名称与详细版本"""
    sys_name = platform.system()
    name_map = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}
    display_name = name_map.get(sys_name, sys_name)
    release_str = platform.platform()
    return display_name, release_str


def _get_running_process_dirs() -> Tuple[List[str], List[str]]:
    """检测当前运行中的迅雷进程并向上追溯各级目录"""
    running_procs = []
    found_dirs = []
    current_os = platform.system()

    if current_os == "Windows":
        try:
            ps_cmd = 'powershell -NoProfile -Command "Get-Process -Name \'*thunder*\', \'*xunlei*\' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path"'
            out = subprocess.check_output(ps_cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                line = line.strip()
                if line and line.lower().endswith(".exe") and os.path.isfile(line):
                    running_procs.append(line)
                    curr = os.path.dirname(line)
                    for _ in range(4):
                        if curr and os.path.isdir(curr):
                            found_dirs.append(curr)
                        parent = os.path.dirname(curr)
                        if parent == curr:
                            break
                        curr = parent
        except Exception:
            pass

    return list(dict.fromkeys(running_procs)), list(dict.fromkeys(found_dirs))


def _find_thunder_base_directories(custom_path: Optional[str] = None) -> List[str]:
    """统一收集系统中存放迅雷数据的可能基准目录"""
    base_dirs = []
    current_os = platform.system()

    if custom_path and os.path.exists(custom_path):
        base_dirs.append(custom_path if os.path.isdir(custom_path) else os.path.dirname(custom_path))

    if current_os == "Darwin":
        mac_bases = [
            os.path.expanduser("~/Library/Application Support/Thunder"),
            os.path.expanduser("~/Library/Application Support/ThunderNetwork"),
            os.path.expanduser("~/Library/Application Support/Xunlei"),
        ]
        for p in glob.glob(os.path.expanduser("~/Library/Application Support/Thunder*")):
            if os.path.isdir(p):
                mac_bases.append(p)
        base_dirs.extend([p for p in mac_bases if os.path.isdir(p)])

    elif current_os == "Windows":
        _, proc_dirs = _get_running_process_dirs()
        base_dirs.extend(proc_dirs)

        env_keys = ["APPDATA", "LOCALAPPDATA", "USERPROFILE", "ProgramData"]
        for k in env_keys:
            v = os.environ.get(k)
            if v and os.path.isdir(v):
                for name in os.listdir(v):
                    lower_name = name.lower()
                    if "thunder" in lower_name or "xunlei" in lower_name:
                        full_p = os.path.join(v, name)
                        if os.path.isdir(full_p):
                            base_dirs.append(full_p)

        drives = [f"{d}:\\" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
        for drive in drives:
            for sub in [r"Program Files\Thunder Network", r"Program Files (x86)\Thunder Network", r"Thunder Network"]:
                p = os.path.join(drive, sub)
                if os.path.isdir(p):
                    base_dirs.append(p)

    else:
        linux_bases = [
            os.path.expanduser("~/.config/Thunder"),
            os.path.expanduser("~/.config/ThunderNetwork"),
            os.path.expanduser("~/.local/share/Thunder"),
        ]
        base_dirs.extend([p for p in linux_bases if os.path.isdir(p)])

    unique_dirs = []
    seen = set()
    for d in base_dirs:
        norm = os.path.normpath(d)
        if norm not in seen and os.path.isdir(norm):
            seen.add(norm)
            unique_dirs.append(norm)

    return unique_dirs


def _get_candidate_db_paths(custom_path: Optional[str] = None) -> List[str]:
    """统一获取所有潜在的凭证数据库路径"""
    candidates = []
    base_dirs = _find_thunder_base_directories(custom_path)

    for b_dir in base_dirs:
        candidates.extend(glob.glob(os.path.join(b_dir, "**", "*credential*.db"), recursive=True))
        for sub in ["Account", "account", "UserData", "Profiles", "profiles", "xlaccount"]:
            sub_p = os.path.join(b_dir, sub)
            if os.path.isdir(sub_p):
                candidates.extend(glob.glob(os.path.join(sub_p, "**", "*.db"), recursive=True))

    unique_existing = []
    seen = set()
    for p in candidates:
        norm = os.path.normpath(p)
        key = norm.lower() if platform.system() == "Windows" else norm
        if key not in seen and os.path.isfile(norm):
            seen.add(key)
            unique_existing.append(norm)

    unique_existing.sort(key=lambda x: (0 if "credential" in os.path.basename(x).lower() else 1, len(x)))
    return unique_existing


def _find_device_id_near_path(db_path: str) -> str:
    """尝试查找关联的设备标识数据库"""
    base_dir = os.path.dirname(db_path)
    search_dirs = [
        os.path.abspath(os.path.join(base_dir, "..", "captcha")),
        os.path.abspath(os.path.join(base_dir, "..", "..", "captcha")),
        os.path.abspath(os.path.join(base_dir, "captcha")),
    ]
    for s_dir in search_dirs:
        if os.path.exists(s_dir):
            cap_dbs = glob.glob(os.path.join(s_dir, "**", "*.db"), recursive=True)
            if cap_dbs:
                parts = cap_dbs[0].split(os.sep)
                if len(parts) >= 3:
                    return parts[-3]
    return ""


def _parse_credential_payload(payload_str: str, source_path: str) -> Optional[Dict[str, str]]:
    """统一解析 JSON 格式凭据"""
    try:
        data = json.loads(payload_str)
        if not isinstance(data, dict):
            return None
        rf = data.get("refresh_token") or data.get("refreshToken") or data.get("token")
        if not rf:
            return None

        uid = data.get("user_id") or data.get("userId") or data.get("sub") or data.get("uid") or ""
        client_id = data.get("client_id") or data.get("clientId") or "YBJdb1UyFQJwh_nS"
        device_id = data.get("device_id") or data.get("deviceId") or _find_device_id_near_path(source_path)

        return {
            "refresh_token": str(rf).strip(),
            "user_id": str(uid).strip(),
            "client_id": str(client_id).strip(),
            "device_id": str(device_id).strip() if device_id else "08c6b0f4b0a64c4f8901413d917eb64c",
            "_source_file": source_path,
        }
    except Exception:
        return None


def _try_extract_from_sqlite(db_path: str, debug: bool = False) -> Optional[Dict[str, str]]:
    """通用深度扫描 SQLite 数据库"""
    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, f"xl_temp_{os.getpid()}_{abs(hash(db_path))}.db")
    try:
        shutil.copy2(db_path, temp_file)
        used_path = temp_file
    except Exception:
        used_path = db_path

    try:
        conn = sqlite3.connect(used_path, timeout=3.0)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_")]

        for tbl in tables:
            try:
                cur.execute(f"PRAGMA table_info(`{tbl}`)")
                col_names = [c[1] for c in cur.fetchall()]
                cur.execute(f"SELECT * FROM `{tbl}` LIMIT 100")
                rows = cur.fetchall()

                for row in rows:
                    row_dict = {}
                    for col_name, val in zip(col_names, row):
                        if isinstance(val, (bytes, bytearray)):
                            for enc in ["utf-8", "gbk", "latin-1"]:
                                try:
                                    val = val.decode(enc)
                                    break
                                except Exception:
                                    pass
                        row_dict[col_name] = val

                        if isinstance(val, str):
                            val_str = val.strip()
                            if ("{" in val_str and "}" in val_str) or ("token" in val_str.lower()):
                                res = _parse_credential_payload(val_str, db_path)
                                if res:
                                    conn.close()
                                    return res

                                m = re.search(r'["\']refresh_token["\']\s*:\s*["\']([^"\']+)["\']', val_str, re.I)
                                if m:
                                    conn.close()
                                    return {
                                        "refresh_token": m.group(1).strip(),
                                        "user_id": "",
                                        "client_id": "YBJdb1UyFQJwh_nS",
                                        "device_id": _find_device_id_near_path(db_path) or "08c6b0f4b0a64c4f8901413d917eb64c",
                                        "_source_file": db_path,
                                    }

                    for col_name, val in row_dict.items():
                        c_lower = col_name.lower().replace("_", "")
                        if "refreshtoken" in c_lower or (c_lower in ["token", "credential"] and isinstance(val, str) and len(val) > 25):
                            if isinstance(val, str) and len(val.strip()) > 15 and not val.strip().startswith("{"):
                                conn.close()
                                return {
                                    "refresh_token": val.strip(),
                                    "user_id": str(row_dict.get("user_id") or ""),
                                    "client_id": "YBJdb1UyFQJwh_nS",
                                    "device_id": _find_device_id_near_path(db_path) or "08c6b0f4b0a64c4f8901413d917eb64c",
                                    "_source_file": db_path,
                                }
            except Exception:
                continue
        conn.close()
    except Exception:
        pass
    finally:
        if used_path != db_path and os.path.exists(used_path):
            try:
                os.remove(used_path)
            except Exception:
                pass

    return None


def extract_thunder_credentials(custom_path: Optional[str] = None, debug: bool = False) -> Optional[Dict[str, str]]:
    """跨平台统一凭证提取"""
    candidate_paths = _get_candidate_db_paths(custom_path)
    for db_path in candidate_paths:
        cred = _try_extract_from_sqlite(db_path, debug=debug)
        if cred:
            return cred
    return None


def _copy_to_system_clipboard(text: str) -> bool:
    """跨平台复制内容至系统剪贴板（Windows / macOS / Linux）"""
    sys_name = platform.system()
    try:
        if sys_name == "Windows":
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(input=text.strip().encode("gbk", errors="ignore"))
            return p.returncode == 0
        elif sys_name == "Darwin":
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.strip().encode("utf-8"))
            return p.returncode == 0
        elif sys_name == "Linux":
            for tool in ["xclip -selection clipboard", "xsel -b"]:
                try:
                    p = subprocess.Popen(tool.split(), stdin=subprocess.PIPE)
                    p.communicate(input=text.strip().encode("utf-8"))
                    if p.returncode == 0:
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def _print_debug_report(custom_path: Optional[str] = None):
    """仅在显式传入 --debug / --diagnose 时输出的排查报告"""
    sys_name, rel_str = _get_platform_info()
    print("=" * 65)
    print(" 🛠️  [环境诊断报告 / Diagnostic Details]")
    print(f" • 操作系统: {sys_name} ({rel_str})")

    running_procs, proc_dirs = _get_running_process_dirs()
    if running_procs:
        print(f" • 检测到的迅雷进程 ({len(running_procs)} 个):")
        for p in running_procs:
            print(f"    - {p}")
    else:
        print(" • 检测到的迅雷进程: 暂无活跃进程")

    base_dirs = _find_thunder_base_directories(custom_path)
    print(f" • 扫描到的数据目录 ({len(base_dirs)} 个):")
    for d in base_dirs[:10]:
        print(f"    - {d}")

    candidate_paths = _get_candidate_db_paths(custom_path)
    print(f" • 探测到的数据库文件 ({len(candidate_paths)} 个):")
    for cp in candidate_paths[:10]:
        print(f"    - {cp}")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="迅雷网盘客户端本地凭证一键提取助手（支持 macOS / Windows / Linux）"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="提取成功后自动存入项目后台云盘数据库（在 pan-relay 项目根目录运行时可用）",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="手动指定迅雷客户端安装路径或数据目录",
    )
    parser.add_argument(
        "--debug",
        "--diagnose",
        action="store_true",
        help="开启详细诊断模式（输出扫描路径与进程探测详情）",
    )
    args = parser.parse_args()

    sys_name, _ = _get_platform_info()

    print("=" * 65)
    print(f"   ⚡ 迅雷网盘客户端凭证一键提取工具 (当前平台: {sys_name})")
    print("=" * 65)

    if args.debug:
        _print_debug_report(args.path)

    cred = extract_thunder_credentials(args.path, debug=args.debug)

    if cred:
        source_file = cred.pop("_source_file", "")
        cred_json = json.dumps(cred, ensure_ascii=False)

        print("\n✅ 成功从本地迅雷客户端提取到认证凭证！")
        print(f" • 凭证来源: {source_file}")
        print(f" • 账号 UID : {cred.get('user_id') or '已自动识别'}")
        print(f" • 客户端 ID: {cred.get('client_id')}")
        print(f" • 设备标识: {cred.get('device_id')}")
        print("\n📋 凭证内容 (已自动格式化)：")
        print("-" * 65)
        print(cred_json)
        print("-" * 65)

        if _copy_to_system_clipboard(cred_json):
            print("✨ [提示] 凭证 JSON 已自动复制到系统剪贴板！可直接按 Ctrl+V / Cmd+V 粘贴发送。")

        if args.save:
            try:
                from src.db.credentials import save_cookie
                ok, msg = save_cookie("迅雷网盘", cred_json)
                if ok:
                    print("\n🎉 已成功自动保存到系统云盘数据库 (cloud_name='迅雷网盘')！")
                else:
                    print(f"\n❌ 保存至数据库失败: {msg}")
            except ModuleNotFoundError:
                print("\n💡 提示: 当前为独立运行模式，未检测到 pan-relay 项目后台环境，直接复制上方凭证即可。")
            except Exception as exc:
                print(f"\n❌ 保存至数据库异常: {exc}")
        else:
            print("\n💡 提示: 若在项目根目录下执行 `python extract_xunlei_token.py --save` 可一键入库。")

    else:
        print(f"\n⚠️  未能从当前 {sys_name} 本地客户端中读取到有效的持久化凭据。")

        if sys_name == "Windows":
            print("\n📌 【Windows 平台说明与推荐方案】")
            print(" 1. 原因说明：")
            print("    Windows 最新版官方迅雷客户端（Thunder 11/12）基于全新安全架构，")
            print("    登录态仅在运行期内存中维护，已不再向本地磁盘保存明文 refresh_token。")
            print("\n 2. 推荐获取方式（手机迅雷 APP 抓包，耗时约 1 分钟）：")
            print("    pan-relay 核心驱动基于官方移动端原生协议，抓取手机端 Token 兼容性最高、最稳定：")
            print("    ① 手机开启抓包工具（iOS 推荐免费的 Stream / 安卓推荐 Reqable、小黄鸟）；")
            print("    ② 打开手机迅雷 APP，退出后重新登录；")
            print("    ③ 过滤域名 xluser-ssl.xunlei.com，在 /v1/auth/token 接口响应中复制 refresh_token；")
            print("    ④ 直接将得到的 refresh_token 填入系统后台即可！")

        elif sys_name == "Darwin":
            print("\n📌 【macOS 平台排查建议】")
            print(" 1. 请确认已打开 Mac 官方迅雷客户端并完成扫码登录；")
            print(" 2. 登录后退出迅雷（Cmd + Q）让数据充分落盘，然后重新执行本命令。")

        else:
            print("\n📌 【Linux 平台排查建议】")
            print(" 1. 请确认 Linux 下迅雷已安装且登录态配置在 ~/.config/Thunder 下；")
            print(" 2. 或直接通过手机迅雷 APP 抓包获取 refresh_token 填入后台。")

        if not args.debug:
            print("\n💡 提示: 若需排查本地扫描详情，可附加 `--debug` 参数重新执行。")


if __name__ == "__main__":
    main()
