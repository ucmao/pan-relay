import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from src.clients.base_client import BasePanClient

logger = logging.getLogger(__name__)


class CaiyunPanClient(BasePanClient):
    """
    中国移动云盘 (和彩云 / 139云盘) 客户端实现
    提供转存 (store)、创建新分享与文件删除 (del_file) 功能。
    """
    api_base = "https://api.caiyun.feixin.10086.cn"
    orches_base = "https://orches.yun.139.com"

    def __init__(self, credential: Union[str, Dict[str, Any]]) -> None:
        self.raw_credential = credential
        self.auth_token = ""
        self.account = ""
        self.cookie = ""

        if isinstance(credential, dict):
            self.auth_token = str(credential.get("auth_token") or credential.get("authorization") or credential.get("token") or "").strip()
            self.account = str(credential.get("account") or credential.get("phone") or "").strip()
            self.cookie = str(credential.get("cookie") or credential.get("Cookie") or "").strip()
        elif isinstance(credential, str):
            clean_cred = credential.strip()
            if clean_cred.startswith("{") and clean_cred.endswith("}"):
                try:
                    data = json.loads(clean_cred)
                    if isinstance(data, dict):
                        self.auth_token = str(data.get("auth_token") or data.get("authorization") or data.get("token") or "").strip()
                        self.account = str(data.get("account") or data.get("phone") or "").strip()
                        self.cookie = str(data.get("cookie") or data.get("Cookie") or "").strip()
                except Exception:
                    self.auth_token = clean_cred
            else:
                self.auth_token = clean_cred

        self.session = requests.Session()
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "mcloud-client": "10701",
            "mcloud-channel": "1000101",
            "mcloud-sign": "PC",
            "Origin": "https://yun.139.com",
            "Referer": "https://yun.139.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
        }
        if self.auth_token:
            if not self.auth_token.lower().startswith("bearer ") and not self.auth_token.lower().startswith("basic "):
                headers["Authorization"] = f"Bearer {self.auth_token}"
            else:
                headers["Authorization"] = self.auth_token
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.account:
            headers["mcloud-account"] = self.account

        self.session.headers.update(headers)

    def _parse_share_url(self, share_url: str) -> Tuple[Optional[str], Optional[str]]:
        """从移动云盘分享链接中提取 share_id 与提取码"""
        if not share_url:
            return None, None

        match = re.search(
            r"(?:yun\.139\.com/shareweb/#/w/i/|caiyun\.139\.com/w/i/|caiyun\.139\.com/m/i\?|pan\.10086\.cn/s/|/w/i/)([a-zA-Z0-9_-]+)",
            share_url,
            re.IGNORECASE,
        )
        if not match:
            # 兼容 query 参数 linkID
            q_match = re.search(r"linkId=([a-zA-Z0-9_-]+)", share_url, re.IGNORECASE)
            if q_match:
                share_id = q_match.group(1)
            else:
                return None, None
        else:
            share_id = match.group(1)

        pwd_match = re.search(r"(?:[?&]pwd=|提取码[:：=\s]*|密码[:：=\s]*)([a-zA-Z0-9]{4,6})", share_url, re.IGNORECASE)
        pwd = pwd_match.group(1) if pwd_match else None
        return share_id, pwd

    def _request_api(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.api_base}{path}" if path.startswith("/") else path
        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                logger.error(f"移动云盘 API 响应异常 [{resp.status_code}]: {resp.text}")
                return None
        except Exception as exc:
            logger.error(f"移动云盘 API 请求错误: {exc}")
            return None

    def store(
        self, share_url: str, to_pdir_path: str = "/"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        转存移动云盘分享链接并生成新分享。
        """
        share_id, pwd = self._parse_share_url(share_url)
        if not share_id:
            logger.error(f"移动云盘链接解析失败: {share_url}")
            return None, None, None

        # 1. 获取分享内容信息
        share_info = self._request_api(
            "POST",
            "/orchestration/personalCloud/share/v1.0/getShareInfo",
            payload={
                "linkID": share_id,
                "password": pwd or "",
            },
        )
        if not share_info or not share_info.get("success", False):
            # 尝试备用或简单响应格式
            if not share_info or share_info.get("code") not in ("0", 0, "0000", 200, None):
                logger.error(f"移动云盘获取分享信息失败: {share_info}")
                return None, None, None

        data = share_info.get("data") or share_info
        from src.services.ad_filter_service import is_ad_filename

        raw_content_list = data.get("contentList") or data.get("fileList") or []
        content_list = [
            item for item in raw_content_list
            if not is_ad_filename(item.get("contentName") or item.get("name") or "")
        ]
        if not content_list:
            logger.warning(f"移动云盘分享内容全为广告，已终止转存与分享: {share_url}")
            return None, None, None

        first_item = content_list[0]
        file_name = first_item.get("contentName") or data.get("shareTitle") or "移动云盘转存文件"

        content_ids = []
        for item in content_list:
            cid = item.get("contentID") or item.get("id") or item.get("caID")
            if cid:
                content_ids.append(cid)

        # 2. 执行批量转存
        target_dir = to_pdir_path if to_pdir_path not in ("/", "") else "root"
        restore_res = self._request_api(
            "POST",
            "/orchestration/personalCloud/batch/v1.0/createBatch",
            payload={
                "action": "restore",
                "linkID": share_id,
                "contentIDs": content_ids,
                "targetDirID": target_dir,
            },
        )
        if not restore_res or not (restore_res.get("success", True) or restore_res.get("code") in ("0", 0, "0000")):
            logger.error(f"移动云盘转存失败: {restore_res}")
            return None, None, None

        saved_data = restore_res.get("data") or restore_res
        saved_file_ids = saved_data.get("contentIDs") or content_ids

        # 尝试植入个人自定义引流广告 (若已配置并启用)
        for fid in saved_file_ids:
            try:
                self.add_ad(fid)
            except Exception:
                pass


        # 3. 创建新分享链接
        share_create_res = self._request_api(
            "POST",
            "/orchestration/personalCloud/share/v1.0/createShare",
            payload={
                "contentIDs": saved_file_ids,
                "shareType": 1,
                "period": 0,  # 永久
                "shareTitle": file_name,
            },
        )
        new_share_url = None
        if share_create_res:
            res_data = share_create_res.get("data") or share_create_res
            new_share_url = res_data.get("shareUrl") or res_data.get("linkUrl")
            new_link_id = res_data.get("linkID") or res_data.get("id")
            if not new_share_url and new_link_id:
                new_share_url = f"https://yun.139.com/shareweb/#/w/i/{new_link_id}"
                new_pwd = res_data.get("password")
                if new_pwd:
                    new_share_url += f"?pwd={new_pwd}"

        saved_file_id_str = json.dumps(saved_file_ids, ensure_ascii=False) if isinstance(saved_file_ids, list) else str(saved_file_ids)
        return saved_file_id_str, file_name, new_share_url


    def get_or_create_dir(self, dir_name: str, parent_id: str = "root") -> str:
        """获取或创建移动云盘目标目录"""
        if not dir_name or dir_name.strip() in ("", "/"):
            return parent_id or "root"
        clean_name = dir_name.strip().strip("/")
        try:
            res = self._request_api(
                "POST",
                "/orchestration/personalCloud/catalog/v1.0/createCatalog",
                payload={"parentCatalogID": parent_id or "root", "catalogName": clean_name},
            )
            if res:
                data = res.get("data") or res
                cat_id = data.get("catalogID") or data.get("id")
                if cat_id:
                    logger.info(f"移动云盘新建/确认目录 [{clean_name}]: {cat_id}")
                    return str(cat_id)
        except Exception as exc:
            logger.error(f"移动云盘创建目录异常: {exc}")
        return parent_id or "root"

    def _clean_ad_files_and_folders(self, file_ids: List[str]) -> List[str]:
        """清理移动云盘转存文件中的广告引流文件"""
        from src.services.ad_filter_service import is_ad_filename

        valid_ids = []
        ad_ids = []
        for fid in file_ids:
            try:
                info = self._request_api(
                    "POST",
                    "/orchestration/personalCloud/catalog/v1.0/getContentInfo",
                    payload={"contentID": fid},
                )
                data = (info or {}).get("data") or info or {}
                name = data.get("contentName") or data.get("name") or ""
                if name and is_ad_filename(name):
                    logger.info(f"移动云盘转存项命中广告关键词: {name} ({fid})")
                    ad_ids.append(fid)
                else:
                    valid_ids.append(fid)
            except Exception:
                valid_ids.append(fid)

        if ad_ids:
            try:
                self.del_file(ad_ids)
                logger.info(f"移动云盘已清理广告文件 {len(ad_ids)} 项")
            except Exception as exc:
                logger.error(f"移动云盘清理广告失败: {exc}")

        return valid_ids

    def add_ad(self, target_dir_id: str, ad_share_url: Optional[str] = None) -> bool:
        """向移动云盘指定的目录植入个人自定义引流/宣传文件"""
        target_url = (ad_share_url or "").strip()
        if not target_url:
            from src.services.system_config_service import get_ad_share_url_for_disk
            target_url = get_ad_share_url_for_disk("caiyun")

        if not target_url:
            return False

        share_id, pwd = self._parse_share_url(target_url)
        if not share_id:
            logger.warning(f"移动云盘广告植入链接无效: {target_url}")
            return False

        try:
            share_info = self._request_api(
                "POST",
                "/orchestration/personalCloud/share/v1.0/getShareInfo",
                payload={"linkID": share_id, "password": pwd or ""},
            )
            data = (share_info or {}).get("data") or share_info or {}
            content_list = data.get("contentList") or data.get("fileList") or []
            if not content_list:
                return False

            first_cid = content_list[0].get("contentID") or content_list[0].get("id") or content_list[0].get("caID")
            if not first_cid:
                return False

            restore_res = self._request_api(
                "POST",
                "/orchestration/personalCloud/batch/v1.0/createBatch",
                payload={
                    "action": "restore",
                    "linkID": share_id,
                    "contentIDs": [first_cid],
                    "targetDirID": target_dir_id or "root",
                },
            )
            if restore_res and (restore_res.get("success", False) or restore_res.get("code") in ("0", 0, "0000")):
                logger.info(f"移动云盘已向目录 {target_dir_id} 成功植入自定义引流文件 (share_id={share_id})")
                return True
        except Exception as exc:
            logger.error(f"移动云盘植入自定义广告异常: {exc}")
        return False


    def del_file(self, file_ids: Union[str, List[str]]) -> bool:
        """从移动云盘中删除文件"""
        if not file_ids:
            return True

        if isinstance(file_ids, str):
            if file_ids.startswith("["):
                try:
                    targets = json.loads(file_ids)
                except Exception:
                    targets = [file_ids]
            else:
                targets = [file_ids]
        else:
            targets = list(file_ids)

        res = self._request_api(
            "POST",
            "/orchestration/personalCloud/batch/v1.0/createBatch",
            payload={
                "action": "delete",
                "contentIDs": targets,
            },
        )
        if res and (res.get("success", False) or res.get("code") in ("0", 0, "0000", 200, None)):
            logger.info(f"移动云盘删除文件成功: {targets}")
            return True

        logger.error(f"移动云盘删除文件失败: {res}")
        return False
