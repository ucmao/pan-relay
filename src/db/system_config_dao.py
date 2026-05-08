import json
import logging
from typing import Any, Dict, Optional

from pymysql.cursors import DictCursor

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)

SYSTEM_CONFIG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS system_config (
  config_key varchar(100) NOT NULL COMMENT '配置键',
  config_value text DEFAULT NULL COMMENT '配置值(JSON字符串)',
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表'
"""


def ensure_system_config_table() -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(SYSTEM_CONFIG_TABLE_SQL)
        conn.commit()
        return True
    except Error as err:
        logger.error(f"初始化 system_config 表失败: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def get_config_value(config_key: str) -> Optional[str]:
    if not ensure_system_config_table():
        return None

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(DictCursor)
        cursor.execute(
            "SELECT config_value FROM system_config WHERE config_key = %s",
            (config_key,),
        )
        row = cursor.fetchone()
        return row["config_value"] if row else None
    except Error as err:
        logger.error(f"读取系统配置 {config_key} 失败: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def set_config_value(config_key: str, config_value: Dict[str, Any]) -> bool:
    if not ensure_system_config_table():
        return False

    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO system_config (config_key, config_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
            """,
            (config_key, json.dumps(config_value, ensure_ascii=True)),
        )
        conn.commit()
        return True
    except Error as err:
        logger.error(f"保存系统配置 {config_key} 失败: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()
