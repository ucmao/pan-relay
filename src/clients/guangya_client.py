# -*- coding: utf-8 -*-
"""
光鸭云盘客户端（guangyapan.com）
---------------------------------------------------------------
适配 2026-11 的现行接口。原项目里的 /drive/v1/* 已全部下线，
调用会返回 410 {"code":128,"msg":"路径不允许访问"}。

本文件已按线上接口实测校正，接口契约如下：

| 用途             | 接口（全部 POST，Bearer 鉴权）                       |
|------------------|-----------------------------------------------------|
| 换 access_token  | account.guangyapan.com/v1/auth/token                |
| 列目录           | /userres/v1/file/get_file_list                      |
| 建目录           | /userres/v1/file/create_dir                         |
| 删文件/目录      | /userres/v1/file/delete_file                        |
| 容量/会员        | /assets/v1/get_assets                               |
| 分享概要         | /userres/v1/get_share_summary                       |
| 分享访问 token   | /userres/v1/get_share_access_token                  |
| 分享内文件列表   | /userres/v1/get_share_page_files_list               |
| 转存（异步任务） | /userres/v1/restore_share  -> data.taskId           |
| 任务状态轮询     | /userres/v1/get_task_status  (2=成功 3=失败)         |
| 新建分享         | /userres/v1/share_file -> data.shareUrl             |

要点：
1. 根目录 parentId 是空字符串 ""，不是 "0"；
2. 转存前必须先拿"分享 accessToken"（不是账号 token），它是一次性的 share-scoped JWT；
3. 转存是异步任务：restore_share 只返回 taskId，必须轮询 get_task_status 到 2/3；
4. 不能转存自己账号发布的分享（服务端返回 code=204「不能转存自己的分享」）；
5. refresh_token 刷新后不会轮换（实测新旧 refresh_token 一致），配置一次可长期用；
6. get_file_list 不能带 resType 参数，带了只返回文件、把文件夹滤掉，
   转存进来的目录就"看不见"，最终表现为"转存成功但换不出链接"（实测踩过）；
7. 后台填的转存目录是"路径"，必须逐级解析成 fileId（_ensure_dir_path），
   直接把路径当 parentId 传会静默落进根目录；
8. delete_file 只是移入回收站（默认保留 30 天），删除后已用空间不会立刻下降，
   后台容量读数还包含回收站占用，属正常现象；
9. 框架 pan_operator._resolve_target_dir 会先调本类 get_or_create_dir 把目录解析成
   fileId，再把 fileId 当 to_pdir_path 传回 store()；所以目标既可能是 path 也可能是
   纯数字 fileId，还可能是框架兜底的 "0"，三种都要认（见 _resolve_target_parent）；
10. 后台凭证框支持"只填 refresh_token"，而光鸭 refresh_token 以 "gy." 开头。
    构造时必须按前缀区分 refresh_token / access_token，否则会把 refresh_token
    当 Bearer 发出去，全部接口 401 code=117「无效token」，容量显示 0 B。
"""

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

ROOT_ID = ""          # 光鸭根目录标识
TASK_SUCCESS = 2
TASK_FAILED = 3


