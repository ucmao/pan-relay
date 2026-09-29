import csv
import io
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from src.db.accounts import create_account, get_all_accounts
from src.services.account_pool_manager import AccountPoolManager

logger = logging.getLogger(__name__)

CLOUD_ALIAS_MAP: Dict[str, str] = {
    "夸克": "夸克网盘",
    "夸克网盘": "夸克网盘",
    "quark": "夸克网盘",
    "quarkpan": "夸克网盘",
    "百度": "百度网盘",
    "百度网盘": "百度网盘",
    "baidu": "百度网盘",
    "baidupan": "百度网盘",
    "阿里": "阿里云盘",
    "阿里云": "阿里云盘",
    "阿里云盘": "阿里云盘",
    "alipan": "阿里云盘",
    "aliyun": "阿里云盘",
    "aliyunpan": "阿里云盘",
    "uc": "UC网盘",
    "uc网盘": "UC网盘",
    "uc云盘": "UC网盘",
    "ucpan": "UC网盘",
    "迅雷": "迅雷网盘",
    "迅雷云盘": "迅雷网盘",
    "迅雷网盘": "迅雷网盘",
    "xunlei": "迅雷网盘",
    "xunleipan": "迅雷网盘",
    "光鸭": "光鸭云盘",
    "光鸭网盘": "光鸭云盘",
    "光鸭云盘": "光鸭云盘",
    "guangya": "光鸭云盘",
    "guangyapan": "光鸭云盘",
    "悟空": "悟空网盘",
    "悟空云盘": "悟空网盘",
    "悟空网盘": "悟空网盘",
    "wukong": "悟空网盘",
    "wukongpan": "悟空网盘",
    "移动": "移动云盘",
    "移动云盘": "移动云盘",
    "移动网盘": "移动云盘",
    "和彩云": "移动云盘",
    "caiyun": "移动云盘",
    "caiyunpan": "移动云盘",
}


def normalize_cloud_name(raw: str) -> Optional[str]:
    """将输入的网盘别名规范化为系统标准网盘名"""
    if not raw:
        return None
    cleaned = raw.strip().lower()
    return CLOUD_ALIAS_MAP.get(cleaned) or CLOUD_ALIAS_MAP.get(raw.strip())


def parse_boolean_value(val: Any, default: bool = True) -> bool:
    """解析布尔值，兼容中英文及数字表达"""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "t", "是", "启用", "开启", "on", "active", "正常"):
        return True
    if s in ("0", "false", "no", "n", "f", "否", "停用", "关闭", "off", "inactive", "禁用"):
        return False
    return default


def export_accounts_csv(cloud_name: Optional[str] = None) -> str:
    """
    导出网盘账号列表为带 UTF-8 BOM 的 CSV 格式文本。
    支持按平台过滤导出。
    """
    accounts = get_all_accounts(cloud_name=cloud_name if cloud_name and cloud_name != "ALL" else None)

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM

    writer = csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    headers = [
        "网盘平台",
        "账号备注",
        "凭据内容",
        "优先级",
        "轮询权重",
        "是否启用",
        "用户名",
        "状态",
        "已用空间(字节)",
        "总空间(字节)",
        "累计转存",
    ]
    writer.writerow(headers)

    for acc in accounts:
        is_active_str = "是" if acc.get("is_active") == 1 else "否"
        is_valid = acc.get("is_valid") == 1
        status_str = "正常就绪" if is_valid else ("失效" if acc.get("invalid_reason") else "待检")
        writer.writerow(
            [
                acc.get("cloud_name", ""),
                acc.get("account_name", ""),
                acc.get("credential", ""),
                acc.get("priority", 0),
                acc.get("weight", 10),
                is_active_str,
                acc.get("username", "") or "",
                status_str,
                acc.get("used_space_bytes", 0) or 0,
                acc.get("total_space_bytes", 0) or 0,
                acc.get("transferred_count", 0) or 0,
            ]
        )

    return output.getvalue()


