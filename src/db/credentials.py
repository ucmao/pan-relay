import logging
from typing import Any, Dict, List, Optional, Tuple

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)

def get_all_cookies() -> List[Dict[str, Any]]:
    """
    从数据库中读取所有云盘凭证配置。
    """
    conn = get_db_connection()
    if not conn:
        return []

    cookies = []
    query = "SELECT id, cloud_name, cookie, created_at, updated_at FROM cookie_config ORDER BY created_at DESC"

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(query)
        results = cursor.fetchall()

        for row in results:
            cookie_config = {
                "id": row["id"],
                "cloud_name": row["cloud_name"],
                "cookie": row["cookie"],
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"])
            }
            cookies.append(cookie_config)
    except Error as err:
        logger.error(f"查询云盘凭证配置时出错: {err}")
    finally:
        cursor.close()
        conn.close()

    return cookies

def get_cookie_by_cloud_name(cloud_name: str) -> Optional[str]:
    """
    根据云盘名称获取对应的凭证内容。
    """
    conn = get_db_connection()
    if not conn:
        return None

    query = "SELECT cookie FROM cookie_config WHERE cloud_name = ?"

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(query, (cloud_name,))
        result = cursor.fetchone()
        return result["cookie"] if result else None
    except Error as err:
        logger.error(f"根据云盘名称查询凭证时出错: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def save_cookie(cloud_name: str, cookie: str) -> Tuple[bool, str]:
    """
    保存或更新云盘凭证配置。
    如果存在相同的cloud_name，则更新；否则插入新记录。
    """
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    # 先检查是否已存在
    existing_cookie = get_cookie_by_cloud_name(cloud_name)
    
    try:
        cursor = conn.cursor()
        if existing_cookie is not None:
            # 更新现有记录
            query = "UPDATE cookie_config SET cookie = ? WHERE cloud_name = ?"
            params = (cookie, cloud_name)
            action = "更新"
        else:
            # 插入新记录
            query = "INSERT INTO cookie_config (cloud_name, cookie) VALUES (?, ?)"
            params = (cloud_name, cookie)
            action = "添加"
        
        cursor.execute(query, params)
        conn.commit()
        logger.info(f"成功{action}云盘'{cloud_name}'的凭证配置")
        return True, f"云盘凭证配置{action}成功"
    except Error as err:
        logger.error(f"{action}云盘凭证配置时出错: {err}")
        conn.rollback()
        return False, f"云盘凭证配置{action}失败: {err}"
    finally:
        cursor.close()
        conn.close()

def delete_cookie(cloud_name: str) -> Tuple[bool, str]:
    """
    根据云盘名称删除凭证配置。
    """
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    query = "DELETE FROM cookie_config WHERE cloud_name = ?"

    try:
        cursor = conn.cursor()
        cursor.execute(query, (cloud_name,))
        conn.commit()
        
        if cursor.rowcount > 0:
            logger.info(f"成功删除云盘'{cloud_name}'的凭证配置")
            return True, "云盘凭证配置删除成功"
        else:
            logger.warning(f"尝试删除云盘'{cloud_name}'的凭证配置，但未找到该记录")
            return False, "未找到该云盘的凭证配置"
    except Error as err:
        logger.error(f"删除云盘凭证配置时出错: {err}")
        conn.rollback()
        return False, f"云盘凭证配置删除失败: {err}"
    finally:
        cursor.close()
        conn.close()
