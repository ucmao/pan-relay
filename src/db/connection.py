import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

from src.configs.app_config import SQLITE_DB_PATH, BASE_DIR

logger = logging.getLogger(__name__)
Error = sqlite3.Error


class DictCursor:
    """兼容原代码对 DictCursor 的引用"""
    pass


class Cursor:
    """兼容原代码对 Cursor 的引用"""
    pass


class SQLiteCursorWrapper:
    """包装 sqlite3.Cursor，兼容 MySQL 的 %s 占位符、部分常用函数及 DictCursor 特性。"""

    def __init__(self, raw_cursor: sqlite3.Cursor, as_dict: bool = False):
        self._cursor = raw_cursor
        self.as_dict = as_dict

    def _transform_sql(self, sql: str) -> str:
        # 将 %s 占位符替换为 SQLite 的 ? 占位符
        sql = sql.replace("%s", "?")
        # 兼容 RAND() 为 RANDOM()
        sql = re.sub(r"\bRAND\(\)", "RANDOM()", sql, flags=re.IGNORECASE)
        # 兼容 NOW() 为 datetime('now')
        sql = re.sub(r"\bNOW\(\)", "datetime('now')", sql, flags=re.IGNORECASE)
        return sql

    def execute(self, sql: str, params=None):
        transformed = self._transform_sql(sql)
        if params is None:
            return self._cursor.execute(transformed)
        return self._cursor.execute(transformed, params)

    def executemany(self, sql: str, params=None):
        transformed = self._transform_sql(sql)
        if params is None:
            return self._cursor.executemany(transformed)
        return self._cursor.executemany(transformed, params)

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
    """包装 sqlite3.Connection，提供与原有 connection 相同的 cursor/commit/rollback 行为。"""

    def __init__(self, raw_conn: sqlite3.Connection):
        self._conn = raw_conn

    def cursor(self, cursor_type=None) -> SQLiteCursorWrapper:
        as_dict = bool(cursor_type and cursor_type is not Cursor)
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
        raw_conn.execute("PRAGMA busy_timeout=30000;")

        cursor = raw_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_config'")
        table_exists = cursor.fetchone() is not None

        if not table_exists and os.path.exists(schema_file):
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            raw_conn.executescript(schema_sql)
            raw_conn.commit()
            logger.info(f"成功使用 {schema_file} 初始化 SQLite 数据库: {db_path}")

        raw_conn.close()
        _db_initialized = True
    except Exception as err:
        logger.error(f"初始化 SQLite 数据库失败: {err}")


def get_db_connection() -> Optional[SQLiteConnectionWrapper]:
    """获取 SQLite 数据库连接的统一入口。"""
    global _db_initialized
    if not _db_initialized:
        init_sqlite_db()

    try:
        raw_conn = sqlite3.connect(SQLITE_DB_PATH, timeout=30.0)
        raw_conn.execute("PRAGMA journal_mode=WAL;")
        raw_conn.execute("PRAGMA synchronous=NORMAL;")
        raw_conn.execute("PRAGMA busy_timeout=30000;")
        return SQLiteConnectionWrapper(raw_conn)
    except Error as err:
        logger.error(f"SQLite 数据库连接失败: {err}")
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

    cursor = conn.cursor(DictCursor if as_dict else Cursor)
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
