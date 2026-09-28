import json
import logging
from typing import Any, Dict, List, Optional

from src.db.connection import Error, get_db_connection

logger = logging.getLogger(__name__)


def create_account(data: Dict[str, Any]) -> Optional[int]:
    """
    新建网盘账号。
    """
    conn = get_db_connection()
    if not conn:
        return None

    query = """
        INSERT INTO cloud_accounts (
            cloud_name, account_name, credential, extra_data, username,
            vip_status, is_active, is_valid, invalid_reason,
            total_space_bytes, used_space_bytes, left_space_bytes,
            priority, weight, transferred_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cloud_name = str(data.get("cloud_name", "")).strip()
    account_name = str(data.get("account_name", "")).strip() or f"{cloud_name}-账号"
    credential = str(data.get("credential", "")).strip()
    extra_data = data.get("extra_data")
    if isinstance(extra_data, dict):
        extra_data = json.dumps(extra_data, ensure_ascii=False)
    username = data.get("username")
    vip_status = int(data.get("vip_status", 0))
    is_active = 1 if data.get("is_active", True) else 0
    is_valid = 1 if data.get("is_valid", True) else 0
    invalid_reason = data.get("invalid_reason")
    total_space = int(data.get("total_space_bytes", 0))
    used_space = int(data.get("used_space_bytes", 0))
    left_space = max(0, total_space - used_space)
    priority = int(data.get("priority", 0))
    weight = max(1, int(data.get("weight", 10)))
    transferred_count = int(data.get("transferred_count", 0))

    try:
        cursor = conn.cursor()
        cursor.execute(
            query,
            (
                cloud_name,
                account_name,
                credential,
                extra_data,
                username,
                vip_status,
                is_active,
                is_valid,
                invalid_reason,
                total_space,
                used_space,
                left_space,
                priority,
                weight,
                transferred_count,
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()
        return new_id
    except Error as err:
        logger.error(f"创建网盘账号失败: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def update_account(account_id: int, data: Dict[str, Any]) -> bool:
    """
    更新网盘账号属性（支持局部字段更新）。
    """
    conn = get_db_connection()
    if not conn:
        return False

    allowed_fields = [
        "account_name",
        "credential",
        "extra_data",
        "username",
        "vip_status",
        "is_active",
        "is_valid",
        "invalid_reason",
        "total_space_bytes",
        "used_space_bytes",
        "left_space_bytes",
        "priority",
        "weight",
        "transferred_count",
    ]

    updates = []
    params = []

    for field in allowed_fields:
        if field in data:
            val = data[field]
            if field == "extra_data" and isinstance(val, dict):
                val = json.dumps(val, ensure_ascii=False)
            elif field in ("is_active", "is_valid"):
                val = 1 if val else 0
            updates.append(f"{field} = ?")
            params.append(val)

    if not updates:
        return True

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(account_id)

    sql = f"UPDATE cloud_accounts SET {', '.join(updates)} WHERE id = ?"

    try:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except Error as err:
        logger.error(f"更新网盘账号(id={account_id})失败: {err}")
        return False
    finally:
        cursor.close()
        conn.close()


def delete_account(account_id: int) -> bool:
    """
    删除网盘账号。
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cloud_accounts WHERE id = ?", (account_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as err:
        logger.error(f"删除网盘账号(id={account_id})失败: {err}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_account_by_id(account_id: int) -> Optional[Dict[str, Any]]:
    """
    按 ID 获取账号信息。
    """
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute("SELECT * FROM cloud_accounts WHERE id = ?", (account_id,))
        return cursor.fetchone()
    except Error as err:
        logger.error(f"按ID查询网盘账号失败: {err}")
        return None
    finally:
        cursor.close()
        conn.close()


def get_accounts_by_cloud(
    cloud_name: str, only_active: bool = True, only_valid: bool = True
) -> List[Dict[str, Any]]:
    """
    按平台查询可用账号列表，按 priority 升序、updated_at 升序排列。
    """
    conn = get_db_connection()
    if not conn:
        return []

    conditions = ["cloud_name = ?"]
    params: List[Any] = [cloud_name]

    if only_active:
        conditions.append("is_active = 1")
    if only_valid:
        conditions.append("is_valid = 1")

    sql = f"""
        SELECT * FROM cloud_accounts
        WHERE {' AND '.join(conditions)}
        ORDER BY priority ASC, updated_at ASC
    """

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()
    except Error as err:
        logger.error(f"查询平台({cloud_name})账号列表失败: {err}")
        return []
    finally:
        cursor.close()
        conn.close()


def get_all_accounts(cloud_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    查询所有账号列表（可按平台过滤），按云盘名称、优先级排序。
    """
    conn = get_db_connection()
    if not conn:
        return []

    conditions = []
    params: List[Any] = []

    if cloud_name:
        conditions.append("cloud_name = ?")
        params.append(cloud_name)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT * FROM cloud_accounts
        {where_clause}
        ORDER BY cloud_name ASC, priority ASC, id ASC
    """

    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()
    except Error as err:
        logger.error(f"获取所有网盘账号列表失败: {err}")
        return []
    finally:
        cursor.close()
        conn.close()


def update_account_status(
    account_id: int, is_valid: bool, invalid_reason: Optional[str] = None
) -> bool:
    """
    更新账号有效性状态。
    """
    return update_account(
        account_id,
        {
            "is_valid": 1 if is_valid else 0,
            "invalid_reason": invalid_reason or ("" if is_valid else "未知错误"),
        },
    )


def update_account_space(
    account_id: int,
    total_space: int,
    used_space: int,
    username: Optional[str] = None,
    vip_status: Optional[int] = None,
) -> bool:
    """
    更新账号空间容量与用户信息。
    """
    left_space = max(0, total_space - used_space)
    data: Dict[str, Any] = {
        "total_space_bytes": total_space,
        "used_space_bytes": used_space,
        "left_space_bytes": left_space,
        "is_valid": 1,
        "invalid_reason": "",
    }
    if username is not None:
        data["username"] = username
    if vip_status is not None:
        data["vip_status"] = vip_status
    return update_account(account_id, data)


def update_account_credential(
    account_id: int, credential: str, extra_data: Optional[str] = None
) -> bool:
    """
    更新账号凭证（支持同时更新 extra_data）。
    """
    data: Dict[str, Any] = {
        "credential": credential,
        "is_valid": 1,
        "invalid_reason": "",
    }
    if extra_data is not None:
        data["extra_data"] = extra_data
    return update_account(account_id, data)


def record_account_transfer(account_id: int) -> bool:
    """
    记录一次成功的转存调用（自增转存计数，更新最近使用时间）。
    """
    conn = get_db_connection()
    if not conn:
        return False

    sql = """
        UPDATE cloud_accounts
        SET transferred_count = transferred_count + 1,
            last_used_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (account_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as err:
        logger.error(f"记录账号转存调用失败: {err}")
        return False
    finally:
        cursor.close()
        conn.close()


def record_account_keepalive(account_id: int) -> bool:
    """
    记录一次账号保活操作（更新最近保活时间）。
    """
    conn = get_db_connection()
    if not conn:
        return False

    sql = """
        UPDATE cloud_accounts
        SET last_keepalive_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (account_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as err:
        logger.error(f"记录账号保活时间失败: {err}")
        return False
    finally:
        cursor.close()
        conn.close()
