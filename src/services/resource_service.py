import logging

from src.db.resources import (
    list_resources as db_list_resources,
    get_resource_by_id,
    insert_resource_simple,
    update_resource_basic_info,
    delete_resource_by_id,
)
from src.pan_operator import create_share, del_share

logger = logging.getLogger(__name__)


def list_resources(page: int = 1, page_size: int = 10, search: str = ""):
    """获取资源列表，支持分页和搜索"""
    return db_list_resources(page=page, page_size=page_size, search=search)


def get_resource_detail(resource_id: int):
    """获取单个资源详情"""
    return get_resource_by_id(resource_id)


def add_resource_and_share(resource_data: dict):
    """
    添加新资源。
    所有资源直接保存到数据库，然后调用 create_share 方法处理网盘替换。
    若资源链接已存在，则复用现有记录并发起转存。
    """
    if not resource_data.get("name") or not resource_data.get("share_link"):
        return False, "标题和分享链接为必填项", None

    share_link = resource_data["share_link"].strip()
    resource_data["share_link"] = share_link

    if not resource_data.get("cloud_name"):
        from src.utils.netdisk_utils import match_netdisk_link
        resource_data["cloud_name"] = match_netdisk_link(share_link)

    save_to_netdisk = resource_data.get("save_to_netdisk", {}) or {}
    should_create_share = any(save_to_netdisk.values())

    # 检查数据库是否已存在该链接
    from src.db.resources import get_resource_by_share_link
    existing = get_resource_by_share_link(share_link)

    if existing:
        target_id = existing["id"]
        logger.info(f"资源已存在于库中 (ID: {target_id})")
        if should_create_share:
            # 用户选择批量转存：复用现有记录 ID 继续发起转存与链接替换
            share_data = {
                "id": target_id,
                "share_url": share_link,
                "title": resource_data.get("name") or existing.get("name"),
                "cloud_name": resource_data.get("cloud_name") or existing.get("cloud_name"),
                "resource_type": resource_data.get("type") or existing.get("type"),
                "remark": resource_data.get("remarks") or existing.get("remarks"),
                "save_to_netdisk": save_to_netdisk,
            }
            try:
                create_share(share_data)
            except Exception as share_err:
                logger.error(f"调用 create_share 处理资源分享链接时出错: {share_err}")
            return True, "已触发转存并更新", target_id
        else:
            return True, "资源链接已存在，无需重复导入", target_id

    # 向数据库插入资源
    success, message, new_id = insert_resource_simple(resource_data)
    if not success:
        return False, message, None

    logger.info(f"成功直接添加资源到数据库，标题: {resource_data['name']}")

    if not should_create_share:
        return True, "资源已直接入库", new_id

    # 调用 create_share 处理网盘替换
    share_data = {
        "id": new_id,
        "share_url": share_link,
        "title": resource_data["name"],
        "cloud_name": resource_data.get("cloud_name", ""),
        "resource_type": resource_data.get("type", ""),
        "remark": resource_data.get("remarks", ""),
        "save_to_netdisk": save_to_netdisk,
    }

    try:
        create_share(share_data)
    except Exception as share_err:
        logger.error(f"调用 create_share 处理资源分享链接时出错: {share_err}")

    return True, "资源添加成功", new_id


def update_resource_info(resource_id: int, resource_data: dict):
    """更新资源信息（标题、云盘名称、类型和备注）"""
    if not resource_data.get("name"):
        return False, "标题为必填项"

    if resource_data.get("share_link") and not resource_data.get("cloud_name"):
        from src.utils.netdisk_utils import match_netdisk_link
        resource_data["cloud_name"] = match_netdisk_link(resource_data["share_link"])

    return update_resource_basic_info(resource_id, resource_data)


def delete_resource_and_share(resource_id: int):
    """
    删除资源。
    直接删除数据库记录并将 share_url 传递给 del_share 函数。
    """
    # 从数据库删除资源，同时获取被删除记录的 share_link 和 file_id
    success, message, resource = delete_resource_by_id(resource_id)
    if not success:
        return False, message

    # 调用 del_share 处理网盘删除
    try:
        share_data = {
            "share_url": resource["share_link"],
            "file_id": resource["file_id"],
        }
        del_share(share_data)
        logger.info(f"调用del_share处理资源分享链接: {resource['share_link']}")
    except Exception as share_err:
        logger.error(f"调用del_share处理资源分享链接时出错: {share_err}")

    return True, "资源删除成功"

