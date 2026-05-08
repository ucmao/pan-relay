import logging
from contextlib import contextmanager
from typing import Generator, Optional

import pymysql
from pymysql.connections import Connection as PyMySQLConnection
from pymysql.cursors import Cursor, DictCursor

from configs.app_config import db_config

logger = logging.getLogger(__name__)
Error = pymysql.MySQLError


def get_db_connection() -> Optional[PyMySQLConnection]:
    """
    获取数据库连接的统一入口。
    统一返回原生 PyMySQL 连接对象。
    """
    try:
        return pymysql.connect(**db_config)
    except Error as err:
        logger.error(f"数据库连接失败: {err}")
        return None


@contextmanager
def db_cursor(as_dict: bool = False):
    """
    提供一个上下文管理器，统一管理连接与游标生命周期。
    使用示例：

        with db_cursor(as_dict=True) as cursor:
            cursor.execute("SELECT ...")
            rows = cursor.fetchall()
    """
    conn = get_db_connection()
    if not conn:
        yield None
        return

    cursor_class = DictCursor if as_dict else Cursor
    cursor = conn.cursor(cursor_class)
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
