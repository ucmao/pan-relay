import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.clients.base_client import BasePanClient
from src.services.ad_filter_service import is_ad_filename

logger = logging.getLogger(__name__)


class UcPanClient(BasePanClient):
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
            msg = (stoken_data or {}).get("message") or "未知错误"
            if msg == "require login [guest]":
                logger.error("UC 网盘未登录或Cookie已失效，请更新凭证 (pwd_id=%s)", pwd_id)
            else:
                logger.error("UC 网盘获取 stoken 失败: %s", msg)
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
            msg = (detail_data or {}).get("message") or "获取分享详情失败"
            logger.error("UC 网盘获取分享详情失败: %s", msg)
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
            msg = (save_result or {}).get("message") or "转存请求失败"
            if msg == "require login [guest]":
                logger.error("UC 网盘未登录或Cookie已失效，保存失败")
            elif "capacity limit" in str(msg).lower():
                logger.error("UC 网盘容量不足，保存失败")
            else:
                logger.error("UC 网盘转存请求失败: %s", msg)
            return None, None, None

        task_id = (save_result.get("data") or {}).get("task_id")
        task_data = self._wait_task(task_id)
        if not task_data:
            return None, None, None

        save_as_top_fids = ((task_data.get("save_as") or {}).get("save_as_top_fids")) or []
        if not save_as_top_fids:
            logger.error("UC 网盘未返回转存后的 fid")
            return None, None, None

        # 广告过滤与净化
        cleaned_top_fids = self._clean_ad_files_and_folders(save_as_top_fids)
        if not cleaned_top_fids:
            logger.warning("UC 网盘转存内容全为广告，已删除并终止分享")
            return None, None, None

        # 尝试植入个人自定义引流广告 (若已配置并启用)
        for top_fid in cleaned_top_fids:
            try:
                sub_files = self.get_dir_file(str(top_fid))
                if sub_files:
                    self.add_ad(str(top_fid))
            except Exception:
                pass

        share_task_result = self._request(
            "POST",
            "https://pc-api.uc.cn/1/clouddrive/share",
            {
                "fid_list": cleaned_top_fids,
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
        return json.dumps(cleaned_top_fids, ensure_ascii=False), title, final_url

    def get_dir_file(self, dir_id: str, page: int = 1, size: int = 100) -> List[Dict[str, Any]]:
        """遍历 UC 网盘目录文件"""
        list_data = self._request(
            "GET",
            "https://pc-api.uc.cn/1/clouddrive/file/sort",
            params={
                "pr": "UCBrowser",
                "fr": "pc",
                "pdir_fid": dir_id,
                "_page": page,
                "_size": size,
                "_fetch_total": 1,
                "_sort": "file_type:asc,updated_at:desc",
            },
        )
        return ((list_data or {}).get("data") or {}).get("list") or []

    def _clean_ad_files_and_folders(self, save_as_top_fids: List[str]) -> List[str]:
        """
        扫描 UC 网盘转存后的顶级文件/文件夹，智能检测并清理广告引流文件。
        若文件夹内全部为广告文件，则彻底删除整个文件夹并从顶级列表中剔除。
        """
        valid_fids = []
        for fid in save_as_top_fids:
            if not fid:
                continue
            try:
                sub_files = self.get_dir_file(str(fid))
            except Exception as e:
                logger.warning("UC 网盘读取目录 %s 内容失败: %s", fid, e)
                sub_files = []

            if sub_files:
                total_count = len(sub_files)
                ad_fids_to_del = []
                for child in sub_files:
                    c_name = child.get("file_name", "")
                    c_fid = str(child.get("fid") or "")
                    if c_fid and is_ad_filename(c_name):
                        logger.info("UC 网盘检测到广告文件并准备清理: %s (fid=%s)", c_name, c_fid)
                        ad_fids_to_del.append(c_fid)

                if ad_fids_to_del:
                    self.del_file(ad_fids_to_del)
                    logger.info("UC 网盘已清理 %d 个广告文件", len(ad_fids_to_del))

                if len(ad_fids_to_del) >= total_count:
                    logger.warning("UC 网盘目录 %s 内容全为广告，正在删除空目录...", fid)
                    self.del_file([str(fid)])
                    continue

                valid_fids.append(fid)
            else:
                valid_fids.append(fid)

        return valid_fids

    def add_ad(self, dir_id: str, ad_share_url: Optional[str] = None) -> bool:
        """
        向 UC 网盘指定的转存目录植入个人自定义引流/广告文件。
        """
        target_url = (ad_share_url or "").strip()
        if not target_url:
            from src.services.system_config_service import get_custom_ad_injection_config
            cfg = get_custom_ad_injection_config()
            if not cfg.get("enabled"):
                return False
            target_url = cfg.get("ad_share_url", "").strip()

        if not target_url:
            return False

        pwd_id = self._extract_pwd_id(target_url)
        if not pwd_id:
            logger.warning("UC 网盘广告植入链接无效: %s", target_url)
            return False

        try:
            stoken_data = self._request(
                "POST",
                "https://pc-api.uc.cn/1/clouddrive/share/sharepage/v2/detail",
                {"passcode": "", "pwd_id": pwd_id},
                params={"pr": "UCBrowser", "fr": "pc"},
            )
            stoken = ((stoken_data.get("data") or {}).get("token_info") or {}).get("stoken", "")
            if not stoken:
                return False
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
                    "_size": "50",
                    "_fetch_total": "1",
                    "_sort": "file_type:asc,updated_at:desc",
                },
            )
            detail = (detail_data or {}).get("data") or {}
            file_list = detail.get("list") or []
            if not file_list:
                return False
            first_item = file_list[0]
            fid = first_item.get("fid")
            fid_token = first_item.get("share_fid_token")
            if not fid or not fid_token:
                return False

            save_res = self._request(
                "POST",
                "https://pc-api.uc.cn/1/clouddrive/share/sharepage/save",
                {
                    "fid_list": [fid],
                    "fid_token_list": [fid_token],
                    "to_pdir_fid": dir_id,
                    "pwd_id": pwd_id,
                    "stoken": stoken,
                    "pdir_fid": "0",
                    "scene": "link",
                },
                params={"entry": "update_share", "pr": "UCBrowser", "fr": "pc"},
            )
            task_id = ((save_res or {}).get("data") or {}).get("task_id")
            if task_id:
                self._wait_task(task_id, retries=5)
                logger.info("UC 网盘已向目录 %s 成功植入自定义引流文件 (pwd_id=%s)", dir_id, pwd_id)
                return True
        except Exception as exc:
            logger.error("UC 网盘植入自定义广告异常: %s", exc)
        return False

    def get_or_create_dir(self, dir_name: str, parent_dir_id: str = "0") -> str:
        """获取指定名称的文件夹 fid，若不存在则自动新建"""
        if not dir_name or dir_name.strip() in ("", "/"):
            return parent_dir_id
        clean_name = dir_name.strip().strip("/")
        try:
            list_data = self._request(
                "GET",
                "https://pc-api.uc.cn/1/clouddrive/file/sort",
                params={
                    "pr": "UCBrowser",
                    "fr": "pc",
                    "pdir_fid": parent_dir_id,
                    "_page": 1,
                    "_size": 50,
                    "_fetch_total": 1,
                    "_sort": "file_type:asc,updated_at:desc",
                },
            )
            file_list = ((list_data or {}).get("data") or {}).get("list") or []
            for item in file_list:
                if item.get("file_name") == clean_name and item.get("file_type") == 0:
                    fid = str(item.get("fid") or "")
                    if fid:
                        logger.info("UC 网盘找到现有目录 [%s]: fid=%s", clean_name, fid)
                        return fid

            create_data = self._request(
                "POST",
                "https://pc-api.uc.cn/1/clouddrive/file",
                {
                    "pdir_fid": parent_dir_id,
                    "file_name": clean_name,
                    "dir_path": "",
                    "dir_init_lock": False,
                },
                params={"pr": "UCBrowser", "fr": "pc"},
            )
            new_fid = ((create_data or {}).get("data") or {}).get("fid")
            if new_fid:
                logger.info("UC 网盘成功新建目录 [%s]: fid=%s", clean_name, new_fid)
                return str(new_fid)
        except Exception as exc:
            logger.error("UC 网盘获取或创建目录异常: %s", exc)
        return parent_dir_id

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
            msg = result.get("message") or ""
            if msg == "capacity limit[{0}]" or "capacity limit" in str(msg).lower():
                logger.error("UC 网盘容量不足，转存任务失败")
                return None
            if msg == "require login [guest]":
                logger.error("UC 网盘未登录或Cookie已失效")
                return None
            if result.get("status") != 200:
                time.sleep(0.2)
                continue
            data = result.get("data") or {}
            if data.get("status") == 2 or data.get("save_as") or data.get("share_id"):
                return data
            if data.get("status") == 3:
                logger.error("UC 网盘异步任务执行失败: %s", data.get("message") or "任务失败")
                return None
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
