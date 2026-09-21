import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

from src.configs.app_config import SQLITE_DB_PATH, BASE_DIR

logger = logging.getLogger(__name__)
Error = sqlite3.Error


class SQLiteCursorWrapper:
    """包装 sqlite3.Cursor，提供纯净原生 SQLite 游标操作与字典行解析。"""

    def __init__(self, raw_cursor: sqlite3.Cursor, as_dict: bool = False):
        self._cursor = raw_cursor
        self.as_dict = as_dict

    def execute(self, sql: str, params=None):
        if params is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, params)

    def executemany(self, sql: str, params=None):
        if params is None:
            return self._cursor.executemany(sql)
        return self._cursor.executemany(sql, params)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self.as_dict and self._cursor.description:
            return {col[0]: row[idx] for idx, col in enumerate(self._cursor.description)}
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        if self.as_dict and self._cursor.description:
            cols = [col[0] for col in self._cursor.description]
            return [{cols[i]: val for i, val in enumerate(r)} for r in rows]
        return rows

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> Optional[int]:
        return self._cursor.lastrowid

    def close(self):
        self._cursor.close()

    def __iter__(self):
        for row in self.fetchall():
            yield row


class SQLiteConnectionWrapper:
    """包装 sqlite3.Connection，提供便捷的 cursor/commit/rollback 行为。"""

    def __init__(self, raw_conn: sqlite3.Connection):
        self._conn = raw_conn

    def cursor(self, as_dict: bool = False) -> SQLiteCursorWrapper:
        return SQLiteCursorWrapper(self._conn.cursor(), as_dict=as_dict)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def execute(self, sql: str, params=None):
        cursor = self.cursor()
        return cursor.execute(sql, params)

    def executescript(self, script: str):
        return self._conn.executescript(script)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()


_db_initialized = False


def init_sqlite_db():
    """初始化 SQLite 数据库，自动建表与填充默认配置。"""
    global _db_initialized
    db_path = SQLITE_DB_PATH
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    schema_file = os.path.join(BASE_DIR, "schema_sqlite.sql")

    try:
        raw_conn = sqlite3.connect(db_path, timeout=30.0)
        raw_conn.execute("PRAGMA journal_mode=WAL;")
        raw_conn.execute("PRAGMA synchronous=NORMAL;")

        if os.path.exists(schema_file):
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            raw_conn.executescript(schema_sql)
            logger.info("SQLite 数据库初始化与表结构校验完成。")
        else:
            logger.error(f"未找到数据库初始化脚本: {schema_file}")

        raw_conn.close()
        _db_initialized = True

        try:
            from src.services.system_config_service import init_default_search_sources
            init_default_search_sources()
        except Exception as e:
            logger.warning(f"自动初始化默认全量搜索源配置失败: {e}")
    except Exception as e:
        logger.error(f"初始化 SQLite 数据库失败: {e}")
        raise


def get_db_connection() -> Optional[SQLiteConnectionWrapper]:
    """
    获取 SQLite 数据库连接。
    返回封装后的 SQLiteConnectionWrapper。
    """
    global _db_initialized
    if not _db_initialized or not os.path.exists(SQLITE_DB_PATH):
        init_sqlite_db()
    else:
        try:
            with sqlite3.connect(SQLITE_DB_PATH, timeout=5.0) as check_conn:
                row = check_conn.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='resources';"
                ).fetchone()
                if not row or row[0] == 0:
                    init_sqlite_db()
        except Exception:
            init_sqlite_db()

    try:
        raw_conn = sqlite3.connect(SQLITE_DB_PATH, timeout=30.0)
        raw_conn.execute("PRAGMA journal_mode=WAL;")
        raw_conn.execute("PRAGMA synchronous=NORMAL;")
        return SQLiteConnectionWrapper(raw_conn)
    except sqlite3.Error as err:
        logger.error(f"连接 SQLite 数据库失败: {err}")
        return None


@contextmanager
def db_cursor(as_dict: bool = False):
    """
    统一管理连接与游标生命周期的上下文管理器。
    """
    conn = get_db_connection()
    if not conn:
        yield None
        return

    cursor = conn.cursor(as_dict=as_dict)
    try:
        yield cursor
        conn.commit()
    except Exception as err:
        logger.error(f"数据库操作出错: {err}")
        conn.rollback()
        raise
    finally:
        try:
            cursor.close()
        finally:
            conn.close()


def vacuum_db() -> bool:
    """执行 SQLite VACUUM，压缩数据库并自动归还硬盘碎片空间。"""
    try:
        raw_conn = sqlite3.connect(SQLITE_DB_PATH, timeout=60.0)
        raw_conn.execute("VACUUM;")
        raw_conn.close()
        logger.info("SQLite 数据库已成功执行 VACUUM 压缩，已归还磁盘空间。")
        return True
    except Exception as e:
        logger.error(f"执行 VACUUM 释放磁盘空间失败: {e}")
        return False

