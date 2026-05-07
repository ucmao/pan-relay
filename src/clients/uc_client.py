import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class UcDrive:
    def __init__(self, cookie: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json;charset=UTF-8",
                "Referer": "https://drive.uc.cn/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "cookie": cookie,
            }
        )

    def store(
        self, share_url: str, to_dir: str = "0"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        pwd_id = self._extract_pwd_id(share_url)
        if not pwd_id:
            logger.error("UC 网盘链接解析失败: %s", share_url)
            return None, None, None

        stoken_data = self._request(
            "POST",
            "https://pc-api.uc.cn/1/clouddrive/share/sharepage/v2/detail",
            {"passcode": "", "pwd_id": pwd_id},
            params={"pr": "UCBrowser", "fr": "pc"},
        )
        if not stoken_data or stoken_data.get("status") != 200:
            logger.error("UC 网盘获取 stoken 失败: %s", stoken_data)
            return None, None, None

        stoken = ((stoken_data.get("data") or {}).get("token_info") or {}).get("stoken", "")
        if not stoken:
            logger.error("UC 网盘响应中缺少 stoken")
            return None, None, None
        stoken = stoken.replace(" ", "+")

        detail_data = self._request(
            "GET",
            "https://pc-api.uc.cn/1/clouddrive/share/sharepage/detail",
            params={
                "pr": "UCBrowser",
                "fr": "pc",
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": "0",
                "force": "0",
                "_page": "1",
                "_size": "100",
                "_fetch_banner": "1",
                "_fetch_share": "1",
                "_fetch_total": "1",
                "_sort": "file_type:asc,updated_at:desc",
            },
        )
        if not detail_data or detail_data.get("status") != 200:
            logger.error("UC 网盘获取分享详情失败: %s", detail_data)
            return None, None, None

        detail = detail_data.get("data") or {}
        file_list = detail.get("list") or []
        if not file_list:
            logger.error("UC 网盘分享详情为空")
            return None, None, None

        fid_list = [item["fid"] for item in file_list if item.get("fid")]
        fid_token_list = [item["share_fid_token"] for item in file_list if item.get("share_fid_token")]
        title = (detail.get("share") or {}).get("title") or file_list[0].get("file_name") or "UC网盘资源"
        if not fid_list or len(fid_list) != len(fid_token_list):
            logger.error("UC 网盘 fid 信息不完整")
            return None, None, None

        save_result = self._request(
            "POST",
            "https://pc-api.uc.cn/1/clouddrive/share/sharepage/save",
            {
                "fid_list": fid_list,
                "fid_token_list": fid_token_list,
                "to_pdir_fid": to_dir or "0",
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": "0",
                "scene": "link",
            },
            params={"entry": "update_share", "pr": "UCBrowser", "fr": "pc"},
        )
        if not save_result or save_result.get("status") != 200:
            logger.error("UC 网盘转存请求失败: %s", save_result)
            return None, None, None

        task_id = (save_result.get("data") or {}).get("task_id")
        task_data = self._wait_task(task_id)
        if not task_data:
            return None, None, None

        save_as_top_fids = ((task_data.get("save_as") or {}).get("save_as_top_fids")) or []
        if not save_as_top_fids:
            logger.error("UC 网盘未返回转存后的 fid")
            return None, None, None

        share_task_result = self._request(
            "POST",
            "https://pc-api.uc.cn/1/clouddrive/share",
            {
                "fid_list": save_as_top_fids,
                "expired_type": 1,
                "title": title,
                "url_type": 1,
            },
            params={"pr": "UCBrowser", "fr": "pc"},
        )
        if not share_task_result or share_task_result.get("status") != 200:
            logger.error("UC 网盘创建分享任务失败: %s", share_task_result)
            return None, None, None

        share_task_id = (share_task_result.get("data") or {}).get("task_id")
        share_task_data = self._wait_task(share_task_id)
        if not share_task_data:
            return None, None, None

        share_id = share_task_data.get("share_id")
        if not share_id:
            logger.error("UC 网盘未返回 share_id")
            return None, None, None

        password_result = self._request(
            "POST",
            "https://pc-api.uc.cn/1/clouddrive/share/password",
            {"share_id": share_id},
            params={"pr": "UCBrowser", "fr": "pc"},
        )
        if not password_result or password_result.get("status") != 200:
            logger.error("UC 网盘获取分享链接失败: %s", password_result)
            return None, None, None

        share_data = password_result.get("data") or {}
        share_url_new = share_data.get("share_url")
        pass_code = share_data.get("pass_code")
        if not share_url_new:
            return None, None, None

        final_url = f"{share_url_new}?pwd={pass_code}" if pass_code else share_url_new
        return json.dumps(save_as_top_fids, ensure_ascii=False), title, final_url

    def del_file(self, file_ids: List[str]) -> bool:
        if not file_ids:
            return False

        result = self._request(
            "POST",
            "https://pc-api.uc.cn/1/clouddrive/file/delete",
            {"action_type": 2, "exclude_fids": [], "filelist": file_ids},
            params={"pr": "UCBrowser", "fr": "pc"},
        )
        return bool(result) and result.get("status") == 200

    def _wait_task(self, task_id: str, retries: int = 50) -> Optional[Dict[str, Any]]:
        if not task_id:
            return None

        for retry_index in range(retries):
            result = self._request(
                "GET",
                "https://pc-api.uc.cn/1/clouddrive/task",
                params={
                    "pr": "UCBrowser",
                    "fr": "pc",
                    "task_id": task_id,
                    "retry_index": retry_index,
                },
            )
            if not result:
                continue
            if result.get("message") == "capacity limit[{0}]":
                logger.error("UC 网盘容量不足")
                return None
            if result.get("status") != 200:
                time.sleep(0.2)
                continue
            data = result.get("data") or {}
            if data.get("status") == 2:
                return data
            time.sleep(0.2)

        logger.error("UC 网盘任务轮询超时: %s", task_id)
        return None

    def _request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        response = self.session.request(
            method,
            url,
            json=payload if payload is not None else None,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_pwd_id(url: str) -> str:
        match = re.search(r"/s/([a-zA-Z0-9]+)", url)
        if match:
            return match.group(1)
        return ""