def generate_accounts_template_csv() -> str:
    """
    生成标准网盘账号导入 CSV 模板（带 UTF-8 BOM 与示例数据）。
    """
    output = io.StringIO()
    output.write("\ufeff")

    writer = csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    headers = [
        "网盘平台",
        "账号备注",
        "凭据内容",
        "优先级",
        "轮询权重",
        "是否启用",
    ]
    writer.writerow(headers)

    sample_rows = [
        ["夸克网盘", "夸克-示例01", "_UP_A4A_11_=xxx; cookie_here...", 0, 10, "是"],
        ["百度网盘", "百度-示例01", "BDUSS=xxx; STOKEN=yyy...", 0, 10, "是"],
        ["阿里云盘", "阿里-示例01", "e884102640e947548c66e2c39d73d6", 0, 10, "是"],
        ["UC网盘", "UC-示例01", "token_value_here...", 0, 10, "是"],
        ["迅雷网盘", "迅雷-示例01", '{"refresh_token":"xxx","captcha_sign":"yyy"}', 0, 10, "是"],
        ["光鸭云盘", "光鸭-示例01", "eyJhbGciOi...", 0, 10, "是"],
        ["悟空网盘", "悟空-示例01", "session_token_here...", 0, 10, "是"],
        ["移动云盘", "移动-示例01", "authorization_token_here...", 0, 10, "是"],
    ]

    for row in sample_rows:
        writer.writerow(row)

    return output.getvalue()


def _decode_csv_content(csv_data: Union[str, bytes]) -> str:
    """自动探测并解码 CSV 字节流"""
    if isinstance(csv_data, str):
        return csv_data

    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk", "latin-1"]
    for enc in encodings:
        try:
            return csv_data.decode(enc)
        except UnicodeDecodeError:
            continue
    return csv_data.decode("utf-8", errors="replace")


