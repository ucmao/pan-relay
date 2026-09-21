import json
import logging
from typing import Any, Dict, Optional

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)

def get_config_value(config_key: str) -> Optional[str]:
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(
            "SELECT config_value FROM system_config WHERE config_key = ?",
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
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO system_config (config_key, config_value)
            VALUES (?, ?)
            ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value, updated_at = datetime('now')
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


def delete_config_value(config_key: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM system_config WHERE config_key = ?", (config_key,))
        conn.commit()
        return True
    except Error as err:
        logger.error(f"删除系统配置 {config_key} 失败: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

