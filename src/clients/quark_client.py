import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from src.clients.base_client import BasePanClient
from src.services.ad_filter_service import is_ad_filename

logger = logging.getLogger(__name__)


def ad_check(file_name: str) -> bool:
    return is_ad_filename(file_name)


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
        file_list = detail.get("list") or []
        fid_list = [item["fid"] for item in file_list if item.get("fid")]
        fid_token_list = [item["share_fid_token"] for item in file_list if item.get("share_fid_token")]

        if not fid_list or len(fid_list) != len(fid_token_list):
            logger.error(
                "夸克网盘分享详情缺少必要信息: fid_list=%s, share_fid_token_list=%s",
                fid_list,
                fid_token_list,
            )
            return None, None, None

        save_task_id = self.save_task_id(pwd_id, stoken, fid_list, fid_token_list, to_pdir_fid)
        if not save_task_id:
            logger.error("夸克网盘创建保存任务失败")
            return None, None, None

        save_task_result = self.task(save_task_id)
        save_as_data = ((save_task_result or {}).get("data") or {}).get("save_as") or {}
        save_as_top_fids = save_as_data.get("save_as_top_fids") or []
        if not save_as_top_fids:
            logger.error("夸克网盘保存结果中没有找到文件 ID")
            return None, None, None

        # 广告过滤与净化
        cleaned_top_fids = self._clean_ad_files_and_folders(save_as_top_fids)
        if not cleaned_top_fids:
            logger.warning("夸克网盘转存内容全为广告，已删除并终止分享")
            return None, None, None

        share_task_id = self.share_task_id(cleaned_top_fids, file_name or "夸克网盘资源")
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

        file_id_ret = cleaned_top_fids[0] if len(cleaned_top_fids) == 1 else json.dumps(cleaned_top_fids, ensure_ascii=False)
        return file_id_ret, file_name, share_link

    def get_stoken(self, pwd_id: str) -> str:
        data = self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/token",
            payload={"pwd_id": pwd_id, "passcode": ""},
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": "", "__dt": 405, "__t": generate_timestamp(13)},
        )
        if not data:
            return ""
        if data.get("status") != 200:
            msg = data.get("message") or "未知错误"
            if msg == "require login [guest]":
                logger.error("夸克网盘未登录或Cookie已失效，请更新凭证 (pwd_id=%s)", pwd_id)
            else:
                logger.error("夸克网盘获取 stoken 失败: %s (pwd_id=%s)", msg, pwd_id)
            return ""
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
        if not data:
            return {}
        if data.get("status") != 200:
            msg = data.get("message") or "未知错误"
            if msg == "require login [guest]":
                logger.error("夸克网盘未登录或Cookie已失效")
            else:
                logger.error("夸克网盘获取分享详情接口失败: %s (pwd_id=%s)", msg, pwd_id)
            return {}

        response_data = (data or {}).get("data") or {}
        file_list = response_data.get("list") or []
        if not file_list:
            logger.error("夸克网盘获取分享详情失败，列表为空: %s", pwd_id)
            return {}

        item = file_list[0]
        title = (response_data.get("share") or {}).get("title") or item.get("file_name") or "夸克网盘资源"
        return {
            "title": title,
            "file_type": item.get("file_type"),
            "fid": item.get("fid"),
            "pdir_fid": item.get("pdir_fid"),
            "share_fid_token": item.get("share_fid_token"),
            "list": file_list,
        }

    def save_task_id(
        self,
        pwd_id: str,
        stoken: str,
        first_id: Union[str, List[str]],
        share_fid_token: Union[str, List[str]],
        to_pdir_fid: str = "0",
    ) -> str:
        logger.info("夸克网盘创建保存任务")
        fid_list = first_id if isinstance(first_id, list) else [first_id]
        fid_token_list = share_fid_token if isinstance(share_fid_token, list) else [share_fid_token]
        data = self._request(
            "POST",
            "https://drive.quark.cn/1/clouddrive/share/sharepage/save",
            payload={
                "fid_list": fid_list,
                "fid_token_list": fid_token_list,
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
        if not data or data.get("status") != 200:
            msg = (data or {}).get("message") or "未知错误"
            if msg == "require login [guest]":
                logger.error("夸克网盘未登录或Cookie已失效，保存任务创建失败")
            elif "capacity limit" in str(msg).lower():
                logger.error("夸克网盘容量不足，无法保存新文件")
            else:
                logger.error("夸克网盘创建保存任务失败: %s", msg)
            return ""
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
                if not data:
                    continue
                if data.get("status") != 200:
                    msg = data.get("message") or ""
                    if msg == "require login [guest]":
                        logger.error("夸克网盘未登录或Cookie已失效")
                        return None
                    elif "capacity limit" in str(msg).lower():
                        logger.error("夸克网盘容量不足，任务失败")
                        return None
                    time.sleep(0.2)
                    continue

                task_data = data.get("data") or {}
                # 状态 2 表示任务成功完成
                if task_data.get("status") == 2 or task_data.get("save_as") or task_data.get("share_id"):
                    return data
                # 状态 3 表示任务明确失败
                if task_data.get("status") == 3:
                    task_err = task_data.get("message") or "夸克网盘异步任务处理失败"
                    logger.error("夸克网盘任务执行失败: %s", task_err)
                    return None
            except Exception as exc:
                logger.error("夸克网盘任务轮询异常: %s", exc)
            time.sleep(0.2)
        logger.warning("夸克网盘任务执行失败或超时: %s", task_id)
        return None

    def share_task_id(self, file_id: Union[str, List[str]], file_name: str) -> str:
        fid_list = file_id if isinstance(file_id, list) else [file_id]
        data = self._request(
            "POST",
            "https://drive-pc.quark.cn/1/clouddrive/share",
            payload={
                "fid_list": fid_list,
                "title": file_name,
                "url_type": 1,
                "expired_type": 1,
            },
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        )
        return ((data or {}).get("data") or {}).get("task_id", "")

    def _clean_ad_files_and_folders(self, save_as_top_fids: List[str]) -> List[str]:
        """
        扫描转存后的顶级文件/文件夹，智能检测并清理广告与引流文件。
        若文件夹内全部为广告文件，则彻底删除整个文件夹并从顶级列表中剔除。
        """
        valid_fids = []
        for fid in save_as_top_fids:
            if not fid:
                continue
            # 尝试作为文件夹列取其子文件
            try:
                sub_files = self.get_dir_file(str(fid))
            except Exception as e:
                logger.warning("夸克网盘读取目录 %s 内容失败: %s", fid, e)
                sub_files = []

            if sub_files:
                # 是文件夹且包含子内容
                total_count = len(sub_files)
                ad_fids_to_del = []
                for child in sub_files:
                    c_name = child.get("file_name", "")
                    c_fid = str(child.get("fid") or "")
                    if c_fid and is_ad_filename(c_name):
                        logger.info("夸克网盘检测到广告文件并准备清理: %s (fid=%s)", c_name, c_fid)
                        ad_fids_to_del.append(c_fid)

                if ad_fids_to_del:
                    self.del_file(ad_fids_to_del)
                    logger.info("夸克网盘已清理 %d 个广告文件", len(ad_fids_to_del))

                # 若文件夹中全部都是广告文件，或者清理后无实质有效内容
                if len(ad_fids_to_del) >= total_count:
                    logger.warning("夸克网盘目录 %s 内容全为广告，正在删除空目录...", fid)
                    self.del_file(str(fid))
                    continue

                valid_fids.append(fid)
            else:
                valid_fids.append(fid)

        return valid_fids

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

    def get_or_create_dir(self, dir_name: str, parent_dir_id: str = "0") -> str:
        """获取指定名称的文件夹 fid，若不存在则自动新建"""
        if not dir_name or dir_name.strip() in ("", "/"):
            return parent_dir_id
        clean_name = dir_name.strip().strip("/")
        try:
            files = self.get_dir_file(parent_dir_id) if parent_dir_id != "0" else self.get_all_file()
            for item in files:
                if item.get("file_name") == clean_name and item.get("file_type") == 0:
                    fid = str(item.get("fid") or "")
                    if fid:
                        logger.info("夸克网盘找到现有目录 [%s]: fid=%s", clean_name, fid)
                        return fid
            res = self.create_dir(clean_name, parent_dir_id)
            new_fid = ((res or {}).get("data") or {}).get("fid")
            if new_fid:
                logger.info("夸克网盘成功新建目录 [%s]: fid=%s", clean_name, new_fid)
                return str(new_fid)
        except Exception as exc:
            logger.error("夸克网盘获取或创建目录异常: %s", exc)
        return parent_dir_id

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
        ad_fids = []
        for file in file_list:
            if ad_check(file.get("file_name", "")):
                fid = file.get("fid")
                if fid:
                    ad_fids.append(str(fid))
        if ad_fids:
            self.del_file(ad_fids)

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