def import_accounts_from_csv(
    csv_data: Union[str, bytes], auto_test: bool = True
) -> Dict[str, Any]:
    """
    从 CSV 文本或文件内容批量解析并导入网盘账号。
    支持中英文表头、模糊匹配与无表头位置兼容。
    """
    text = _decode_csv_content(csv_data)
    # 去除首尾空白与 BOM
    text = text.lstrip("\ufeff").strip()

    if not text:
        return {
            "success": False,
            "message": "CSV 内容为空，未导入任何账号",
            "total": 0,
            "imported": 0,
            "failed": 0,
            "errors": [],
            "account_ids": [],
        }

    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]

    if not rows:
        return {
            "success": False,
            "message": "CSV 未包含有效数据行",
            "total": 0,
            "imported": 0,
            "failed": 0,
            "errors": [],
            "account_ids": [],
        }

    # 1. 检测表头或定位列索引
    first_row = [c.strip() for c in rows[0]]
    header_indices: Dict[str, int] = {}

    cloud_headers = {"网盘平台", "平台名称", "网盘", "平台", "cloud_name", "cloud"}
    name_headers = {"账号备注", "账号名称", "账号名", "备注", "别名", "account_name", "name"}
    cred_headers = {"凭据内容", "凭证内容", "凭据", "凭证", "cookie", "token", "credential", "credentials", "cookies"}
    prio_headers = {"优先级", "priority"}
    weight_headers = {"轮询权重", "权重", "weight"}
    active_headers = {"是否启用", "启用", "状态", "is_active", "active", "enabled"}

    has_header = False
    for idx, col in enumerate(first_row):
        col_clean = col.lower().replace(" ", "").replace("_", "")
        if any(h.lower().replace(" ", "").replace("_", "") == col_clean for h in cloud_headers):
            header_indices["cloud_name"] = idx
            has_header = True
        elif any(h.lower().replace(" ", "").replace("_", "") == col_clean for h in name_headers):
            header_indices["account_name"] = idx
            has_header = True
        elif any(h.lower().replace(" ", "").replace("_", "") == col_clean for h in cred_headers):
            header_indices["credential"] = idx
            has_header = True
        elif any(h.lower().replace(" ", "").replace("_", "") == col_clean for h in prio_headers):
            header_indices["priority"] = idx
            has_header = True
        elif any(h.lower().replace(" ", "").replace("_", "") == col_clean for h in weight_headers):
            header_indices["weight"] = idx
            has_header = True
        elif any(h.lower().replace(" ", "").replace("_", "") == col_clean for h in active_headers):
            header_indices["is_active"] = idx
            has_header = True

    data_rows = rows[1:] if has_header else rows
    start_line_offset = 2 if has_header else 1

    # 如果没匹配到有效表头，按默认顺序尝试：平台, 备注, 凭据, 优先级, 权重, 是否启用
    if "cloud_name" not in header_indices or "credential" not in header_indices:
        header_indices = {
            "cloud_name": 0,
            "account_name": 1,
            "credential": 2,
            "priority": 3,
            "weight": 4,
            "is_active": 5,
        }

    imported_ids: List[int] = []
    errors: List[Dict[str, Any]] = []

    for idx, row in enumerate(data_rows):
        line_no = idx + start_line_offset
        if not any(cell.strip() for cell in row):
            continue

        def get_col(field_key: str, default: str = "") -> str:
            c_idx = header_indices.get(field_key)
            if c_idx is not None and c_idx < len(row):
                return row[c_idx].strip()
            return default

        raw_cloud = get_col("cloud_name")
        raw_name = get_col("account_name")
        raw_cred = get_col("credential")
        raw_prio = get_col("priority", "0")
        raw_weight = get_col("weight", "10")
        raw_active = get_col("is_active", "1")

        # 校验网盘平台
        norm_cloud = normalize_cloud_name(raw_cloud)
        if not norm_cloud:
            errors.append({
                "row": line_no,
                "error": f"网盘平台「{raw_cloud or '(空)'}」无效或未识别，支持平台包括：夸克网盘、百度网盘、阿里云盘、UC网盘、迅雷网盘、光鸭云盘、悟空网盘、移动云盘",
            })
            continue

        # 校验凭据
        if not raw_cred:
            errors.append({
                "row": line_no,
                "error": f"第 {line_no} 行「{norm_cloud}」的凭据内容 (Cookie/Token) 不能为空",
            })
            continue

        # 解析优先级
        try:
            priority = int(raw_prio) if raw_prio else 0
        except (ValueError, TypeError):
            priority = 0

        # 解析权重
        try:
            weight = max(1, min(100, int(raw_weight))) if raw_weight else 10
        except (ValueError, TypeError):
            weight = 10

        # 解析启用状态
        is_active = parse_boolean_value(raw_active, default=True)

        # 账号名称默认生成
        account_name = raw_name or f"{norm_cloud}-账号"

        account_payload = {
            "cloud_name": norm_cloud,
            "account_name": account_name,
            "credential": raw_cred,
            "priority": priority,
            "weight": weight,
            "is_active": is_active,
        }

        new_id = create_account(account_payload)
        if new_id:
            imported_ids.append(new_id)
        else:
            errors.append({
                "row": line_no,
                "error": f"第 {line_no} 行账号入库保存失败 (平台: {norm_cloud}, 名称: {account_name})",
            })

    # 执行自测（如果开启）
    tested_count = 0
    if auto_test and imported_ids:
        mgr = AccountPoolManager.get_instance()
        for acc_id in imported_ids:
            try:
                mgr.inspect_and_refresh_account(acc_id)
                tested_count += 1
            except Exception as e:
                logger.warning(f"导入后账号(ID={acc_id})自动探测异常: {e}")

    total_count = len(data_rows)
    success = len(imported_ids) > 0 or (total_count == 0 and len(errors) == 0)
    msg = f"成功导入 {len(imported_ids)} 个网盘账号"
    if errors:
        msg += f"，失败/跳过 {len(errors)} 条"
    if auto_test and tested_count:
        msg += f"，已完成 {tested_count} 个账号的连通性探测"

    return {
        "success": success,
        "message": msg,
        "total": total_count,
        "imported": len(imported_ids),
        "failed": len(errors),
        "errors": errors,
        "account_ids": imported_ids,
    }
