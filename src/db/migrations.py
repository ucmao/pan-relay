"""
SQLite 版本化迁移。

用 ``PRAGMA user_version`` 记录数据库结构版本，启动时只执行比当前版本新的迁移，
每个迁移在独立事务中完成，失败即回滚并阻止启动，避免数据库停留在半升级状态。

新增迁移的约定：
1. 在 MIGRATIONS 末尾追加 ``(版本号, 说明, 函数)``，版本号严格递增，已发布的迁移不要再改。
2. 迁移函数必须幂等（重复执行无副作用），因为老库没有版本号时会从头跑一遍。
3. 不要用 schema_sqlite.sql 去"修改"已有表：新库靠 schema 建表，老库靠迁移补齐。
   SQLite 改列类型 / 删列 / 改约束需走"建新表 → 拷数据 → 删旧表 → 改名"流程。
"""

import glob
import logging
import os
import sqlite3
from datetime import datetime
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 每个数据库最多保留的升级前备份数
MAX_BACKUPS = 5


# ---------------------------------------------------------------------------
# 迁移实现
# ---------------------------------------------------------------------------

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table});").fetchall()]


def ensure_legacy_columns(conn: sqlite3.Connection) -> None:
    """
    v1 基线：补齐引入版本号之前通过"启动时检查列"方式加入的字段与表。

    也会在执行 schema_sqlite.sql 之前调用一次，因为 schema 中的部分索引
    依赖这些列，老库缺列时直接执行 schema 会报错。
    """
    res_cols = _columns(conn, "resources")
    if res_cols:
        if "account_id" not in res_cols:
            conn.execute("ALTER TABLE resources ADD COLUMN account_id INTEGER DEFAULT NULL;")
        if "origin_type" not in res_cols:
            conn.execute("ALTER TABLE resources ADD COLUMN origin_type TEXT NOT NULL DEFAULT 'manual';")
        if "cover_url" not in res_cols:
            conn.execute("ALTER TABLE resources ADD COLUMN cover_url TEXT DEFAULT NULL;")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_resources_account ON resources(account_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_resources_origin ON resources(origin_type);")

    temp_cols = _columns(conn, "temp_share")
    if temp_cols and "account_id" not in temp_cols:
        conn.execute("ALTER TABLE temp_share ADD COLUMN account_id INTEGER DEFAULT NULL;")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS resource_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          resource_name TEXT NOT NULL,
          contact TEXT DEFAULT NULL,
          note TEXT DEFAULT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          client_ip TEXT DEFAULT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_res_requests_created ON resource_requests(created_at DESC);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_res_requests_status ON resource_requests(status);")


def migrate_cookie_config_to_accounts(conn: sqlite3.Connection) -> None:
    """
    v2：把旧版单账号凭据表 cookie_config 中的数据导入账号池 cloud_accounts。

    账号池版本直接用 cloud_accounts 替换了 cookie_config 却没有迁移数据，
    老用户升级后凭据会"消失"。这里为每个尚未在账号池中配置的网盘导入一个账号；
    已经手动重新添加过账号的网盘会跳过，避免重复。旧表保留不删，以便回溯。
    """
    if not _table_exists(conn, "cookie_config") or not _table_exists(conn, "cloud_accounts"):
        return

    rows = conn.execute(
        "SELECT cloud_name, cookie, created_at, updated_at FROM cookie_config"
    ).fetchall()

    imported, skipped = 0, 0
    for cloud_name, cookie, created_at, updated_at in rows:
        cloud_name = str(cloud_name or "").strip()
        credential = str(cookie or "").strip()
        if not cloud_name or not credential:
            continue

        exists = conn.execute(
            "SELECT 1 FROM cloud_accounts WHERE cloud_name = ? LIMIT 1", (cloud_name,)
        ).fetchone()
        if exists:
            skipped += 1
            continue

        conn.execute(
            """
            INSERT INTO cloud_accounts (
                cloud_name, account_name, credential, is_active, is_valid,
                priority, weight, created_at, updated_at
            ) VALUES (?, ?, ?, 1, 1, 0, 10,
                      COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))
            """,
            (cloud_name, f"{cloud_name}-账号", credential, created_at, updated_at),
        )
        imported += 1

    if imported or skipped:
        logger.info(
            f"旧版凭据迁移：导入 {imported} 个网盘账号，"
            f"跳过 {skipped} 个（账号池中已存在该网盘账号）。"
        )


MigrationFn = Callable[[sqlite3.Connection], None]

MIGRATIONS: List[Tuple[int, str, MigrationFn]] = [
    (1, "基线：补齐历史字段与求片工单表", ensure_legacy_columns),
    (2, "旧版 cookie_config 凭据导入账号池", migrate_cookie_config_to_accounts),
]

LATEST_VERSION = MIGRATIONS[-1][0]


# ---------------------------------------------------------------------------
# 版本与备份
# ---------------------------------------------------------------------------

def get_user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version;").fetchone()[0])


def _has_user_tables(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
    ).fetchone()
    return row is not None


def needs_migration(conn: sqlite3.Connection) -> bool:
    return get_user_version(conn) < LATEST_VERSION


def backup_database(conn: sqlite3.Connection, db_path: str) -> Optional[str]:
    """
    使用 SQLite 在线备份 API 生成一致性快照（WAL 模式下也安全），
    文件名形如 ``pan_relay.db.bak-v1-20261114-221000``，仅保留最近 MAX_BACKUPS 份。
    """
    version = get_user_version(conn)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{db_path}.bak-v{version}-{stamp}"

    dest = sqlite3.connect(backup_path)
    try:
        conn.backup(dest)
    finally:
        dest.close()

    old_backups = sorted(glob.glob(f"{glob.escape(db_path)}.bak-*"), key=os.path.getmtime)
    for path in old_backups[:-MAX_BACKUPS]:
        try:
            os.remove(path)
        except OSError as exc:
            logger.warning(f"清理旧数据库备份失败 {path}: {exc}")

    return backup_path


# ---------------------------------------------------------------------------
# 执行入口
# ---------------------------------------------------------------------------

def prepare_for_schema(conn: sqlite3.Connection) -> Optional[str]:
    """
    在执行 schema_sqlite.sql 之前调用：
    - 已有数据且版本落后时先做备份；
    - 补齐 schema 中索引依赖的历史列（仅对未完成 v1 的老库）。
    返回备份文件路径（未备份时为 None）。
    """
    backup_path = None
    if _has_user_tables(conn) and needs_migration(conn):
        backup_path = backup_database(conn, _main_db_path(conn))
        logger.info(
            f"检测到数据库需要升级（v{get_user_version(conn)} → v{LATEST_VERSION}），"
            f"已备份至: {backup_path}"
        )

    if get_user_version(conn) < 1:
        ensure_legacy_columns(conn)
        conn.commit()
    return backup_path


def run_migrations(conn: sqlite3.Connection, backup_path: Optional[str] = None) -> int:
    """
    依次执行所有未完成的迁移，返回最终版本号。
    任一迁移失败会回滚该迁移并抛出异常，数据库版本停留在上一个成功的版本。
    """
    current = get_user_version(conn)
    pending = [m for m in MIGRATIONS if m[0] > current]
    if not pending:
        return current

    prev_isolation = conn.isolation_level
    conn.isolation_level = None  # 手动管理事务
    try:
        for version, desc, fn in pending:
            try:
                conn.execute("BEGIN IMMEDIATE;")
                fn(conn)
                conn.execute(f"PRAGMA user_version = {int(version)};")
                conn.execute("COMMIT;")
                logger.info(f"数据库迁移 v{version} 完成：{desc}")
            except Exception:
                conn.execute("ROLLBACK;")
                hint = f"，升级前备份位于 {backup_path}" if backup_path else ""
                logger.exception(f"数据库迁移 v{version}（{desc}）失败，已回滚{hint}")
                raise
    finally:
        conn.isolation_level = prev_isolation

    return get_user_version(conn)


def _main_db_path(conn: sqlite3.Connection) -> str:
    for _, name, path in conn.execute("PRAGMA database_list;").fetchall():
        if name == "main":
            return path
    raise RuntimeError("无法获取数据库文件路径")
