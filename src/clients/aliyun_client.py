import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.clients.base_client import BasePanClient

logger = logging.getLogger(__name__)

# 全局缓存，避免频繁刷新 Token 触发风控
# 结构: {refresh_token: {"access_token": str, "drive_id": str, "expires_at": float}}
_ALIYUN_ACCESS_TOKEN_CACHE: Dict[str, Dict[str, Any]] = {}


class AliyunPanClient(BasePanClient):
    def __init__(self, refresh_token: str) -> None:
        self.refresh_token = refresh_token.strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://www.alipan.com",
                "Referer": "https://www.alipan.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "X-Canary": "client=web,app=share,version=v2.3.1",
            }
        )
        self.access_token = ""
        self.drive_id = ""
        self._refresh_access_token()

    def store(
        self, share_url: str, to_dir: str = "root"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        share_id = self._extract_share_id(share_url)
        if not share_id:
            logger.error("阿里云盘链接解析失败: %s", share_url)
            return None, None, None

        share_info = self._post_anonymous(
            "https://api.aliyundrive.com/adrive/v3/share_link/get_share_by_anonymous",
            {"share_id": share_id},
        )
        if not share_info or not share_info.get("file_infos"):
            err_msg = (share_info or {}).get("message") or (share_info or {}).get("code") or "分享链接无效或已过期"
            logger.error("阿里云盘获取分享信息失败: %s (share_id=%s)", err_msg, share_id)
            return None, None, None

        share_token_data = self._request(
            "POST",
            "https://api.aliyundrive.com/v2/share_link/get_share_token",
            {"share_id": share_id},
        )
        share_token = (share_token_data or {}).get("share_token")
        if not share_token:
            err_msg = (share_token_data or {}).get("message") or "获取 share_token 失败"
            logger.error("阿里云盘获取 share_token 失败: %s (share_id=%s)", err_msg, share_id)
            return None, None, None

        from src.services.ad_filter_service import is_ad_filename

        raw_file_infos = share_info["file_infos"]
        file_infos = [f for f in raw_file_infos if not is_ad_filename(f.get("name", ""))]
        if not file_infos:
            logger.warning("阿里云盘分享内容全为广告，已终止转存与分享")
            return None, None, None

        title = share_info.get("share_name") or file_infos[0].get("name") or "阿里云盘资源"

        requests_payload = []
        for idx, file_info in enumerate(file_infos):
            requests_payload.append(
                {
                    "body": {
                        "auto_rename": True,
                        "file_id": file_info["file_id"],
                        "share_id": share_id,
                        "to_drive_id": self.drive_id,
                        "to_parent_file_id": to_dir or "root",
                    },
                    "headers": {"Content-Type": "application/json"},
                    "id": str(idx),
                    "method": "POST",
                    "url": "/file/copy",
                }
            )

        batch_result = self._request(
            "POST",
            "https://api.aliyundrive.com/adrive/v4/batch",
            {"requests": requests_payload, "resource": "file"},
            extra_headers={"X-Share-Token": share_token},
        )
        responses = (batch_result or {}).get("responses") or []
        if not responses:
            err_msg = (batch_result or {}).get("message") or "批量转存无响应"
            logger.error("阿里云盘批量转存失败: %s", err_msg)
            return None, None, None

        new_file_ids: List[str] = []
        for item in responses:
            body = item.get("body") or {}
            if body.get("code"):
                logger.error("阿里云盘单个文件转存返回错误: %s (%s)", body.get("message") or body.get("code"), body)
                return None, None, None
            if body.get("file_id"):
                new_file_ids.append(body["file_id"])

        if not new_file_ids:
            logger.error("阿里云盘未返回转存后的 file_id")
            return None, None, None

        # 尝试植入个人自定义引流广告 (若已配置并启用)
        for fid in new_file_ids:
            try:
                self.add_ad(fid)
            except Exception:
                pass


        share_result = self._request(
            "POST",
            "https://api.aliyundrive.com/adrive/v2/share_link/create",
            {
                "drive_id": self.drive_id,
                "expiration": "",
                "share_pwd": "",
                "file_id_list": cleaned_file_ids,
            },
        )
        share_url_new = (share_result or {}).get("share_url")
        if not share_url_new:
            err_msg = (share_result or {}).get("message") or (share_result or {}).get("code") or "创建分享失败"
            logger.error("阿里云盘创建分享失败: %s", err_msg)
            return None, None, None

        return json.dumps(cleaned_file_ids, ensure_ascii=False), title, share_url_new

    def _clean_ad_files_and_folders(self, file_ids: List[str]) -> List[str]:
        """扫描阿里云盘转存后的文件，智能清理广告/引流文件"""
        from src.services.ad_filter_service import is_ad_filename

        valid_ids: List[str] = []
        ad_ids: List[str] = []

        for fid in file_ids:
            try:
                info = self._request(
                    "POST",
                    "https://api.aliyundrive.com/v2/file/get",
                    {"drive_id": self.drive_id, "file_id": fid},
                )
                name = (info or {}).get("name") or ""
                if name and is_ad_filename(name):
                    logger.info("阿里云盘转存项命中广告关键词，标记清理: %s (fid=%s)", name, fid)
                    ad_ids.append(fid)
                else:
                    valid_ids.append(fid)
            except Exception as exc:
                logger.warning("阿里云盘检测文件信息异常 (fid=%s): %s", fid, exc)
                valid_ids.append(fid)

        if ad_ids:
            try:
                self.del_file(ad_ids)
                logger.info("阿里云盘已清理广告文件 %d 项: %s", len(ad_ids), ad_ids)
            except Exception as exc:
                logger.error("阿里云盘清理广告文件失败: %s", exc)

        return valid_ids

    def add_ad(self, parent_file_id: str, ad_share_url: Optional[str] = None) -> bool:
        """向阿里云盘指定的目录植入个人自定义引流/宣传文件"""
        target_url = (ad_share_url or "").strip()
        if not target_url:
            from src.services.system_config_service import get_ad_share_url_for_disk
            target_url = get_ad_share_url_for_disk("aliyun")

        if not target_url:
            return False

        share_id = self._extract_share_id(target_url)
        if not share_id:
            logger.warning("阿里云盘广告植入链接无效: %s", target_url)
            return False

        try:
            share_info = self._post_anonymous(
                "https://api.aliyundrive.com/adrive/v3/share_link/get_share_by_anonymous",
                {"share_id": share_id},
            )
            file_infos = (share_info or {}).get("file_infos") or []
            if not file_infos:
                return False

            token_data = self._request(
                "POST",
                "https://api.aliyundrive.com/v2/share_link/get_share_token",
                {"share_id": share_id},
            )
            share_token = (token_data or {}).get("share_token")
            if not share_token:
                return False

            first_file = file_infos[0]
            copy_res = self._request(
                "POST",
                "https://api.aliyundrive.com/adrive/v4/batch",
                {
                    "requests": [
                        {
                            "body": {
                                "auto_rename": True,
                                "file_id": first_file["file_id"],
                                "share_id": share_id,
                                "to_drive_id": self.drive_id,
                                "to_parent_file_id": parent_file_id or "root",
                            },
                            "headers": {"Content-Type": "application/json"},
                            "id": "ad-copy-0",
                            "method": "POST",
                            "url": "/file/copy",
                        }
                    ],
                    "resource": "file",
                },
                extra_headers={"X-Share-Token": share_token},
            )
            if copy_res and (copy_res.get("responses") or []):
                logger.info("阿里云盘已向目录 %s 成功植入自定义引流文件 (share_id=%s)", parent_file_id, share_id)
                return True
        except Exception as exc:
            logger.error("阿里云盘植入自定义广告异常: %s", exc)
        return False


    def get_or_create_dir(self, dir_name: str, parent_file_id: str = "root") -> str:
        """获取指定名称的文件夹 file_id，若不存在则自动新建"""
        if not dir_name or dir_name.strip() in ("", "/"):
            return parent_file_id
        clean_name = dir_name.strip().strip("/")
        try:
            res = self._request(
                "POST",
                "https://api.aliyundrive.com/adrive/v2/file/create",
                {
                    "drive_id": self.drive_id,
                    "parent_file_id": parent_file_id,
                    "name": clean_name,
                    "type": "folder",
                    "check_name_mode": "refuse",
                },
            )
            file_id = (res or {}).get("file_id")
            if file_id:
                logger.info("阿里云盘新建/确认目录 [%s]: file_id=%s", clean_name, file_id)
                return str(file_id)

            # 查询目录列表兜底
            list_res = self._request(
                "POST",
                "https://api.aliyundrive.com/adrive/v3/file/list",
                {
                    "drive_id": self.drive_id,
                    "parent_file_id": parent_file_id,
                    "limit": 100,
                    "type": "folder",
                },
            )
            for item in (list_res or {}).get("items", []):
                if item.get("name") == clean_name:
                    found_id = str(item.get("file_id") or "")
                    if found_id:
                        logger.info("阿里云盘找到现有目录 [%s]: file_id=%s", clean_name, found_id)
                        return found_id
        except Exception as exc:
            logger.error("阿里云盘获取或创建目录异常: %s", exc)
        return parent_file_id

    def del_file(self, file_ids: List[str]) -> bool:
        if not file_ids:
            return False

        requests_payload = []
        for idx, file_id in enumerate(file_ids):
            requests_payload.append(
                {
                    "body": {"drive_id": self.drive_id, "file_id": file_id},
                    "headers": {"Content-Type": "application/json"},
                    "id": f"trash-{idx}",
                    "method": "POST",
                    "url": "/recyclebin/trash",
                }
            )

        result = self._request(
            "POST",
            "https://api.aliyundrive.com/adrive/v4/batch",
            {"requests": requests_payload, "resource": "file"},
        )
        responses = (result or {}).get("responses") or []
        if not responses:
            logger.error("阿里云盘删除文件请求失败: %s", (result or {}).get("message") or "无响应")
            return False
        return True

    def _refresh_access_token(self, force: bool = False) -> None:
        global _ALIYUN_ACCESS_TOKEN_CACHE

        now = time.time()
        cached = _ALIYUN_ACCESS_TOKEN_CACHE.get(self.refresh_token)
        if not force and cached and cached.get("access_token") and now < cached.get("expires_at", 0) - 60:
            self.access_token = cached["access_token"]
            self.drive_id = cached.get("drive_id", "")
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            return

        try:
            data = self._post_anonymous(
                "https://api.aliyundrive.com/token/refresh",
                {"refresh_token": self.refresh_token},
            )
        except Exception as exc:
            logger.error("阿里云盘请求 refresh_token 异常: %s", exc)
            raise ValueError(f"阿里云盘刷新 Token 请求失败: {exc}")

        if not data or not data.get("access_token"):
            err_code = (data or {}).get("code") or "未知原因"
            err_msg = (data or {}).get("message") or "refresh_token 无效或已过期"
            logger.error("阿里云盘认证失败: %s (%s)", err_msg, err_code)
            raise ValueError(f"阿里云盘 refresh_token 无效或已过期: {err_msg}")

        self.access_token = data["access_token"]
        self.drive_id = (
            data.get("default_drive_id")
            or data.get("resource_drive_id")
            or data.get("backup_drive_id")
            or ""
        )
        if not self.drive_id:
            logger.error("阿里云盘未返回有效 drive_id: %s", data)
            raise ValueError("阿里云盘未返回有效 drive_id")

        expires_in = int(data.get("expires_in", 7200))
        _ALIYUN_ACCESS_TOKEN_CACHE[self.refresh_token] = {
            "access_token": self.access_token,
            "drive_id": self.drive_id,
            "expires_at": now + expires_in,
        }

        self.session.headers["Authorization"] = f"Bearer {self.access_token}"

    def _request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        headers = dict(self.session.headers)
        if extra_headers:
            headers.update(extra_headers)

        response = self.session.request(method, url, json=payload or {}, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()

    def _post_anonymous(self, url: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_share_id(url: str) -> str:
        match = re.search(r"/s/([a-zA-Z0-9]+)", url)
        if match:
            return match.group(1)
        return ""

