#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pan-Relay 管理员密码命令行重置工具
用法：
    python scripts/reset_password.py [新密码] [新用户名(可选)]
示例：
    python scripts/reset_password.py MyNewPass@2026
    python scripts/reset_password.py MyNewPass@2026 admin
"""

import getpass
import os
import sys

# 将项目根目录添加到 sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.db.connection import init_sqlite_db
from src.services.admin_auth_service import get_admin_username, reset_admin_password


def main():
    print("=" * 60)
    print(" Pan-Relay 管理员密码应急重置工具")
    print("=" * 60)

    # 确保数据库表已初始化
    init_sqlite_db()

    current_user = get_admin_username()
    print(f"当前管理员用户名: {current_user}")

    new_password = None
    target_username = None

    if len(sys.argv) >= 2:
        new_password = sys.argv[1].strip()
        if len(sys.argv) >= 3:
            target_username = sys.argv[2].strip()
    else:
        try:
            pwd1 = getpass.getpass("请输入新管理员密码（至少 6 位）: ").strip()
            if not pwd1:
                print("❌ 密码不能为空，操作已取消。")
                sys.exit(1)
            pwd2 = getpass.getpass("请再次输入新密码确认: ").strip()
            if pwd1 != pwd2:
                print("❌ 两次输入的密码不一致，操作已取消。")
                sys.exit(1)
            new_password = pwd1

            custom_user = input(f"修改管理员用户名 (直接回车保持为 '{current_user}'): ").strip()
            if custom_user:
                target_username = custom_user
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消。")
            sys.exit(0)

    if not new_password or len(new_password) < 6:
        print("❌ 错误：密码长度至少需要 6 个字符！")
        sys.exit(1)

    success, msg = reset_admin_password(new_password, new_username=target_username)
    if success:
        final_user = target_username or current_user
        print("\n✅ 密码重置成功！")
        print(f"   用户名: {final_user}")
        print("   新密码已加密持久化至数据库，免重启即时生效。")
        print("   您现在可以使用新密码登录管理后台。")
    else:
        print(f"\n❌ 重置失败: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
