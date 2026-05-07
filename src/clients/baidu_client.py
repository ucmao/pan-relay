import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class Baidu:
    def __init__(self, credential: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Host": "pan.baidu.com",
                "Connection": "keep-alive",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/114.0.0.0 Safari/537.36"
                ),
                "Referer": "https://pan.baidu.com/disk/home",
                "Cookie": credential,
            }
        )
        self.bdstoken = self._get_bdstoken()

    def store(
        self, share_url: str, to_dir: str = "/"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        try:
            surl, pwd = self._parse_share_url(share_url)
            if not surl:
                logger.error("百度网盘链接解析失败: %s", share_url)
                return None, None, None

            if pwd and not self._verify_pwd(surl, pwd):
                logger.error("百度网盘提取码验证失败: surl=%s", surl)
                return None, None, None

            share_info = self._get_share_page_info(surl)
            if not share_info:
                logger.error("百度网盘无法获取分享页面详情")
                return None, None, None

            share_id, from_uk, fs_id_list, file_names = share_info
            target_fs_id = fs_id_list[0]
            file_name = file_names[0]

            if not self._transfer_file(share_id, from_uk, [target_fs_id], to_dir):
                logger.error("百度网盘转存失败: %s", file_name)
                return None, None, None

            full_path = f"{to_dir.rstrip('/')}/{file_name}" if to_dir != "/" else f"/{file_name}"
            new_fs_id = self._get_file_id_by_path(full_path)
            if not new_fs_id:
                logger.error("百度网盘未找到转存后的文件 ID: %s", full_path)
                return full_path, file_name, ""

            new_share_link = self._create_share(new_fs_id)
            if not new_share_link:
                logger.error("百度网盘创建新分享失败: %s", full_path)
                return full_path, file_name, ""

            return full_path, file_name, new_share_link
        except Exception as exc:
            logger.exception("百度网盘 store 异常: %s", exc)
            return None, None, None

    def del_file(self, file_path_list: List[str]) -> bool:
        logger.info("正在删除百度网盘文件: %s", file_path_list)
        params = {
            "async": 2,
            "onnest": "fail",
            "opera": "delete",
            "bdstoken": self.bdstoken,
            "newVerify": 1,
            "clienttype": 0,
            "web": 1,
            "app_id": 250528,
        }
        payload = {"filelist": self._to_json(file_path_list)}

        try:
            data = self._request(
                "POST",
                "https://pan.baidu.com/api/filemanager",
                params=params,
                data=payload,
            )
            errno = data.get("errno")
            if errno == 0:
                logger.info("百度网盘删除请求已提交: task=%s", data.get("taskid"))
                return True
            if errno == 2:
                logger.warning("百度网盘文件不存在，按删除成功处理: %s", file_path_list)
                return True
            logger.error("百度网盘删除失败: %s", data)
            return False
        except Exception as exc:
            logger.error("百度网盘删除请求异常: %s", exc)
            return False

    def _get_bdstoken(self) -> str:
        try:
            data = self._request(
                "GET",
                "https://pan.baidu.com/api/gettemplatevariable?fields=[%22bdstoken%22]",
            )
            return (data.get("result") or {}).get("bdstoken", "")
        except Exception:
            return ""

    def _parse_share_url(self, url: str) -> Tuple[str, str]:
        surl_match = re.search(r"s/1([a-zA-Z0-9-_]+)", url) or re.search(
            r"surl=([a-zA-Z0-9-_]+)", url
        )
        surl = surl_match.group(1) if surl_match else ""
        if not surl and "baidu.com/s/" in url:
            candidate = url.split("baidu.com/s/")[-1].split(" ")[0]
            surl = candidate[1:] if candidate.startswith("1") else candidate

        pwd_match = re.search(r"[?&]pwd=([a-zA-Z0-9]{4})", url)
        if pwd_match:
            return surl, pwd_match.group(1)

        code_match = re.search(r"提取码[:： ]*([a-zA-Z0-9]{4})", url)
        if code_match:
            return surl, code_match.group(1)

        return surl, ""

    def _verify_pwd(self, surl: str, pwd: str) -> bool:
        params = {
            "surl": surl,
            "t": int(time.time() * 1000),
            "bdstoken": self.bdstoken,
            "channel": "chunlei",
            "clienttype": 0,
            "web": 1,
        }
        payload = {"pwd": pwd, "vcode": "", "vcode_str": ""}
        try:
            data = self._request(
                "POST",
                "https://pan.baidu.com/share/verify",
                params=params,
                data=payload,
            )
            if data.get("errno") == 0:
                return True
            logger.warning("百度网盘提取码校验失败: %s", data)
            return False
        except Exception as exc:
            logger.error("百度网盘提取码验证异常: %s", exc)
            return False

    def _get_share_page_info(
        self, surl: str
    ) -> Optional[Tuple[str, str, List[str], List[str]]]:
        try:
            response = self.session.get(f"https://pan.baidu.com/s/1{surl}", timeout=20)
            response.raise_for_status()
            html = response.text

            share_id = re.search(r'"shareid":(\d+),', html)
            share_uk = re.search(r'"share_uk":"?(\d+)"?,', html)
            fs_ids = list(dict.fromkeys(re.findall(r'"fs_id":(\d+),', html)))
            file_names = list(dict.fromkeys(re.findall(r'"server_filename":"(.+?)",', html)))

            if share_id and share_uk and fs_ids and file_names:
                return share_id.group(1), share_uk.group(1), fs_ids, file_names
            return None
        except Exception as exc:
            logger.error("百度网盘解析分享页面异常: %s", exc)
            return None

    def _transfer_file(self, share_id: str, from_uk: str, fs_id_list: List[str], to_path: str) -> bool:
        params = {
            "shareid": share_id,
            "from": from_uk,
            "ondup": "newcopy",
            "async": 1,
            "bdstoken": self.bdstoken,
            "channel": "chunlei",
            "clienttype": 0,
            "web": 1,
            "app_id": 250528,
        }
        payload = {
            "fsidlist": f"[{','.join(str(item) for item in fs_id_list)}]",
            "path": to_path,
        }
        try:
            data = self._request(
                "POST",
                "https://pan.baidu.com/share/transfer",
                params=params,
                data=payload,
            )
            if data.get("errno") == 0:
                return True
            logger.error("百度网盘转存接口返回错误: %s", data)
            return False
        except Exception as exc:
            logger.error("百度网盘转存请求异常: %s", exc)
            return False

    def _get_file_id_by_path(self, path: str) -> Optional[int]:
        if path == "/":
            return None

        normalized_path = path[:-1] if path.endswith("/") else path
        dir_path, filename = normalized_path.rsplit("/", 1)
        dir_path = dir_path or "/"

        params = {
            "dir": dir_path,
            "bdstoken": self.bdstoken,
            "clienttype": 0,
            "web": 1,
            "page": 1,
            "num": 1000,
            "order": "time",
            "desc": 1,
        }
        try:
            data = self._request("GET", "https://pan.baidu.com/api/list", params=params)
            if data.get("errno") != 0:
                return None
            for item in data.get("list", []):
                if item.get("server_filename") == filename:
                    return item.get("fs_id")
            return None
        except Exception as exc:
            logger.error("百度网盘按路径查询文件 ID 异常: %s", exc)
            return None

    def _create_share(self, fs_id: int) -> Optional[str]:
        params = {
            "bdstoken": self.bdstoken,
            "channel": "chunlei",
            "clienttype": 0,
            "web": 1,
            "app_id": 250528,
        }
        pwd = "".join(random.sample("0123456789abcdefghijklmnopqrstuvwxyz", 4))
        payload = {
            "fid_list": f"[{fs_id}]",
            "schannel": 4,
            "channel_list": "[]",
            "period": 0,
            "pwd": pwd,
        }

        try:
            data = self._request(
                "POST",
                "https://pan.baidu.com/share/set",
                params=params,
                data=payload,
            )
            if data.get("errno") == 0 and data.get("shorturl"):
                return f"{data['shorturl']}?pwd={pwd}"
            logger.error("百度网盘创建分享失败: %s", data)
            return None
        except Exception as exc:
            logger.error("百度网盘创建分享请求异常: %s", exc)
            return None

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = self.session.request(method, url, params=params, data=data, timeout=20)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _to_json(value: Any) -> str:
        import json

        return json.dumps(value, ensure_ascii=False)
