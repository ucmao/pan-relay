import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.clients.base_client import BasePanClient
from src.utils.netdisk_utils import extract_password_from_url

logger = logging.getLogger(__name__)

BAIDU_ERRNO_MAP: Dict[int, str] = {
    -1: "链接失效、缺少提取码或触发访问频繁安全风控",
    -4: "无效登录，请重新登录账号",
    -6: "Cookie已失效，请使用浏览器无痕模式重新获取",
    -7: "转存目录名包含非法字符（不能包含 < > | * ? \\ :）",
    -8: "转存失败，目录中已有同名文件或文件夹存在",
    -9: "链接不存在或提取码错误",
    -10: "百度网盘容量不足",
    -12: "提取码错误",
    -62: "链接访问次数过多，请稍后再试",
    0: "操作成功",
    2: "目标目录不存在或文件不存在",
    4: "目录中存在同名文件",
    12: "转存文件数超过网盘单次限制",
    20: "百度网盘容量不足",
    105: "所访问的分享页面不存在",
    115: "该文件涉及敏感违规，禁止分享",
}


def get_baidu_errno_message(errno: Any) -> str:
    """获取百度网盘 errno 对应的中文诊断信息"""
    try:
        code = int(errno)
        return BAIDU_ERRNO_MAP.get(code, f"百度网盘未知错误 (errno={errno})")
    except (ValueError, TypeError):
        return f"百度网盘未知异常 (errno={errno})"


