import logging
from typing import Any, Dict, List, Optional, Tuple

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)

def get_all_cookies() -> List[Dict[str, Any]]:
    """
    从数据库中读取所有云盘凭证配置（直接基于 cloud_accounts 账号池）。
    """
    conn = get_db_connection()
    if not conn:
        return []

    cookies = []
    query = """
        SELECT id, cloud_name, account_name, credential, is_active, is_valid, created_at, updated_at 
        FROM cloud_accounts 
        ORDER BY priority ASC, updated_at ASC
    """

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(query)
        results = cursor.fetchall()

        for row in results:
            cookie_config = {
                "id": row["id"],
                "cloud_name": row["cloud_name"],
                "account_name": row["account_name"],
                "cookie": row["credential"],
                "is_active": row["is_active"],
                "is_valid": row["is_valid"],
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
    根据云盘名称获取对应的凭证内容（直接从 cloud_accounts 账号池获取有效主号）。
    """
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(
            """
            SELECT credential FROM cloud_accounts
            WHERE cloud_name = ? AND is_active = 1 AND is_valid = 1
            ORDER BY priority ASC, updated_at ASC
            LIMIT 1
            """,
            (cloud_name,),
        )
        res = cursor.fetchone()
        if res and res.get("credential"):
            return res["credential"]

        cursor.execute(
            """
            SELECT credential FROM cloud_accounts
            WHERE cloud_name = ? AND is_active = 1
            ORDER BY priority ASC, updated_at ASC
            LIMIT 1
            """,
            (cloud_name,),
        )
        res = cursor.fetchone()
        return res["credential"] if res and res.get("credential") else None
    except Error as err:
        logger.error(f"根据云盘名称查询凭证时出错: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def save_cookie(cloud_name: str, cookie: str) -> Tuple[bool, str]:
    """
    保存或更新云盘凭证配置（直接映射到 cloud_accounts 账号池）。
    """
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    existing_cookie = get_cookie_by_cloud_name(cloud_name)
    
    try:
        cursor = conn.cursor()
        if existing_cookie is not None:
            query = """
                UPDATE cloud_accounts 
                SET credential = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = (
                    SELECT id FROM cloud_accounts 
                    WHERE cloud_name = ? 
                    ORDER BY priority ASC, updated_at ASC 
                    LIMIT 1
                )
            """
            params = (cookie, cloud_name)
            action = "更新"
        else:
            query = "INSERT INTO cloud_accounts (cloud_name, account_name, credential, is_active, is_valid) VALUES (?, ?, ?, 1, 1)"
            params = (cloud_name, f"{cloud_name}-主号", cookie)
            action = "添加"
        
        cursor.execute(query, params)
        conn.commit()
        logger.info(f"成功{action}云盘'{cloud_name}'的凭证配置 (账号池)")
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
    根据云盘名称删除凭证配置（直接操作 cloud_accounts 账号池）。
    """
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    query = """
        DELETE FROM cloud_accounts 
        WHERE id = (
            SELECT id FROM cloud_accounts 
            WHERE cloud_name = ? 
            ORDER BY priority ASC, updated_at ASC 
            LIMIT 1
        )
    """

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


def update_xunlei_refresh_token(new_refresh_token: str) -> bool:
    """
    当迅雷网盘接口刷新返回新的 refresh_token 时，自动更新数据库中的迅雷凭证配置。
    """
    import json

    if not new_refresh_token or not new_refresh_token.strip():
        return False

    raw_credential = get_cookie_by_cloud_name("迅雷网盘")
    if not raw_credential:
        logger.warning("更新迅雷 refresh_token 失败：数据库中未找到迅雷网盘凭证配置")
        return False

    try:
        parsed = json.loads(raw_credential)
        if not isinstance(parsed, dict):
            parsed = {}
    except Exception:
        parsed = {}

    if parsed.get("refresh_token") == new_refresh_token.strip():
        return True

    parsed["refresh_token"] = new_refresh_token.strip()
    updated_credential = json.dumps(parsed, ensure_ascii=False)

    success, msg = save_cookie("迅雷网盘", updated_credential)
    if success:
        logger.info("已成功持久化更新迅雷网盘的 refresh_token 到数据库")
    else:
        logger.error(f"持久化更新迅雷网盘 refresh_token 失败: {msg}")
    return success

