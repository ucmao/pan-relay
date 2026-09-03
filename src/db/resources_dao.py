import logging
from typing import Any, Dict, List, Optional, Tuple

from src.db.connection import DictCursor, Error, db_cursor, get_db_connection

logger = logging.getLogger(__name__)


def insert_resource(record: Dict[str, Any]) -> Optional[int]:
    """
    插入一条资源记录，返回新记录的 ID。
    兼容 pan_operator 传入的数据字段。
    """
    file_id = record.get("file_id")
    name = record.get("name")
    share_link = record.get("share_link")
    cloud_name = record.get("cloud_name", "")
    resource_type = record.get("type", "")
    remarks = record.get("remarks", "")

    sql = """
    INSERT INTO resources (file_id, name, share_link, cloud_name, type, remarks)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (file_id, name, share_link, cloud_name, resource_type, remarks)

    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        conn.commit()
        new_id = cursor.lastrowid
        logger.info(f"成功插入资源记录: {name}, ID: {new_id}")
        return new_id
    except Error as err:
        logger.error(f"插入资源记录 {name} 失败: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def query_file_id_by_share_link(share_link: str) -> Optional[str]:
    """根据分享链接查询 file_id，用于 pan_operator。"""
    sql = "SELECT file_id FROM resources WHERE share_link = %s"
    with db_cursor() as cursor:
        if cursor is None:
            return None
        cursor.execute(sql, (share_link,))
        row = cursor.fetchone()
        if row:
            file_id = row[0]
            logger.info(f"根据分享链接 {share_link} 查询到的 file_id 是: {file_id}")
            return file_id
        logger.error(f"未找到与分享链接 {share_link} 对应的 file_id")
        return None


def delete_by_share_link(share_link: str) -> int:
    """根据分享链接删除资源记录，返回受影响行数。"""
    sql = "DELETE FROM resources WHERE share_link = %s"
    with db_cursor() as cursor:
        if cursor is None:
            return 0
        cursor.execute(sql, (share_link,))
        rows = cursor.rowcount
        if rows > 0:
            logger.info(f"成功删除分享链接 {share_link} 对应的记录")
        else:
            logger.warning(f"未找到分享链接 {share_link} 对应的记录，未执行删除操作")
        return rows


def random_read_record() -> Optional[Tuple]:
    """随机读取一条资源记录，返回原始行数据。"""
    sql = "SELECT * FROM resources ORDER BY RAND() LIMIT 1"
    with db_cursor() as cursor:
        if cursor is None:
            return None
        cursor.execute(sql)
        row = cursor.fetchone()
        if row:
            logger.info(f"随机读取到的资源记录: {row}")
            return row
        logger.warning("resources 表中未找到任何记录")
        return None


def update_share_link(resource_id: int, new_share_link: str, file_id: Optional[str] = None) -> bool:
    """
    更新资源的分享链接和 is_replaced 状态（供 pan_operator 使用）。
    """
    conn = get_db_connection()
    if not conn:
        return False

    cursor = conn.cursor()
    try:
        if file_id:
            sql = """
            UPDATE resources
            SET share_link = %s, file_id = %s, is_replaced = TRUE
            WHERE id = %s
            """
            params = (new_share_link, file_id, resource_id)
        else:
            sql = """
            UPDATE resources
            SET share_link = %s, is_replaced = TRUE
            WHERE id = %s
            """
            params = (new_share_link, resource_id)

        cursor.execute(sql, params)
        conn.commit()

        if cursor.rowcount > 0:
            logger.info(f"资源ID {resource_id} 的分享链接已更新为 {new_share_link}")
            return True
        logger.warning(f"未找到资源ID {resource_id}")
        return False
    except Error as err:
        logger.error(f"更新资源分享链接时发生数据库错误: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def list_resources(
    page: int = 1, page_size: int = 10, search: str = ""
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    后台列表分页查询 resources（供 hot_resource_service 调用）。
    返回: (success, message, data)
    """
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", None

    try:
        cursor = conn.cursor(DictCursor)

        where_clause = " WHERE 1=1 "
        params: List[Any] = []

        if search:
            where_clause += " AND name LIKE %s"
            params.append(f"%{search}%")

        count_sql = f"SELECT COUNT(*) AS total FROM resources{where_clause}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()["total"]

        total_pages = (total_count + page_size - 1) // page_size
        offset = (page - 1) * page_size

        query_sql = f"""
        SELECT id, name, share_link, cloud_name, type, remarks, is_replaced, created_at, updated_at
        FROM resources
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        cursor.execute(query_sql, params)
        rows = cursor.fetchall()

        for r in rows:
            if r["created_at"]:
                r["created_at"] = str(r["created_at"])
            if r["updated_at"]:
                r["updated_at"] = str(r["updated_at"])

        data = {
            "items": rows,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
        }
        return True, "", data
    except Error as err:
        logger.error(f"获取资源列表时出错: {err}")
        return False, f"获取资源列表失败: {err}", None
    finally:
        cursor.close()
        conn.close()


def get_resource_by_id(resource_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """根据 ID 获取单个资源详情。"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", None

    try:
        cursor = conn.cursor(DictCursor)
        sql = """
        SELECT id, name, share_link, cloud_name, type, remarks, is_replaced, created_at, updated_at
        FROM resources WHERE id = %s
        """
        cursor.execute(sql, (resource_id,))
        row = cursor.fetchone()
        if not row:
            return False, "资源不存在", None

        if row["created_at"]:
            row["created_at"] = str(row["created_at"])
        if row["updated_at"]:
            row["updated_at"] = str(row["updated_at"])

        return True, "", row
    except Error as err:
        logger.error(f"获取资源时出错: {err}")
        return False, f"获取资源失败: {err}", None
    finally:
        cursor.close()
        conn.close()