class GuangyaPanClient(BasePanClient):
    """光鸭云盘客户端实现 (guangyapan.com)"""

    api_base = "https://api.guangyapan.com"
    auth_base = "https://account.guangyapan.com"
    client_id = "aMe-8VSlkrbQXpUR"

    def __init__(self, credential: Union[str, Dict[str, Any]]) -> None:
        self.raw_credential = credential
        self.access_token = ""
        self.refresh_token = ""

        if isinstance(credential, dict):
            self.access_token = str(credential.get("access_token") or "").strip()
            self.refresh_token = str(credential.get("refresh_token") or "").strip()
        elif isinstance(credential, str):
            clean_cred = credential.strip()
            at, rt = self._loose_extract_tokens(clean_cred)
            if rt:
                # 有 refresh_token 就绝不依赖 access_token：后者可能被复制成"中间带省略号"
                # 的半截串，拿它发 Authorization 会直接抛
                # 'latin-1' codec can't encode character '\u2026'，所有接口全挂。
                self.refresh_token = rt
                self.access_token = ""
            elif at:
                self.access_token = at
            elif clean_cred.startswith("{") and clean_cred.endswith("}"):
                try:
                    data = json.loads(clean_cred)
                    if isinstance(data, dict):
                        self.access_token = str(data.get("access_token") or "").strip()
                        self.refresh_token = str(data.get("refresh_token") or "").strip()
                    else:
                        self.access_token = self._strip_junk(clean_cred)
                except Exception:
                    self.access_token = self._strip_junk(clean_cred)
            else:
                self.access_token = self._strip_junk(clean_cred)

        self._drop_bad_tokens()

        # 目录路径 -> fileId 缓存，键为 (父目录 fileId, 目录名)
        self._dir_id_cache: Dict[Tuple[str, str], str] = {}

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

    # ------------------------------------------------------------------
    # 凭证清洗
    # ------------------------------------------------------------------
    _JUNK_CHARS = ("\u2026", "\u200b", "\u200c", "\u200d", "\ufeff", "\u00a0")

    @classmethod
    def _strip_junk(cls, text: str) -> str:
        """去掉复制粘贴常带的不可见/非法字符（省略号、零宽空格、不间断空格、换行）。"""
        s = str(text or "")
        for ch in cls._JUNK_CHARS:
            s = s.replace(ch, "")
        return "".join(s.split())

    @classmethod
    def _loose_extract_tokens(cls, text: str) -> Tuple[str, str]:
        """从被污染的粘贴串里抠出 (access_token, refresh_token)。

        典型污染：从聊天窗口复制成 {"access_token":"eyJ…nnc4","refresh_token":"gy.xxx"}，
        中间被塞了省略号，json.loads 直接失败；若硬把整串当 token 发出去，requests
        会抛 'latin-1' codec can't encode character '\\u2026'，所有接口一起挂。
        两种令牌前缀是固定的（access_token 一律 eyJ 开头的 JWT / refresh_token 一律 gy.），
        所以按前缀正则提取，比解析 JSON 抗污染。
        """
        raw = str(text or "")
        at_match = re.search(r"eyJ[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+){1,2}", raw)
        rt_match = re.search(r"gy\.[A-Za-z0-9_\-\.]{20,}", raw)
        at = cls._strip_junk(at_match.group(0)) if at_match else ""
        rt = cls._strip_junk(rt_match.group(0)) if rt_match else ""
        return at, rt

    def _drop_bad_tokens(self) -> None:
        """丢弃含非法字符的令牌：一个坏字符就能让整个客户端的所有接口全挂。"""
        for name in ("access_token", "refresh_token"):
            val = getattr(self, name, "") or ""
            if val and not val.isascii():
                logger.error(
                    f"光鸭云盘凭证里的 {name} 含非 ASCII 字符（多为复制时带进了省略号/中文引号），"
                    f"已丢弃；请在后台只粘贴完整、连续的 refresh_token（以 gy. 开头）。"
                )
                setattr(self, name, "")

    # ------------------------------------------------------------------
    # 鉴权
    # ------------------------------------------------------------------
    def _get_access_token(self) -> str:
        if self.access_token and not self.refresh_token:
            return self.access_token
        if self.refresh_token:
            cached = _GUANGYA_ACCESS_TOKEN_CACHE.get(self.refresh_token)
            if cached and cached.get("expires_at", 0) > time.time() + 60:
                return cached.get("access_token", "")
            try:
                resp = self.session.post(
                    f"{self.auth_base}/v1/auth/token",
                    json={
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                        "client_id": self.client_id,
                    },
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
                else:
                    logger.warning(
                        "光鸭云盘刷新 access_token 失败 [%s]: %s",
                        resp.status_code, resp.text[:200],
                    )
            except Exception as e:
                logger.warning(f"光鸭云盘刷新 access_token 失败: {e}")
        return self.access_token

    # ------------------------------------------------------------------
    # 通用请求
    # ------------------------------------------------------------------
    def _request_api(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> Optional[Dict[str, Any]]:
        """光鸭现行接口全部是 POST + JSON body，method 参数保留只为兼容旧调用。"""
        token = self._get_access_token()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"{self.api_base}{path}" if path.startswith("/") else path
        body = payload if payload is not None else {}
        if params:
            # 少数接口仍需 query，兼容保留
            body = dict(body)
            body.update({k: v for k, v in params.items() if k not in body})
        try:
            resp = self.session.request(
                method="POST",
                url=url,
                json=body,
                headers=headers,
                timeout=timeout,
            )
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    logger.error(f"光鸭云盘返回非 JSON: {resp.text[:200]}")
                    return None
            logger.error(f"光鸭云盘 API 请求失败 [{resp.status_code}] {path}: {resp.text[:200]}")
            return None
        except Exception as exc:
            logger.error(f"光鸭云盘 API 请求异常 {path}: {exc}")
            return None

    @staticmethod
    def _ok(res: Optional[Dict[str, Any]]) -> bool:
        """光鸭成功响应有两种风格：{"msg":"success","data":{}} 或 {"code":0,...}"""
        if not res:
            return False
        if res.get("_http"):
            return False
        code = res.get("code")
        return code in (None, 0, 200) and res.get("msg") in (None, "success", "")

    # ------------------------------------------------------------------
    # 分享链接解析
    # ------------------------------------------------------------------
    def _parse_share_url(self, share_url: str) -> Tuple[Optional[str], Optional[str]]:
        """从分享 URL 中解析出 shareId 与提取码（光鸭参数名可能是 pwd / code / shareCode）"""
        if not share_url:
            return None, None
        match = re.search(r"guangyapan\.com/s/([a-zA-Z0-9_\-]+)", share_url, re.IGNORECASE)
        if not match:
            return None, None
        share_id = match.group(1)
        pwd_match = re.search(
            r"(?:[?&](?:pwd|code|shareCode)=|提取码[:：=\s]*|密码[:：=\s]*)([a-zA-Z0-9]{3,8})",
            share_url, re.IGNORECASE,
        )
        pwd = pwd_match.group(1) if pwd_match else None
        return share_id, pwd

    # ------------------------------------------------------------------
    # 目录
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_parent(parent_id: Optional[str]) -> str:
        """光鸭根目录是空串；旧调用传进来的 "0" / "/" 统一转换"""
        if not parent_id or str(parent_id).strip() in ("", "/", "0"):
            return ROOT_ID
        return str(parent_id).strip()

    def _list_dir(self, parent_id: str = ROOT_ID, page_size: int = 100) -> List[Dict[str, Any]]:
        parent = self._norm_parent(parent_id)
        items: List[Dict[str, Any]] = []
        page = 0
        while page < 20:  # 安全上限
            # 关键：绝对不能带 resType。光鸭的 resType 是"资源类型"过滤，
            # 传 1 只会返回文件、把文件夹整个滤掉，转存进来的目录就永远"看不见"，
            # 表现为转存成功但拿不到新 fileId（实测踩过这个坑）。
            res = self._request_api(
                "POST", "/userres/v1/file/get_file_list",
                payload={"page": page, "pageSize": page_size, "parentId": parent},
            )
            if not self._ok(res):
                logger.warning(f"光鸭云盘列目录失败 [parent={parent!r}]: {str(res)[:200]}")
                break
            data = res.get("data") or {}
            batch = data.get("list") or []
            items.extend(batch)
            total = int(data.get("total") or 0)
            page += 1
            if not batch or len(items) >= total:
                break
        return items

    def get_or_create_dir(self, dir_name: str, parent_id: str = ROOT_ID) -> Optional[str]:
        """获取或创建单级目录，返回目录 fileId；失败返回 None。

        光鸭 create_dir 带 failIfNameExist=True 时，同名目录会返回
        code=159「文件夹名称重复」，但响应里仍带已存在目录的 fileId，可直接复用，
        所以不需要"先列再建"两趟请求。
        """
        if not dir_name or str(dir_name).strip() in ("", "/"):
            return self._norm_parent(parent_id)
        raw_name = str(dir_name).strip().strip("/")
        # 兼容上层直接传多级路径（如 "备份/Pan-Relay分享"）的情况，
        # 单级目录名里出现分隔符时按路径逐级解析，避免建出一个名字里带斜杠的怪目录。
        if re.search(r"[\\/]", raw_name):
            return self._ensure_dir_path(raw_name)
        clean_name = raw_name
        parent = self._norm_parent(parent_id)

        cached = self._dir_id_cache.get((parent, clean_name))
        if cached:
            return cached

        res = self._request_api(
            "POST", "/userres/v1/file/create_dir",
            payload={"parentId": parent, "dirName": clean_name, "failIfNameExist": True},
        )
        data = (res or {}).get("data") or {}
        fid = data.get("fileId")
        if fid:
            if (res or {}).get("code") == 159:
                logger.info(f"光鸭云盘复用已有目录 [{clean_name}]: {fid}")
            else:
                logger.info(f"光鸭云盘成功创建目录 [{clean_name}]: {fid}")
            self._dir_id_cache[(parent, clean_name)] = str(fid)
            return str(fid)

        # 兜底：接口异常时退回"先列目录再建"的老路
        for item in self._list_dir(parent):
            if item.get("fileName") == clean_name and item.get("dirType") == 1:
                fid = str(item.get("fileId"))
                self._dir_id_cache[(parent, clean_name)] = fid
                return fid
        logger.error(f"光鸭云盘创建目录失败 [{clean_name}]: {str(res)[:200]}")
        return None

    def _ensure_dir_path(self, path: str) -> str:
        """把 "/a/b/c" 这样的目标路径逐级解析成末尾目录的 fileId，缺哪级就建哪级。

        后台配置的"转存目录"是路径而不是 fileId，必须走这里转换；
        直接当 parentId 传给服务端会静默落到根目录。
        """
        raw = str(path or "").strip()
        segments = [s for s in re.split(r"[\\/]+", raw) if s and s not in (".", "..")]
        current = ROOT_ID
        for seg in segments:
            current = self.get_or_create_dir(seg, current)
            if not current:
                raise ValueError(f"光鸭云盘目标目录创建失败: {raw}（{seg}）")
        logger.info(f"光鸭云盘目标目录 [{raw or '/'}] -> fileId={current or '(根目录)'}")
        return current

    def _resolve_target_parent(self, target: Any) -> str:
        """把框架传进来的转存目标解析成光鸭的 parentId。

        框架（pan_operator._resolve_target_dir）拿到的值有三种形态，必须分开处理：
          1. 空 / "/" / "0" / "root"  —— 表示根目录（"0" 是框架对非百度网盘的默认兜底值）；
          2. 纯数字长串           —— 框架已经调过 get_or_create_dir 拿到 fileId，
                                      这时再当目录名去建，会建出一个"纯数字名字"的目录；
          3. 路径（如 "/Pan-Relay分享" 或 "备份/Pan-Relay分享"） —— 逐级解析、缺级补建。
        """
        raw = str(target or "").strip()
        if raw in ("", "/", "0", "root", ".", "./"):
            return ROOT_ID
        if re.fullmatch(r"\d{10,25}", raw):
            # 已经是 fileId，直接用
            return raw
        return self._ensure_dir_path(raw)

    # ------------------------------------------------------------------
    # 转存相关
    # ------------------------------------------------------------------
    def _get_share_access_token(self, share_id: str, pwd: Optional[str]) -> Optional[str]:
        payload = {"shareId": share_id}
        if pwd:
            payload["code"] = pwd
        res = self._request_api("POST", "/userres/v1/get_share_access_token", payload=payload)
        token = ((res or {}).get("data") or {}).get("accessToken")
        if not token:
            logger.error(f"光鸭云盘获取分享访问令牌失败: {str(res)[:200]}")
        return token

    def _get_share_files(self, share_id: str, share_token: str) -> List[Dict[str, Any]]:
        res = self._request_api(
            "POST", "/userres/v1/get_share_page_files_list",
            payload={"shareId": share_id, "accessToken": share_token,
                     "parentId": "", "page": 0, "pageSize": 200},
        )
        if not self._ok(res):
            logger.error(f"光鸭云盘获取分享文件列表失败: {str(res)[:200]}")
            return []
        return (res.get("data") or {}).get("list") or []

    def _restore_share(
        self, share_id: str, share_token: str, file_ids: List[str], parent_id: str, pwd: Optional[str]
    ) -> List[str]:
        """转存到指定目录，返回落盘后的新 fileId 列表"""
        parent = self._norm_parent(parent_id)
        before_ids = {str(i.get("fileId")) for i in self._list_dir(parent)}

        payload = {
            "accessToken": share_token,
            "fileIds": file_ids,
            "parentId": parent,
        }
        if pwd:
            payload["shareCode"] = pwd
        res = self._request_api("POST", "/userres/v1/restore_share", payload=payload)
        if not res:
            return []
        code = res.get("code")
        if code not in (None, 0, 200):
            logger.error(f"光鸭云盘转存失败 [{code}] {res.get('msg')}")
            if code == 204:
                logger.error("光鸭云盘不允许转存本账号自己发布的分享，请换外部分享链接")
            return []
        task_id = (res.get("data") or {}).get("taskId")
        if not task_id:
            logger.error(f"光鸭云盘转存未返回 taskId: {str(res)[:200]}")
            return []

        if not self._wait_task(task_id):
            return []

        after_ids = {str(i.get("fileId")): i for i in self._list_dir(parent)}
        new_ids = [fid for fid in after_ids if fid not in before_ids]
        logger.info(f"光鸭云盘转存成功，新增文件 {len(new_ids)} 项")
        return new_ids

    def _wait_task(self, task_id: Any, timeout: int = 60) -> bool:
        """轮询异步任务状态：2=成功 3=失败"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            res = self._request_api("POST", "/userres/v1/get_task_status", payload={"taskId": task_id})
            data = (res or {}).get("data") or {}
            status = data.get("status")
            if status == TASK_SUCCESS:
                return True
            if status == TASK_FAILED:
                detail = data.get("detail") or {}
                logger.error(f"光鸭云盘异步任务失败: {detail.get('msg')} (code={detail.get('code')})")
                return False
            time.sleep(1)
        logger.error(f"光鸭云盘异步任务超时: taskId={task_id}")
        return False

    # ------------------------------------------------------------------
    # 对外的转存入口
    # ------------------------------------------------------------------
    def store(
        self, share_url: str, to_pdir_path: str = "/"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """转存光鸭分享并在个人网盘中生成自己的新分享链接"""
        share_id, pwd = self._parse_share_url(share_url)
        if not share_id:
            logger.error(f"光鸭云盘分享链接解析失败: {share_url}")
            return None, None, None

        share_token = self._get_share_access_token(share_id, pwd)
        if not share_token:
            return None, None, None

        raw_files = self._get_share_files(share_id, share_token)
        try:
            from src.services.ad_filter_service import is_ad_filename
            files = [f for f in raw_files if not is_ad_filename(f.get("fileName", ""))]
        except Exception:
            files = raw_files
        if not files:
            logger.warning("光鸭云盘分享内容为空或全为广告，已终止转存")
            return None, None, None

        file_ids = [str(f["fileId"]) for f in files if f.get("fileId")]
        file_name = files[0].get("fileName") or "光鸭分享文件"

        # 后台配置的是目录路径（如 "/Pan-Relay分享"），要先解析/创建成 fileId，
        # 否则服务端拿到一个非 fileId 的值会静默落到根目录。
        # 注意框架可能已经把路径解析成 fileId 再传进来，两者都要认（见 _resolve_target_parent）。
        # 目录缓存只在本轮转存内有效：外部删掉目录后不能继续复用旧 fileId，
        # 否则转存会落进一个不存在的目录（服务端可能静默回落到根目录）。
        self._dir_id_cache.clear()
        try:
            parent = self._resolve_target_parent(to_pdir_path)
        except Exception as exc:
            logger.error(f"光鸭云盘转存中止：{exc}")
            return None, None, None

        saved_ids = self._restore_share(share_id, share_token, file_ids, parent, pwd)
        if not saved_ids:
            return None, None, None

        # 植入自定义引流文件（如已配置）
        try:
            self.add_ad(parent)
        except Exception as exc:
            logger.debug(f"光鸭云盘植入引流文件跳过: {exc}")

        res = self._request_api(
            "POST", "/userres/v1/share_file",
            payload={
                "fileIds": saved_ids,
                "title": file_name,
                "validateDuration": 0,   # 0 = 永久有效
                "shareType": 0,
                "downloadType": 1,
                "maxRestoreCount": 0,
            },
        )
        new_share_url = None
        if res and self._ok(res):
            data = res.get("data") or {}
            new_share_url = data.get("shareUrl")
            if not new_share_url and data.get("shareId"):
                new_share_url = f"https://www.guangyapan.com/s/{data['shareId']}"
        else:
            logger.error(f"光鸭云盘创建分享失败: {str(res)[:200]}")

        return json.dumps(saved_ids, ensure_ascii=False), file_name, new_share_url

    def add_ad(self, parent_id: str, ad_share_url: Optional[str] = None) -> bool:
        """向光鸭云盘指定目录植入个人自定义引流文件"""
        target_url = (ad_share_url or "").strip()
        if not target_url:
            try:
                from src.services.system_config_service import get_ad_share_url_for_disk
                target_url = get_ad_share_url_for_disk("guangya")
            except Exception:
                target_url = ""
        if not target_url:
            return False

        share_id, pwd = self._parse_share_url(target_url)
        if not share_id:
            logger.warning(f"光鸭云盘广告链接无效: {target_url}")
            return False
        share_token = self._get_share_access_token(share_id, pwd)
        if not share_token:
            return False
        files = self._get_share_files(share_id, share_token)
        if not files:
            return False
        first_id = str(files[0]["fileId"])
        if self._restore_share(share_id, share_token, [first_id], parent_id, pwd):
            logger.info(f"光鸭云盘已向目录 {parent_id} 植入引流文件 (share_id={share_id})")
            return True
        return False

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------
    def del_file(self, file_ids: Union[str, List[str]]) -> bool:
        """从个人光鸭云盘中批量删除文件或目录"""
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

        res = self._request_api("POST", "/userres/v1/file/delete_file", payload={"fileIds": targets})
        if res and self._ok(res):
            logger.info(f"光鸭云盘删除成功: {targets}")
            return True
        logger.error(f"光鸭云盘删除失败: {str(res)[:200]}")
        return False

    def _clean_ad_files_and_folders(self, file_ids: List[str]) -> List[str]:
        """清理转存结果中的广告引流文件"""
        try:
            from src.services.ad_filter_service import is_ad_filename
        except Exception:
            return list(file_ids)

        valid_ids, ad_ids = [], []
        for fid in file_ids:
            info = self._request_api("POST", "/userres/v1/file/get_info_by_file_id", payload={"fileId": fid})
            name = ((info or {}).get("data") or {}).get("fileName") or ""
            if name and is_ad_filename(name):
                ad_ids.append(fid)
            else:
                valid_ids.append(fid)
        if ad_ids:
            try:
                self.del_file(ad_ids)
            except Exception as exc:
                logger.error(f"光鸭云盘清理广告失败: {exc}")
        return valid_ids

    # ------------------------------------------------------------------
    # 账号信息
    # ------------------------------------------------------------------
    @staticmethod
    def _pick_int(data: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[int]:
        """按候选字段名依次取值，兼容接口字段改名"""
        for key in keys:
            val = data.get(key)
            if val is None or val == "":
                continue
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
        return None

    def get_user_and_space_info(self) -> Dict[str, Any]:
        info = {"username": "", "total_space_bytes": 0, "used_space_bytes": 0, "vip_status": 0}
        token = self._get_access_token()
        if not token:
            return info

        # JWT payload 里取 UID（sub）
        try:
            import base64
            parts = token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
                payload_data = json.loads(
                    base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8", errors="ignore")
                )
                if payload_data.get("sub"):
                    info["username"] = f"UID:{payload_data['sub']}"
        except Exception:
            pass

        res = self._request_api("POST", "/assets/v1/get_assets", payload={})
        if res and self._ok(res):
            data = res.get("data") or {}
            # 留一行原始数据日志：后台容量显示异常时，看日志就能判断是字段名不对
            # 还是服务端返回值问题，不用再抓包。
            logger.info(f"光鸭云盘资产原始数据: {json.dumps(data, ensure_ascii=False)[:400]}")
            total = self._pick_int(data, (
                "totalSpaceSize", "totalSpace", "totalSize", "total_space_size", "total",
            ))
            used = self._pick_int(data, (
                "usedSpaceSize", "usedSpace", "usedSize", "useSpaceSize", "used_space_size", "used",
            ))
            if total:
                info["total_space_bytes"] = total
            if used is not None:
                info["used_space_bytes"] = used
            if data.get("svipStatus") == 1:
                info["vip_status"] = 2
            elif data.get("vipStatus") in (1, 3):
                info["vip_status"] = 1
            if info["total_space_bytes"] and not info["used_space_bytes"]:
                logger.warning(
                    "光鸭云盘已用空间读数为 0，请对照上方资产原始数据确认字段名"
                )
        else:
            logger.warning(f"光鸭云盘获取空间信息失败: {str(res)[:200]}")
        # 用 WARNING 级别打一行解析结果：后台"日志"面板默认只显示 WARNING 及以上，
        # 这样用户点一次自检就能直接看到客户端到底解析出多少，不用去翻容器 stdout。
        logger.warning(
            f"光鸭容量解析结果 total={info['total_space_bytes']} "
            f"used={info['used_space_bytes']} vip={info['vip_status']}"
        )
        return info
