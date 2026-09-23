import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from src.clients.base_client import BasePanClient

logger = logging.getLogger(__name__)


class WukongPanClient(BasePanClient):
    """
    悟空网盘客户端实现 (wkbrowser.com / 悟空浏览器网盘)
    提供转存 (store)、创建新分享与文件删除 (del_file) 功能。
    """
    api_base = "https://pan.wkbrowser.com"

    def __init__(self, credential: Union[str, Dict[str, Any]]) -> None:
        self.raw_credential = credential
        self.cookie = ""
        self.token = ""

        if isinstance(credential, dict):
            self.cookie = str(credential.get("cookie") or credential.get("Cookie") or "").strip()
            self.token = str(credential.get("token") or credential.get("access_token") or "").strip()
        elif isinstance(credential, str):
            clean_cred = credential.strip()
            if clean_cred.startswith("{") and clean_cred.endswith("}"):
                try:
                    data = json.loads(clean_cred)
                    if isinstance(data, dict):
                        self.cookie = str(data.get("cookie") or data.get("Cookie") or "").strip()
                        self.token = str(data.get("token") or data.get("access_token") or "").strip()
                except Exception:
                    self.cookie = clean_cred
            else:
                self.cookie = clean_cred

        self.session = requests.Session()
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://pan.wkbrowser.com",
            "Referer": "https://pan.wkbrowser.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers.update(headers)

    def _parse_share_url(self, share_url: str) -> Tuple[Optional[str], Optional[str]]:
        """从悟空网盘分享链接解析出 share_id 与提取码"""
        if not share_url:
            return None, None

        match = re.search(r"(?:pan\.wkbrowser\.com|wkbrowser\.com)/(?:s/|share/)?([a-zA-Z0-9_-]+)", share_url, re.IGNORECASE)
        if not match:
            return None, None

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
                logger.error(f"悟空网盘 API 响应异常 [{resp.status_code}]: {resp.text}")
                return None
        except Exception as exc:
            logger.error(f"悟空网盘 API 请求错误: {exc}")
            return None

    def store(
        self, share_url: str, to_pdir_path: str = "/"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        转存悟空网盘分享链接并生成新分享。
        """
        share_id, pwd = self._parse_share_url(share_url)
        if not share_id:
            logger.error(f"悟空网盘链接解析失败: {share_url}")
            return None, None, None

        # 1. 获取分享详情
        detail = self._request_api(
            "GET",
            "/api/v1/share/info",
            params={"share_id": share_id, "pwd": pwd or ""},
        )
        if not detail or detail.get("code") not in (0, 200, None):
            logger.error(f"悟空网盘获取分享详情失败: {detail}")
            return None, None, None

        data = detail.get("data") or detail
        from src.services.ad_filter_service import is_ad_filename

        raw_file_list = data.get("files") or data.get("file_list") or []
        file_list = [
            item for item in raw_file_list
            if not is_ad_filename(item.get("name") or item.get("title") or "")
        ]
        if not file_list:
            logger.warning(f"悟空网盘分享内容全为广告，已终止转存与分享: {share_url}")
            return None, None, None

        file_ids = [item.get("file_id") or item.get("id") for item in file_list if (item.get("file_id") or item.get("id"))]
        file_name = (file_list[0].get("name") if file_list else data.get("title")) or "悟空网盘分享文件"


        # 2. 转存文件
        save_res = self._request_api(
            "POST",
            "/api/v1/share/save",
            payload={
                "share_id": share_id,
                "file_ids": file_ids,
                "target_dir_id": to_pdir_path if to_pdir_path not in ("/", "") else "0",
            },
        )
        if not save_res or save_res.get("code") not in (0, 200, None):
            logger.error(f"悟空网盘转存失败: {save_res}")
            return None, None, None

        saved_data = save_res.get("data") or save_res
        saved_file_ids = saved_data.get("file_ids") or file_ids

        # 尝试植入个人自定义引流广告 (若已配置并启用)
        for fid in saved_file_ids:
            try:
                self.add_ad(fid)
            except Exception:
                pass


        # 3. 创建新分享
        new_share_res = self._request_api(
            "POST",
            "/api/v1/share/create",
            payload={
                "file_ids": saved_file_ids,
                "title": file_name,
                "expire_type": 0,
            },
        )
        new_share_url = None
        if new_share_res:
            share_info = new_share_res.get("data") or new_share_res
            new_share_url = share_info.get("share_url") or share_info.get("url")
            sid = share_info.get("share_id") or share_info.get("id")
            if not new_share_url and sid:
                new_share_url = f"https://pan.wkbrowser.com/s/{sid}"
                passcode = share_info.get("pwd") or share_info.get("passcode")
                if passcode:
                    new_share_url += f"?pwd={passcode}"

        saved_file_id_str = json.dumps(saved_file_ids, ensure_ascii=False) if isinstance(saved_file_ids, list) else str(saved_file_ids)
        return saved_file_id_str, file_name, new_share_url


    def get_or_create_dir(self, dir_name: str, parent_id: str = "0") -> str:
        """获取或创建悟空网盘目录"""
        if not dir_name or dir_name.strip() in ("", "/"):
            return parent_id or "0"
        clean_name = dir_name.strip().strip("/")
        try:
            res = self._request_api(
                "POST",
                "/api/v1/folder/create",
                payload={"name": clean_name, "parent_id": parent_id or "0"},
            )
            if res and (res.get("code") in (0, 200, None) or res.get("data")):
                data = res.get("data") or res
                fid = data.get("file_id") or data.get("id")
                if fid:
                    logger.info(f"悟空网盘成功创建目录 [{clean_name}]: {fid}")
                    return str(fid)
        except Exception as exc:
            logger.error(f"悟空网盘创建目录异常: {exc}")
        return parent_id or "0"

    def _clean_ad_files_and_folders(self, file_ids: List[str]) -> List[str]:
        """清理悟空网盘转存文件中的广告引流文件"""
        from src.services.ad_filter_service import is_ad_filename

        valid_ids = []
        ad_ids = []
        for fid in file_ids:
            try:
                info = self._request_api("GET", "/api/v1/file/info", params={"file_id": fid})
                data = (info or {}).get("data") or info or {}
                name = data.get("name") or data.get("title") or ""
                if name and is_ad_filename(name):
                    logger.info(f"悟空网盘转存项命中广告: {name} ({fid})")
                    ad_ids.append(fid)
                else:
                    valid_ids.append(fid)
            except Exception:
                valid_ids.append(fid)

        if ad_ids:
            try:
                self.del_file(ad_ids)
                logger.info(f"悟空网盘已清理广告文件 {len(ad_ids)} 项")
            except Exception as exc:
                logger.error(f"悟空网盘清理广告失败: {exc}")

        return valid_ids

    def add_ad(self, target_dir_id: str, ad_share_url: Optional[str] = None) -> bool:
        """向悟空网盘指定的目录植入个人自定义引流/宣传文件"""
        target_url = (ad_share_url or "").strip()
        if not target_url:
            from src.services.system_config_service import get_ad_share_url_for_disk
            target_url = get_ad_share_url_for_disk("wukong")

        if not target_url:
            return False

        share_id, pwd = self._parse_share_url(target_url)
        if not share_id:
            logger.warning(f"悟空网盘广告植入链接无效: {target_url}")
            return False

        try:
            detail = self._request_api(
                "GET",
                "/api/v1/share/info",
                params={"share_id": share_id, "pwd": pwd or ""},
            )
            data = (detail or {}).get("data") or detail or {}
            files = data.get("files") or data.get("file_list") or []
            if not files:
                return False

            first_fid = files[0].get("file_id") or files[0].get("id")
            if not first_fid:
                return False

            save_res = self._request_api(
                "POST",
                "/api/v1/share/save",
                payload={
                    "share_id": share_id,
                    "file_ids": [first_fid],
                    "target_dir_id": target_dir_id or "0",
                },
            )
            if save_res and save_res.get("code") in (0, 200, None):
                logger.info(f"悟空网盘已向目录 {target_dir_id} 成功植入自定义引流文件 (share_id={share_id})")
                return True
        except Exception as exc:
            logger.error(f"悟空网盘植入自定义广告异常: {exc}")
        return False


    def del_file(self, file_ids: Union[str, List[str]]) -> bool:
        """从个人网盘中删除文件"""
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
            "/api/v1/file/delete",
            payload={"file_ids": targets},
        )
        if res and res.get("code") in (0, 200, None):
            logger.info(f"悟空网盘文件删除成功: {targets}")
            return True

        logger.error(f"悟空网盘删除失败: {res}")
        return False
