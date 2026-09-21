# src/services/resource_health_service.py

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from src.db.logs import insert_system_log
from src.db.resources import (
    count_resources_by_health,
    delete_resource_by_id,
    get_dead_resources,
    get_resource_by_id,
    get_resources_for_audit,
    update_resource_health,
)
from src.pan_operator import del_share
from src.services.link_checker import (
    STATE_BAD,
    STATE_LOCKED,
    STATE_OK,
    STATE_UNCERTAIN,
    check_link,
    check_links_batch,
)

logger = logging.getLogger(__name__)


def audit_single_resource(resource_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    单条资源的实时健康状态检测与入库更新。
    """
    start_time = time.time()
    success, msg, resource = get_resource_by_id(resource_id)
    if not success or not resource:
        return False, msg or "资源不存在", None

    share_link = resource.get("share_link") or ""
    cloud_name = resource.get("cloud_name") or ""
    if not share_link:
        return False, "资源缺少有效的分享链接", None

    try:
        # 执行免登录健康探测 (强制刷新，确保获取最新状态)
        res = check_link(share_link, disk_type=cloud_name, force_refresh=True)
        health_state = res.get("state") or STATE_UNCERTAIN
        health_summary = res.get("summary") or ""

        # 更新数据库
        update_resource_health(resource_id, health_state, health_summary)

        duration_ms = int((time.time() - start_time) * 1000)
        insert_system_log(
            log_type="audit",
            action="resource.audit_single",
            query_text=f"ID={resource_id} | {share_link}",
            status_code=200,
            error_message=health_summary if health_state == STATE_BAD else None,
            duration_ms=duration_ms,
            result_count=1,
        )

        return True, "检测完成", {
            "id": resource_id,
            "name": resource.get("name"),
            "share_link": share_link,
            "cloud_name": cloud_name,
            "health_status": health_state,
            "health_message": health_summary,
            "file_count": res.get("file_count"),
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        logger.error(f"单条资源巡检异常 (ID={resource_id}): {exc}")
        return False, f"巡检异常: {exc}", None


def audit_resources_batch(
    resource_ids: Optional[List[int]] = None,
    limit: int = 100,
    max_workers: int = 4,
) -> Dict[str, Any]:
    """
    批量巡检资源库健康状态并持久化。
    """
    start_time = time.time()
    items_to_audit = get_resources_for_audit(resource_ids=resource_ids, limit=limit)
    if not items_to_audit:
        return {
            "total": 0,
            "ok_count": 0,
            "bad_count": 0,
            "locked_count": 0,
            "uncertain_count": 0,
            "items": [],
            "duration_ms": 0,
        }

    # 构建批量检测入参
    check_payload = [
        {
            "url": item.get("share_link") or "",
            "disk_type": item.get("cloud_name") or "",
        }
        for item in items_to_audit
    ]

    try:
        check_results = check_links_batch(
            check_payload, max_workers=max_workers, force_refresh=True
        )
    except Exception as exc:
        logger.error(f"批量巡检检测执行异常: {exc}")
        check_results = []

    ok_count = 0
    bad_count = 0
    locked_count = 0
    uncertain_count = 0
    updated_items = []

    for idx, item in enumerate(items_to_audit):
        res = check_results[idx] if idx < len(check_results) else None
        res_state = res.get("state") if res else STATE_UNCERTAIN
        res_summary = res.get("summary") if res else "检测未返回结果"

        # 更新数据库
        update_resource_health(item["id"], res_state, res_summary)

        if res_state == STATE_OK:
            ok_count += 1
        elif res_state == STATE_BAD:
            bad_count += 1
        elif res_state == STATE_LOCKED:
            locked_count += 1
        else:
            uncertain_count += 1

        updated_items.append({
            "id": item["id"],
            "name": item.get("name"),
            "share_link": item.get("share_link"),
            "cloud_name": item.get("cloud_name"),
            "health_status": res_state,
            "health_message": res_summary,
            "file_count": res.get("file_count") if res else None,
        })

    duration_ms = int((time.time() - start_time) * 1000)
    insert_system_log(
        log_type="audit",
        action="resource.audit_batch",
        query_text=f"批量巡检 {len(items_to_audit)} 条资源 (有效:{ok_count}, 失效:{bad_count}, 需密码:{locked_count})",
        status_code=200,
        duration_ms=duration_ms,
        result_count=len(items_to_audit),
    )

    logger.info(
        f"批量资源健康巡检完成: 共 {len(items_to_audit)} 条, 有效 {ok_count}, 失效 {bad_count}, 需提取码 {locked_count}, 耗时 {duration_ms}ms"
    )

    return {
        "total": len(items_to_audit),
        "ok_count": ok_count,
        "bad_count": bad_count,
        "locked_count": locked_count,
        "uncertain_count": uncertain_count,
        "items": updated_items,
        "duration_ms": duration_ms,
    }


def cleanup_dead_resources(dry_run: bool = False, limit: int = 100) -> Dict[str, Any]:
    """
    一键清理资源库中已确认失效 (health_status == 'bad') 的死链与空资源。
    同时触发底层网盘 del_share 物理释放空间与清理数据库记录。
    """
    start_time = time.time()
    dead_items = get_dead_resources(limit=limit)
    if not dead_items:
        return {
            "total_found": 0,
            "cleaned_count": 0,
            "dry_run": dry_run,
            "items": [],
            "duration_ms": 0,
        }

    cleaned_count = 0
    cleaned_items = []

    for item in dead_items:
        res_id = item["id"]
        share_url = item.get("share_link") or ""
        file_id = item.get("file_id")

        if not dry_run:
            try:
                # 尝试物理删除网盘文件
                if share_url or file_id:
                    del_share({"share_url": share_url, "file_id": file_id})
            except Exception as exc:
                logger.warning(f"清理失效资源物理网盘文件异常 (ID={res_id}): {exc}")

            try:
                delete_resource_by_id(res_id)
                cleaned_count += 1
            except Exception as exc:
                logger.error(f"从数据库删除失效资源记录失败 (ID={res_id}): {exc}")
        else:
            cleaned_count += 1

        cleaned_items.append({
            "id": res_id,
            "name": item.get("name"),
            "share_link": share_url,
            "cloud_name": item.get("cloud_name"),
            "health_message": item.get("health_message"),
        })

    duration_ms = int((time.time() - start_time) * 1000)
    if not dry_run:
        insert_system_log(
            log_type="cleanup",
            action="resource.cleanup_dead",
            query_text=f"清理失效资源共 {cleaned_count} 条",
            status_code=200,
            duration_ms=duration_ms,
            result_count=cleaned_count,
        )

    logger.info(f"失效死链资源清理完成: 共清理 {cleaned_count} 条 (dry_run={dry_run})")
    return {
        "total_found": len(dead_items),
        "cleaned_count": cleaned_count,
        "dry_run": dry_run,
        "items": cleaned_items,
        "duration_ms": duration_ms,
    }


def get_resource_health_overview() -> Dict[str, Any]:
    """
    获取资源库整体健康度统计概览。
    """
    return count_resources_by_health()


def scheduled_resource_health_audit_job() -> Dict[str, Any]:
    """
    定时后台巡检任务入口，供 APScheduler 定期调用。
    """
    logger.info("开始执行后台资源健康巡检定时任务...")
    try:
        res = audit_resources_batch(limit=100, max_workers=4)
        logger.info(f"后台资源健康巡检定时任务执行完成: {res}")
        return res
    except Exception as exc:
        logger.error(f"后台资源健康巡检定时任务执行异常: {exc}")
        return {"error": str(exc)}