def insert_resource_simple(resource_data: Dict[str, Any]) -> Tuple[bool, str, Optional[int]]:
    """
    后台新增资源用的简单插入（不含 file_id），供 hot_resource_service 调用。
    """
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", None

    try:
        cursor = conn.cursor()
        sql = """
        INSERT INTO resources (name, share_link, cloud_name, type, remarks)
        VALUES (%s, %s, %s, %s, %s)
        """
        params = (
            resource_data["name"],
            resource_data["share_link"],
            resource_data.get("cloud_name", ""),
            resource_data.get("type", ""),
            resource_data.get("remarks", ""),
        )
        cursor.execute(sql, params)
        conn.commit()
        new_id = cursor.lastrowid
        logger.info(f"成功直接添加资源到数据库，标题: {resource_data['name']}")
        return True, "资源添加成功", new_id
    except Error as err:
        logger.error(f"添加资源到数据库时出错: {err}")
        conn.rollback()
        return False, f"资源添加失败: {err}", None
    finally:
        cursor.close()
        conn.close()


def update_resource_basic_info(resource_id: int, resource_data: Dict[str, Any]) -> Tuple[bool, str]:
    """更新资源基础信息（标题、云盘名称、类型、备注和分享链接）。"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        cursor = conn.cursor()
        check_sql = "SELECT id FROM resources WHERE id = %s"
        cursor.execute(check_sql, (resource_id,))
        if not cursor.fetchone():
            return False, "资源不存在"

        sql = """
        UPDATE resources
        SET name = %s, share_link = %s, cloud_name = %s, type = %s, remarks = %s
        WHERE id = %s
        """
        params = (
            resource_data["name"],
            resource_data.get("share_link", ""),
            resource_data.get("cloud_name", ""),
            resource_data.get("type", ""),
            resource_data.get("remarks", ""),
            resource_id,
        )
        cursor.execute(sql, params)
        conn.commit()
        logger.info(f"成功更新资源，ID: {resource_id}")
        return True, "资源更新成功"
    except Error as err:
        logger.error(f"更新资源时出错: {err}")
        conn.rollback()
        return False, f"资源更新失败: {err}"
    finally:
        cursor.close()
        conn.close()


def delete_resource_by_id(resource_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    根据 ID 删除资源，同时返回被删除记录的 share_link 和 file_id，
    以便 hot_resource_service / pan_operator 调用 del_share 使用。
    """
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", None

    try:
        cursor = conn.cursor(DictCursor)

        check_sql = "SELECT share_link, file_id FROM resources WHERE id = %s"
        cursor.execute(check_sql, (resource_id,))
        resource = cursor.fetchone()
        if not resource:
            return False, "资源不存在", None

        delete_sql = "DELETE FROM resources WHERE id = %s"
        cursor.execute(delete_sql, (resource_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return False, "删除资源失败，请检查资源是否存在", None

        logger.info(f"成功删除资源，ID: {resource_id}")
        return True, "资源删除成功", resource
    except Error as err:
        logger.error(f"删除资源时出错: {err}")
        conn.rollback()
        return False, f"资源删除失败: {err}", None
    finally:
        cursor.close()
        conn.close()


def search_resources_by_keyword(keyword: str) -> List[Tuple[str, str, Optional[str]]]:
    """
    根据关键词搜索资源（用于搜索服务）。
    返回: [(name, share_link, cloud_name), ...]
    """
    sql = "SELECT name, share_link, cloud_name FROM resources WHERE name LIKE %s"
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute(sql, (f"%{keyword}%",))
        results = cursor.fetchall()
        return results
    except Error as err:
        logger.error(f"搜索资源时出错: {err}")
        return []
    finally:
        cursor.close()
        conn.close()


def search_resources_advanced(
    name: str = "", cloud_name: str = "", resource_type: str = "", limit: int = 100, sort: str = "default"
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    高级搜索资源（通过名称、云名称或类型）。
    返回: (success, message, results)
    """
    if not any([name, cloud_name, resource_type]):
        return False, "至少需要提供 name、cloud_name 或 type 中的一个参数", []

    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", []

    try:
        cursor = conn.cursor(DictCursor)

        conditions = []
        params = []

        if name:
            conditions.append("name LIKE %s")
            params.append(f"%{name}%")

        if cloud_name:
            conditions.append("cloud_name LIKE %s")
            params.append(f"%{cloud_name}%")

        if resource_type:
            conditions.append("type LIKE %s")
            params.append(f"%{resource_type}%")

        base_query = "SELECT id, name, share_link, cloud_name, type, remarks FROM resources"
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # 根据sort参数确定排序规则
        if sort == "asc":
            order_clause = " ORDER BY id ASC"
        elif sort == "desc":
            order_clause = " ORDER BY id DESC"
        elif sort == "random":
            order_clause = " ORDER BY RAND()"
        else:  # default
            order_clause = " ORDER BY created_at DESC"
            
        limit_clause = " LIMIT %s"

        sql = base_query + where_clause + order_clause + limit_clause
        params.append(limit)

        cursor.execute(sql, params)
        results = cursor.fetchall()

        return True, "", results

    except Error as err:
        logger.error(f"数据库查询错误: {err}")
        return False, f"数据库查询错误: {err}", []
    finally:
        cursor.close()
        conn.close()

