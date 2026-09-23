import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from src.clients.base_client import BasePanClient

logger = logging.getLogger(__name__)

# 全局 Access Token 缓存
# 结构: {refresh_token: {"access_token": str, "expires_at": float}}
_GUANGYA_ACCESS_TOKEN_CACHE: Dict[str, Dict[str, Any]] = {}


class GuangyaPanClient(BasePanClient):
    """
    光鸭云盘客户端实现 (guangyapan.com)
    提供转存 (store)、创建新分享与文件删除 (del_file) 功能。
    """
    api_base = "https://api.guangyapan.com"
    client_id = "guangya_web"

    def __init__(self, credential: Union[str, Dict[str, Any]]) -> None:
        self.raw_credential = credential
        self.access_token = ""
        self.refresh_token = ""

        if isinstance(credential, dict):
            self.access_token = str(credential.get("access_token") or "").strip()
            self.refresh_token = str(credential.get("refresh_token") or "").strip()
        elif isinstance(credential, str):
            clean_cred = credential.strip()
            if clean_cred.startswith("{") and clean_cred.endswith("}"):
                try:
                    data = json.loads(clean_cred)
                    if isinstance(data, dict):
                        self.access_token = str(data.get("access_token") or "").strip()
                        self.refresh_token = str(data.get("refresh_token") or "").strip()
                except Exception:
                    self.access_token = clean_cred
            else:
                self.access_token = clean_cred

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://www.guangyapan.com",
            "Referer": "https://www.guangyapan.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
        })

    def _get_access_token(self) -> str:
        if self.access_token and not self.refresh_token:
            return self.access_token

        if self.refresh_token:
            cached = _GUANGYA_ACCESS_TOKEN_CACHE.get(self.refresh_token)
            if cached and cached.get("expires_at", 0) > time.time() + 60:
                return cached.get("access_token", "")

            # 刷新 Token
            try:
                resp = self.session.post(
                    f"{self.api_base}/drive/v1/auth/token",
                    json={"grant_type": "refresh_token", "refresh_token": self.refresh_token},
                    timeout=10,
                )
                if resp.status_code == 200:
                    res_json = resp.json()
                    new_token = res_json.get("access_token") or res_json.get("token")
                    expires_in = int(res_json.get("expires_in", 3600))
                    if new_token:
                        _GUANGYA_ACCESS_TOKEN_CACHE[self.refresh_token] = {
                            "access_token": new_token,
                            "expires_at": time.time() + expires_in,
                        }
                        self.access_token = new_token
                        return new_token
            except Exception as e:
                logger.warning(f"光鸭云盘刷新 access_token 失败: {e}")

        return self.access_token

    def _request_api(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Optional[Dict[str, Any]]:
        token = self._get_access_token()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{self.api_base}{path}" if path.startswith("/") else path
        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                logger.error(f"光鸭云盘 API 请求失败 [{resp.status_code}]: {resp.text}")
                return None
        except Exception as exc:
            logger.error(f"光鸭云盘 API 请求异常: {exc}")
            return None

    def _parse_share_url(self, share_url: str) -> Tuple[Optional[str], Optional[str]]:
        """从分享 URL 中解析出 share_id 与提取码"""
        if not share_url:
            return None, None
        
        match = re.search(r"guangyapan\.com/s/([a-zA-Z0-9_-]+)", share_url, re.IGNORECASE)
        if not match:
            return None, None
        
        share_id = match.group(1)
        pwd_match = re.search(r"(?:[?&]pwd=|提取码[:：=\s]*|密码[:：=\s]*)([a-zA-Z0-9]{4,6})", share_url, re.IGNORECASE)
        pwd = pwd_match.group(1) if pwd_match else None
        return share_id, pwd

    def store(
        self, share_url: str, to_pdir_path: str = "/"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        转存光鸭云盘分享文件并在个人网盘中生成新分享链接。
        """
        share_id, pwd = self._parse_share_url(share_url)
        if not share_id:
            logger.error(f"光鸭云盘分享链接解析失败: {share_url}")
            return None, None, None

        # 1. 获取分享文件信息
        detail = self._request_api(
            "GET",
            "/drive/v1/share",
            params={"share_id": share_id, "pass_code": pwd or ""},
        )
        if not detail or detail.get("error_code") or detail.get("code", 0) not in (0, 200, None):
            logger.error(f"光鸭云盘获取分享详情失败: {detail}")
            return None, None, None

        files = detail.get("files") or detail.get("data", {}).get("files", [])
        if not files:
            logger.error("光鸭云盘分享内容为空或已被取消分享")
            return None, None, None

        file_ids = [f["id"] for f in files if "id" in f]
        file_name = files[0].get("name", "光鸭分享文件")
        pass_code_token = detail.get("pass_code_token") or detail.get("data", {}).get("pass_code_token", "")

        # 2. 执行转存
        restore_res = self._request_api(
            "POST",
            "/drive/v1/share/restore",
            payload={
                "share_id": share_id,
                "pass_code_token": pass_code_token,
                "file_ids": file_ids,
                "parent_id": to_pdir_path if to_pdir_path not in ("/", "") else "0",
            },
        )
        if not restore_res:
            logger.error("光鸭云盘转存请求无响应")
            return None, None, None

        saved_file_ids = (
            restore_res.get("file_ids")
            or restore_res.get("data", {}).get("file_ids")
            or file_ids
        )

        # 3. 创建新分享链接
        share_res = self._request_api(
            "POST",
            "/drive/v1/shares",
            payload={
                "file_ids": saved_file_ids,
                "title": file_name,
                "expiration": 0,  # 永久有效
            },
        )
        new_share_url = None
        if share_res:
            share_info = share_res.get("data") or share_res
            new_share_url = share_info.get("share_url") or share_info.get("url")
            share_code = share_info.get("share_id") or share_info.get("id")
            pass_code = share_info.get("pass_code") or share_info.get("password")
            if not new_share_url and share_code:
                new_share_url = f"https://www.guangyapan.com/s/{share_code}"
                if pass_code:
                    new_share_url += f"?pwd={pass_code}"

        saved_file_id_str = json.dumps(saved_file_ids, ensure_ascii=False) if isinstance(saved_file_ids, list) else str(saved_file_ids)
        return saved_file_id_str, file_name, new_share_url

    def del_file(self, file_ids: Union[str, List[str]]) -> bool:
        """从个人光鸭云盘中批量删除指定文件或目录"""
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
            "/drive/v1/files/delete",
            payload={"file_ids": targets},
        )
        if res and res.get("code", 0) in (0, 200, None) and not res.get("error_code"):
            logger.info(f"光鸭云盘文件删除成功: {targets}")
            return True

        logger.error(f"光鸭云盘删除文件失败: {res}")
        return False
