import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from src.clients.base_client import BasePanClient

logger = logging.getLogger(__name__)


def ad_check(file_name: str) -> bool:
    ad_keywords = ["公众号", "备用", "防失联", "防封", "更新", "关注", "发布页"]
    file_name_lower = file_name.lower()
    return any(keyword in file_name_lower for keyword in ad_keywords)


def generate_timestamp(length: int) -> int:
    timestamps = str(time.time() * 1000)
    return int(timestamps[0:length])


class QuarkPanClient(BasePanClient):
    ad_pwd_id = "0df525db2bd0"

    def __init__(self, credential: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json; charset=utf-8",
                "sec-ch-ua-mobile": "?0",
                "user-agent": (
                    "Mozilla/5.0 (Linux; Android 10; Pixel 4) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.120 Mobile Safari/537.36"
                ),
                "sec-ch-ua-platform": '"Windows"',
                "origin": "https://pan.quark.cn",
                "sec-fetch-site": "same-site",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty",
                "referer": "https://pan.quark.cn/",
                "accept-encoding": "gzip, deflate, br",
                "accept-language": "zh-CN,zh;q=0.9",
                "cookie": credential,
            }
        )

    def store(
        self, share_url: str, to_pdir_fid: str = "0"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        pwd_id = self._extract_pwd_id(share_url)
        if not pwd_id:
            logger.error("夸克网盘链接解析失败: %s", share_url)
            return None, None, None

        stoken = self.get_stoken(pwd_id)
        if not stoken:
            logger.error("夸克网盘获取 stoken 失败: %s", pwd_id)
            return None, None, None

        detail = self.detail(pwd_id, stoken)
        if not detail:
            logger.error("夸克网盘获取分享详情失败: %s", pwd_id)
            return None, None, None

        file_name = detail.get("title")
        first_id = detail.get("fid")
        share_fid_token = detail.get("share_fid_token")
        if not all([first_id, share_fid_token]):
            logger.error(
                "夸克网盘分享详情缺少必要信息: fid=%s, share_fid_token=%s",
                first_id,
                share_fid_token,
            )
            return None, None, None

        save_task_id = self.save_task_id(pwd_id, stoken, first_id, share_fid_token, to_pdir_fid)
        if not save_task_id:
            logger.error("夸克网盘创建保存任务失败")
            return None, None, None

        save_task_result = self.task(save_task_id)
        save_as_data = ((save_task_result or {}).get("data") or {}).get("save_as") or {}
        save_as_top_fids = save_as_data.get("save_as_top_fids") or []
        if not save_as_top_fids:
            logger.error("夸克网盘保存结果中没有找到文件 ID")
            return None, None, None

        file_id = save_as_top_fids[0]
        share_task_id = self.share_task_id(file_id, file_name or "夸克网盘资源")
        if not share_task_id:
            logger.error("夸克网盘创建分享任务失败")
            return None, None, None

        share_task_result = self.task(share_task_id)
        share_id = ((share_task_result or {}).get("data") or {}).get("share_id")
        if not share_id:
            logger.error("夸克网盘分享结果中没有找到 share_id")
            return None, None, None

        share_link = self.get_share_link(share_id)
        if not share_link:
            logger.error("夸克网盘获取分享链接失败")
            return None, None, None

        return file_id, file_name, share_link

    def get_stoken(self, pwd_id: str) -> str:
        data = self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/token",
            payload={"pwd_id": pwd_id, "passcode": ""},
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": "", "__dt": 405, "__t": generate_timestamp(13)},
        )
        return ((data or {}).get("data") or {}).get("stoken", "")

    def detail(self, pwd_id: str, stoken: str) -> Dict[str, Any]:
        data = self._request(
            "GET",
            "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/detail",
            params={
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": 0,
                "_page": 1,
                "_size": "50",
            },
        )
        response_data = (data or {}).get("data") or {}
        file_list = response_data.get("list") or []
        if not file_list:
            logger.error("夸克网盘获取分享详情失败，列表为空: %s", pwd_id)
            return {}

        item = file_list[0]
        return {
            "title": item.get("file_name"),
            "file_type": item.get("file_type"),
            "fid": item.get("fid"),
            "pdir_fid": item.get("pdir_fid"),
            "share_fid_token": item.get("share_fid_token"),
        }

    def save_task_id(
        self,
        pwd_id: str,
        stoken: str,
        first_id: str,
        share_fid_token: str,
        to_pdir_fid: str = "0",
    ) -> str:
        logger.info("夸克网盘创建保存任务")
        data = self._request(
            "POST",
            "https://drive.quark.cn/1/clouddrive/share/sharepage/save",
            payload={
                "fid_list": [first_id],
                "fid_token_list": [share_fid_token],
                "to_pdir_fid": to_pdir_fid,
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": "0",
                "scene": "link",
            },
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "__dt": int(random.uniform(1, 5) * 60 * 1000),
                "__t": generate_timestamp(13),
            },
        )
        return ((data or {}).get("data") or {}).get("task_id", "")

    def task(self, task_id: str, retries: int = 10) -> Optional[Dict[str, Any]]:
        logger.info("夸克网盘轮询任务: %s", task_id)
        for retry_index in range(retries):
            try:
                data = self._request(
                    "GET",
                    "https://drive-pc.quark.cn/1/clouddrive/task",
                    params={
                        "pr": "ucpro",
                        "fr": "pc",
                        "uc_param_str": "",
                        "task_id": task_id,
                        "retry_index": retry_index,
                        "__dt": 21192,
                        "__t": generate_timestamp(13),
                    },
                )
                if ((data or {}).get("data") or {}).get("status"):
                    return data
            except Exception as exc:
                logger.error("夸克网盘任务轮询异常: %s", exc)
            time.sleep(0.2)
        logger.warning("夸克网盘任务执行失败或超时: %s", task_id)
        return None

    def share_task_id(self, file_id: str, file_name: str) -> str:
        data = self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/share",
            payload={
                "fid_list": [file_id],
                "title": file_name,
                "url_type": 1,
                "expired_type": 1,
            },
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        )
        return ((data or {}).get("data") or {}).get("task_id", "")

    def get_share_link(self, share_id: str) -> str:
        data = self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/share/password",
            payload={"share_id": share_id},
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        )
        return ((data or {}).get("data") or {}).get("share_url", "")

    def get_all_file(self) -> List[Dict[str, Any]]:
        logger.info("夸克网盘获取所有文件")
        data = self._request(
            "GET",
            "https://drive-pc.quark.cn/1/clouddrive/file/sort",
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "pdir_fid": 0,
                "_page": 1,
                "_size": 50,
                "_fetch_total": 1,
                "_fetch_sub_dirs": 0,
                "_sort": "file_type:asc,updated_at:desc",
            },
        )
        return ((data or {}).get("data") or {}).get("list", [])

    def get_dir_file(self, dir_id: str, page: int = 1, size: int = 100) -> List[Dict[str, Any]]:
        logger.info("夸克网盘遍历父文件夹: %s", dir_id)
        data = self._request(
            "GET",
            "https://drive-pc.quark.cn/1/clouddrive/file/sort",
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "pdir_fid": dir_id,
                "_page": page,
                "_size": size,
                "_fetch_total": 1,
                "_fetch_sub_dirs": 0,
                "_sort": "file_type:asc,updated_at:desc",
            },
        )
        return ((data or {}).get("data") or {}).get("list", [])

    def create_dir(self, dir_name: str, parent_dir_id: str = "0") -> Dict[str, Any]:
        logger.info("夸克网盘创建目录: %s", dir_name)
        return self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/file",
            payload={
                "pdir_fid": parent_dir_id,
                "file_name": dir_name,
                "dir_path": "",
                "dir_init_lock": False,
            },
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        )

    def rename_dir(self, dir_id: str, new_name: str) -> Dict[str, Any]:
        logger.info("夸克网盘重命名目录: %s -> %s", dir_id, new_name)
        return self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/file/rename",
            payload={"fid": dir_id, "file_name": new_name},
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        )

    def move_file(self, file_fid: str, to_pdir_fid: str) -> Dict[str, Any]:
        logger.info("夸克网盘移动文件: %s -> %s", file_fid, to_pdir_fid)
        return self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/file/move",
            payload={
                "action_type": 1,
                "exclude_fids": [],
                "filelist": [file_fid],
                "to_pdir_fid": to_pdir_fid,
            },
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        )

    def del_file(self, file_ids: Union[str, List[str]]) -> bool:
        logger.info("夸克网盘删除文件: %s", file_ids)
        normalized_ids = file_ids if isinstance(file_ids, list) else [file_ids]
        data = self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/file/delete",
            payload={"action_type": 2, "filelist": normalized_ids, "exclude_fids": []},
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        )
        task_id = ((data or {}).get("data") or {}).get("task_id", "")
        if not task_id:
            return False
        task_result = self.task(task_id)
        return bool(task_result)

    def del_ad_file(self, file_list: List[Dict[str, Any]]) -> None:
        logger.info("夸克网盘删除可能存在广告的文件")
        for file in file_list:
            if ad_check(file.get("file_name", "")):
                self.del_file(file.get("fid"))

    def add_ad(self, dir_id: str) -> None:
        logger.info("夸克网盘添加个人自定义广告")
        pwd_id = self.ad_pwd_id
        stoken = self.get_stoken(pwd_id)
        detail = self.detail(pwd_id, stoken)
        first_id, share_fid_token = detail.get("fid"), detail.get("share_fid_token")
        task_id = self.save_task_id(pwd_id, stoken, first_id, share_fid_token, dir_id)
        self.task(task_id, 1)
        logger.info("夸克网盘广告移植成功")

    def search_file(self, file_name: str) -> List[Dict[str, Any]]:
        logger.info("夸克网盘搜索文件: %s", file_name)
        data = self._request(
            "GET",
            "https://drive-pc.quark.cn/1/clouddrive/file/search",
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "_page": 1,
                "_size": 50,
                "_fetch_total": 1,
                "_sort": "file_type:desc,updated_at:desc",
                "_is_hl": 1,
                "q": file_name,
            },
        )
        return ((data or {}).get("data") or {}).get("list", [])

    def _request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        match = re.search(r"/s/(\w+)", url)
        return match.group(1) if match else ""

