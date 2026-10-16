"""中国移动云盘新版转存与分享客户端。"""

import base64
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from src.clients.base_client import BasePanClient
from src.clients.caiyun_protocol import (
    CREATE_SHARE_URL, PERSONAL_API_BASE, SHARE_API_BASE, TASK_PATH, TRANSFER_PATH,
    decode_share_response, encode_share_payload, mcloud_sign,
)

logger = logging.getLogger(__name__)


class CaiyunPanClient(BasePanClient):
    def __init__(self, credential: Union[str, Dict[str, Any]]) -> None:
        if isinstance(credential, str):
            try:
                parsed = json.loads(credential)
                if isinstance(parsed, dict):
                    credential = parsed
            except ValueError:
                pass
        if isinstance(credential, dict):
            self.auth_token = str(credential.get("auth_token") or credential.get("authorization") or credential.get("token") or "").strip()
            self.account = str(credential.get("account") or credential.get("phone") or "").strip()
            self.cookie = str(credential.get("cookie") or credential.get("Cookie") or "").strip()
        else:
            self.auth_token = str(credential or "").strip()
            self.account = ""
            self.cookie = ""
        if not self.account and self.auth_token:
            try:
                token = re.sub(r"^Basic\s+", "", self.auth_token, flags=re.I)
                self.account = base64.b64decode(token).decode("utf-8").split(":")[1]
            except (IndexError, UnicodeError, ValueError):
                pass
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://yun.139.com",
            "Referer": "https://yun.139.com/shareweb/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/139.0.0.0 Safari/537.36",
        })
        if self.cookie:
            self.session.headers["Cookie"] = self.cookie

    @property
    def _authorization(self) -> str:
        token = re.sub(r"^Basic\s+", "", self.auth_token, flags=re.I)
        return f"Basic {token}" if token else ""

    def _parse_share_url(self, share_url: str) -> Tuple[Optional[str], Optional[str]]:
        if not share_url:
            return None, None
        match = re.search(
            r"(?:yun\.139\.com/shareweb/#/w/i/|caiyun\.139\.com/w/i/|caiyun\.139\.com/m/i\?|pan\.10086\.cn/s/|/w/i/)([a-zA-Z0-9_-]+)",
            share_url, re.I,
        ) or re.search(r"linkId=([a-zA-Z0-9_-]+)", share_url, re.I)
        if not match:
            return None, None
        password = re.search(r"(?:[?&]pwd=|提取码[:：=\s]*|密码[:：=\s]*)([a-zA-Z0-9]{4,6})", share_url, re.I)
        return match.group(1), password.group(1) if password else None

    @staticmethod
    def _ok(result: Optional[Dict[str, Any]]) -> bool:
        if not result:
            return False
        code = str(result.get("code", result.get("resultCode", "")))
        if code in ("0", "0000"):
            return result.get("success") is not False
        if "code" not in result and "resultCode" not in result and result.get("success") is True:
            return True
        return False

    def _request_share_api(self, path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        headers = {
            "X-Yun-Api-Version": "v1",
            "X-Deviceinfo": "||9|12.27.0|chrome|139.0.0.0|||windows 10||zh-CN|||",
            "hcy-cool-flag": "1", "CMS-DEVICE": "default", "x-m4c-caller": "PC",
        }
        if self._authorization:
            headers["Authorization"] = self._authorization
        try:
            response = self.session.post(SHARE_API_BASE + path, data=encode_share_payload(payload), headers=headers, timeout=20)
            response.raise_for_status()
            result = decode_share_response(response.content)
            if self._ok(result):
                return result
            logger.error("移动云盘分享接口失败: %s %s", result.get("code"), result.get("desc"))
        except (requests.RequestException, ValueError) as exc:
            logger.error("移动云盘分享接口请求错误: %s", exc)
        return None

    def _request_signed_api(self, url: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._authorization:
            logger.error("移动云盘缺少 Basic 授权令牌")
            return None
        headers = {
            "Authorization": self._authorization, "CMS-DEVICE": "default", "Caller": "web",
            "mcloud-channel": "1000101", "mcloud-client": "10701",
            "mcloud-route": "001", "mcloud-sign": mcloud_sign(payload), "mcloud-version": "7.14.0",
            "x-DeviceInfo": "||9|7.14.0|chrome|120.0.0.0|||windows 10||zh-CN|||",
            "x-huawei-channelSrc": "10000034", "x-inner-ntwk": "2",
            "x-m4c-caller": "PC", "x-m4c-src": "10002", "x-SvcType": "1",
            "X-Yun-Api-Version": "v1", "X-Yun-App-Channel": "10000034",
            "X-Yun-Channel-Source": "10000034",
            "X-Yun-Client-Info": "||9|7.14.0|chrome|120.0.0.0|||windows 10||zh-CN|||dW5kZWZpbmVk||",
            "X-Yun-Module-Type": "100", "X-Yun-Svc-Type": "1",
        }
        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            result = response.json()
            if self._ok(result):
                return result
            logger.error("移动云盘个人接口失败: %s %s", result.get("code"), result.get("message"))
        except (requests.RequestException, ValueError) as exc:
            logger.error("移动云盘个人接口请求错误: %s", exc)
        return None

    def get_share_items(self, share_url: str, parent_id: str = "root", start: int = 1) -> Optional[Dict[str, Any]]:
        share_id, password = self._parse_share_url(share_url)
        if not share_id:
            return None
        return self._request_share_api("/richlifeApp/devapp/IOutLink/getOutLinkInfoV6", {
            "getOutLinkInfoReq": {
                "account": self.account, "linkID": share_id, "passwd": password or "",
                "caSrt": 0, "coSrt": 0, "srtDr": 1, "bNum": start,
                "pCaID": parent_id, "eNum": start + 199,
            },
        })

    def _share_entries(self, share_url: str) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        entries: List[Dict[str, Any]] = []
        info: Dict[str, Any] = {}
        for start in range(1, 10002, 200):
            result = self.get_share_items(share_url, start=start)
            if not result or not isinstance(result.get("data"), dict):
                return None
            data = result["data"]
            if not info:
                info = data
            page = (data.get("caLst") or []) + (data.get("coLst") or [])
            entries.extend(page)
            if len(page) < 200:
                break
        return info, entries

    def _list_personal(self, parent_id: str) -> Optional[List[Dict[str, Any]]]:
        items: List[Dict[str, Any]] = []
        cursor = ""
        for _ in range(100):
            result = self._request_signed_api(PERSONAL_API_BASE + "/file/list", {
                "pageInfo": {"pageSize": 100, "pageCursor": cursor or None},
                "orderBy": "updated_at", "orderDirection": "DESC",
                "parentFileId": parent_id, "imageThumbnailStyleList": ["Small", "Large"],
            })
            if not result:
                return None
            data = result.get("data") or {}
            items.extend(data.get("items") or [])
            next_cursor = data.get("nextPageCursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return items

    def _transfer(self, share_url: str, target_dir: str, entries: List[Dict[str, Any]], info: Dict[str, Any]) -> bool:
        share_id, password = self._parse_share_url(share_url)
        if not share_id or not self.account:
            logger.error("移动云盘转存需要有效 Basic 令牌和账号")
            return False
        catalogs = [x.get("path") for x in entries if x.get("caID")]
        contents = [x.get("path") for x in entries if x.get("coID")]
        if not all(catalogs + contents):
            logger.error("移动云盘分享项缺少转存所需的 path")
            return False
        task_info = {
            "linkID": share_id, "contentInfoList": contents, "catalogInfoList": catalogs,
            "newCatalogID": target_dir, "newCatalogName": "全部",
            "needPassword": bool(password),
        }
        result = self._request_share_api(TRANSFER_PATH, {
            "createOuterLinkBatchOprTaskReq": {
                "msisdn": self.account, "ownerAccount": info.get("owner") or info.get("creator") or "",
                "taskType": 1, "taskInfo": task_info, "linkID": share_id,
                "needPassword": bool(password),
            },
        })
        data = (result or {}).get("data") or {}
        task_id = data.get("taskID") or data.get("taskId") or (data.get("createBatchOprTaskRes") or {}).get("taskID")
        if not task_id:
            logger.error("移动云盘转存接口未返回任务 ID")
            return False
        for _ in range(20):
            detail = self._request_share_api(TASK_PATH, {
                "queryBatchOprTaskDetailReq": {"taskID": task_id, "msisdn": self.account},
            })
            if not detail:
                return False
            task = (detail.get("data") or {}).get("queryBatchOprTaskDetailRes") or detail.get("data") or {}
            status = task.get("batchOprTask") or task.get("taskInfo") or {}
            state = status.get("taskStatus", status.get("status"))
            if state in (2, "Succeed", "PartialSucceed", "Failed"):
                if state == "Failed" or str(status.get("taskResultCode", "1")) in ("2", "3"):
                    logger.error("移动云盘转存任务失败: %s", status)
                    return False
                return True
            time.sleep(1)
        logger.error("移动云盘转存任务超时: %s", task_id)
        return False

    def _create_share(self, file_ids: List[str], folder_ids: List[str], title: str) -> Optional[str]:
        if not self.account:
            return None
        result = self._request_signed_api(CREATE_SHARE_URL, {"getOutLinkReq": {
            "subLinkType": 0, "encrypt": 0, "coIDLst": file_ids, "caIDLst": folder_ids,
            "pubType": 1, "dedicatedName": title, "periodUnit": 1,
            "viewerLst": [], "extInfo": {"isWatermark": 0, "shareChannel": "3001"},
            "commonAccountInfo": {"account": self.account, "accountType": 1},
        }})
        data = (result or {}).get("data") or {}
        shares = (data.get("getOutLinkRes") or {}).get("getOutLinkResSet") or []
        if not shares:
            logger.error("移动云盘创建分享响应缺少链接")
            return None
        share = shares[0]
        return share.get("linkUrl") or (f"https://yun.139.com/shareweb/#/w/i/{share['linkID']}" if share.get("linkID") else None)

    def store(self, share_url: str, to_pdir_path: str = "/") -> Tuple[Optional[str], Optional[str], Optional[str]]:
        parsed = self._share_entries(share_url)
        if not parsed:
            return None, None, None
        info, entries = parsed
        from src.services.ad_filter_service import is_ad_filename
        entries = [x for x in entries if not is_ad_filename(x.get("caName") or x.get("coName") or "")]
        if not entries:
            logger.warning("移动云盘分享内容为空或全部为广告")
            return None, None, None
        target = to_pdir_path if to_pdir_path not in ("", "root") else "/"
        before = self._list_personal(target)
        if before is None or not self._transfer(share_url, target, entries, info):
            return None, None, None
        previous_ids = {x.get("fileId") for x in before}
        expected_names = {x.get("caName") or x.get("coName") for x in entries}
        saved: List[Dict[str, Any]] = []
        for _ in range(8):
            after = self._list_personal(target)
            if after is None:
                break
            new_items = [x for x in after if x.get("fileId") not in previous_ids]
            saved = [x for x in new_items if x.get("name") in expected_names]
            # 重复转存时服务端可能自动给同名文件追加序号。
            if len(saved) < len(entries):
                renamed = [x for x in new_items if x not in saved and any(
                    str(x.get("name") or "").startswith(name + suffix)
                    for name in expected_names for suffix in ("(", "（", "_") if name
                )]
                saved.extend(renamed[:len(entries) - len(saved)])
            if len(saved) >= len(entries):
                break
            time.sleep(1)
        if len(saved) < len(entries):
            logger.error("移动云盘转存成功，但未在目标目录找到全部新文件")
            return None, None, None
        file_ids = [x["fileId"] for x in saved if x.get("type") != "folder"]
        folder_ids = [x["fileId"] for x in saved if x.get("type") == "folder"]
        for folder_id in folder_ids:
            try:
                self.add_ad(folder_id)
            except Exception as exc:
                logger.warning("移动云盘植入自定义文件失败: %s", exc)
        title = info.get("lkName") or entries[0].get("caName") or entries[0].get("coName") or "移动云盘转存文件"
        new_url = self._create_share(file_ids, folder_ids, title)
        if not new_url:
            logger.error("移动云盘转存成功，但创建分享失败")
        return json.dumps(file_ids + folder_ids, ensure_ascii=False), title, new_url

    def get_or_create_dir(self, dir_name: str, parent_id: str = "root") -> str:
        parent = "/" if parent_id in ("", "root") else parent_id
        name = (dir_name or "").strip().strip("/")
        if not name:
            return parent
        items = self._list_personal(parent)
        if items is None:
            return parent
        for item in items:
            if item.get("type") == "folder" and item.get("name") == name:
                return item["fileId"]
        result = self._request_signed_api(PERSONAL_API_BASE + "/file/create", {
            "parentFileId": parent, "name": name, "description": "",
            "type": "folder", "fileRenameMode": "force_rename",
        })
        res_data = (result or {}).get("data") or {}
        return str(res_data.get("fileId") or res_data.get("catalogID") or res_data.get("catalogId") or parent)

    def add_ad(self, target_dir_id: str, ad_share_url: Optional[str] = None) -> bool:
        if not ad_share_url:
            from src.services.system_config_service import get_ad_share_url_for_disk
            ad_share_url = get_ad_share_url_for_disk("caiyun")
        if not ad_share_url:
            return False
        parsed = self._share_entries(ad_share_url)
        return bool(parsed and parsed[1] and self._transfer(ad_share_url, target_dir_id, parsed[1][:1], parsed[0]))

    def del_file(self, file_ids: Union[str, List[str]]) -> bool:
        if not file_ids:
            return True
        if isinstance(file_ids, str):
            try:
                decoded = json.loads(file_ids)
                targets = decoded if isinstance(decoded, list) else [file_ids]
            except ValueError:
                targets = [file_ids]
        else:
            targets = list(file_ids)
        return bool(self._request_signed_api(PERSONAL_API_BASE + "/recyclebin/batchTrash", {"fileIds": targets}))

    def get_user_and_space_info(self) -> Dict[str, Any]:
        return {"username": self.account, "total_space_bytes": 0, "used_space_bytes": 0, "vip_status": 0}