class BaiduPanClient(BasePanClient):
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
            }
        )
        self._set_cookie(credential)
        self.randsk = ""
        self.bdstoken = self._get_bdstoken()

    def _set_cookie(self, credential: str) -> None:
        for item in credential.split(";"):
            item = item.strip()
            if not item or "=" not in item:
                continue
            k, v = item.split("=", 1)
            self.session.cookies.set(k.strip(), v.strip(), domain=".baidu.com")

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
                logger.error("百度网盘无法获取分享页面详情: surl=%s", surl)
                return None, None, None

            share_id, from_uk, fs_id_list, file_names = share_info
            target_fs_id = fs_id_list[0]
            file_name = file_names[0]

            if to_dir and to_dir != "/":
                self.ensure_dir(to_dir)

            trans_res = self._transfer_file(share_id, from_uk, [target_fs_id], to_dir, surl=surl)
            if not trans_res:
                logger.error("百度网盘转存失败: %s", file_name)
                return None, None, None

            new_fs_id = trans_res if isinstance(trans_res, int) and trans_res > 1 else None
            full_path = f"{to_dir.rstrip('/')}/{file_name}" if to_dir != "/" else f"/{file_name}"
            if not new_fs_id:
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
            logger.error("百度网盘删除失败: %s (%s)", get_baidu_errno_message(errno), data)
            return False
        except Exception as exc:
            logger.error("百度网盘删除请求异常: %s", exc)
            return False

    def ensure_dir(self, dir_path: str) -> bool:
        """检查并确保百度网盘目录存在，若不存在则自动创建"""
        if not dir_path or dir_path.strip() in ("", "/"):
            return True
        clean_path = "/" + dir_path.strip("/")
        try:
            params = {
                "a": "commit",
                "channel": "chunlei",
                "clienttype": 8,
                "app_id": 250528,
            }
            payload = {
                "path": clean_path,
                "isdir": 1,
                "size": 0,
                "block_list": "[]",
                "rtype": 0,
            }
            data = self._request("POST", "https://pan.baidu.com/api/create", params=params, data=payload)
            errno = data.get("errno")
            # 0: 成功创建; -8: 目录已存在
            if errno in (0, -8):
                logger.info("百度网盘目标目录确认正常: %s", clean_path)
                return True
            logger.warning("百度网盘创建目录响应: %s (%s)", get_baidu_errno_message(errno), data)
            return False
        except Exception as exc:
            logger.error("百度网盘检查/创建目录异常: %s", exc)
            return False

    def _get_bdstoken(self) -> str:
        try:
            data = self._request(
                "GET",
                "https://pan.baidu.com/api/gettemplatevariable?fields=[%22bdstoken%22]",
            )
            return (data.get("result") or {}).get("bdstoken", "")
        except Exception as exc:
            logger.warning("获取百度网盘 bdstoken 异常: %s", exc)
            return ""

    def _parse_share_url(self, url: str) -> Tuple[str, str]:
        surl_match = re.search(r"s/1([a-zA-Z0-9-_]+)", url) or re.search(
            r"surl=([a-zA-Z0-9-_]+)", url
        )
        surl = surl_match.group(1) if surl_match else ""
        if not surl and "baidu.com/s/" in url:
            candidate = url.split("baidu.com/s/")[-1].split(" ")[0].split("?")[0]
            surl = candidate[1:] if candidate.startswith("1") else candidate

        pwd = extract_password_from_url(url) or ""
        return surl, pwd

    def _verify_pwd(self, surl: str, pwd: str) -> bool:
        import urllib.parse

        params = {
            "surl": surl,
            "t": int(time.time() * 1000),
            "bdstoken": self.bdstoken,
            "channel": "chunlei",
            "clienttype": 0,
            "web": 1,
            "app_id": 250528,
        }
        payload = {"pwd": pwd, "vcode": "", "vcode_str": ""}
        try:
            data = self._request(
                "POST",
                "https://pan.baidu.com/share/verify",
                params=params,
                data=payload,
                headers={"Referer": f"https://pan.baidu.com/s/1{surl}"},
            )
            if data.get("errno") == 0:
                raw_randsk = data.get("randsk", "")
                if raw_randsk:
                    self.randsk = urllib.parse.unquote(raw_randsk)
                return True
            errno = data.get("errno")
            logger.warning("百度网盘提取码校验失败: %s (%s)", get_baidu_errno_message(errno), data)
            return False
        except Exception as exc:
            logger.error("百度网盘提取码验证异常: %s", exc)
            return False

    def _get_share_page_info(
        self, surl: str
    ) -> Optional[Tuple[str, str, List[str], List[str]]]:
        # 1. 优先调用官方 JSON 接口 share/list 获取结构化分享详情
        list_url = "https://pan.baidu.com/share/list"
        params = {
            "web": "1",
            "page": "1",
            "num": "100",
            "order": "time",
            "desc": "1",
            "showempty": "0",
            "shorturl": surl,
            "root": "1",
            "clienttype": "0",
            "app_id": "250528",
        }
        if self.randsk:
            params["sekey"] = self.randsk

        try:
            headers = {"Referer": f"https://pan.baidu.com/s/1{surl}", "Accept-Encoding": "identity"}
            data = self._request("GET", list_url, params=params, headers=headers)
            if data.get("errno") == 0:
                share_id = str(data.get("share_id") or "")
                share_uk = str(data.get("uk") or data.get("share_uk") or "")
                file_list = data.get("list") or []
                fs_ids = [str(item["fs_id"]) for item in file_list if "fs_id" in item]
                file_names = [item["server_filename"] for item in file_list if "server_filename" in item]

                if share_id and share_uk and fs_ids and file_names:
                    logger.info("通过 share/list 接口成功获取分享详情: share_id=%s, files=%s", share_id, file_names)
                    return share_id, share_uk, fs_ids, file_names
            else:
                logger.warning("share/list 接口返回非0状态: %s (%s)", get_baidu_errno_message(data.get("errno")), data)
        except Exception as exc:
            logger.warning("通过 share/list 接口获取详情异常，尝试 HTML 页面解析兜底: %s", exc)

        # 2. 兜底方案：请求页面 HTML 正则解析
        try:
            headers = {"Referer": f"https://pan.baidu.com/s/1{surl}", "Accept-Encoding": "identity"}
            response = self.session.get(f"https://pan.baidu.com/s/1{surl}", headers=headers, timeout=20)
            response.raise_for_status()
            html = response.text

            share_id = re.search(r'"shareid":(\d+),', html) or re.search(r'"share_id":(\d+),', html)
            share_uk = re.search(r'"share_uk":"?(\d+)"?,', html) or re.search(r'"uk":"?(\d+)"?,', html)
            fs_ids = list(dict.fromkeys(re.findall(r'"fs_id":(\d+),', html)))
            file_names = list(dict.fromkeys(re.findall(r'"server_filename":"(.+?)",', html)))

            if share_id and share_uk and fs_ids and file_names:
                return share_id.group(1), share_uk.group(1), fs_ids, file_names
            logger.error("百度网盘分享页面 HTML 正则未能匹配到必要参数 (surl=%s)", surl)
            return None
        except Exception as exc:
            logger.error("百度网盘解析分享页面异常: %s", exc)
            return None

    def _transfer_file(
        self, share_id: str, from_uk: str, fs_id_list: List[str], to_path: str, surl: str = ""
    ) -> Optional[int]:
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
        if self.randsk:
            params["sekey"] = self.randsk
        payload = {
            "fsidlist": f"[{','.join(str(item) for item in fs_id_list)}]",
            "path": to_path,
        }
        headers = {
            "Referer": f"https://pan.baidu.com/s/1{surl}" if surl else "https://pan.baidu.com/disk/home"
        }
        try:
            data = self._request(
                "POST",
                "https://pan.baidu.com/share/transfer",
                params=params,
                data=payload,
                headers=headers,
            )
            errno = data.get("errno")
            if errno == 0:
                try:
                    to_fs_id = data.get("extra", {}).get("list", [{}])[0].get("to_fs_id")
                    if to_fs_id:
                        return int(to_fs_id)
                except Exception:
                    pass
                return 1
            logger.error("百度网盘转存失败: %s (%s)", get_baidu_errno_message(errno), data)
            return None
        except Exception as exc:
            logger.error("百度网盘转存请求异常: %s", exc)
            return None

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
                logger.warning("百度网盘列目录失败: %s", get_baidu_errno_message(data.get("errno")))
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
            errno = data.get("errno")
            if errno == 0 and (data.get("shorturl") or data.get("link")):
                link = data.get("shorturl") or data.get("link")
                if not link.startswith("http"):
                    link = f"https://pan.baidu.com/s/{link}"
                return f"{link}?pwd={pwd}" if "?pwd=" not in link else link
            logger.error("百度网盘创建分享失败: %s (%s)", get_baidu_errno_message(errno), data)
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
        headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        req_headers = {"Accept-Encoding": "identity"}
        if headers:
            req_headers.update(headers)
        response = self.session.request(method, url, params=params, data=data, headers=req_headers, timeout=20)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _to_json(value: Any) -> str:
        import json

        return json.dumps(value, ensure_ascii=False)

