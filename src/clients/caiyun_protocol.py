"""移动云盘新版分享接口的请求体编解码。"""

import base64
import hashlib
import json
import os
import secrets
import string
import time
from typing import Any, Dict
from urllib.parse import quote

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


SHARE_API_BASE = "https://share-kd-njs.yun.139.com/yun-share"
SHARE_AES_KEY = b"PVGDwmcvfs1uV3d1"
PERSONAL_API_BASE = "https://personal-kd-njs.yun.139.com/hcy"
TRANSFER_PATH = "/richlifeApp/devapp/IBatchOprTask/createOuterLinkBatchOprTask"
TASK_PATH = "/richlifeApp/devapp/IBatchOprTask/queryBatchOprTaskDetail"
CREATE_SHARE_URL = "https://yun.139.com/orchestration/personalCloud-rebuild/outlink/v1.0/getOutLink"


def encode_share_payload(payload: Dict[str, Any]) -> str:
    """按网页版协议排序 JSON，并将 IV + AES-CBC 密文编码为 Base64。"""
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    iv = os.urandom(AES.block_size)
    encrypted = AES.new(SHARE_AES_KEY, AES.MODE_CBC, iv).encrypt(pad(body, AES.block_size))
    return base64.b64encode(iv + encrypted).decode("ascii")


def decode_share_response(body: bytes) -> Dict[str, Any]:
    """新版接口正常返回加密文本，错误时也可能返回明文 JSON。"""
    body = body.strip()
    if body.startswith(b"{"):
        result = json.loads(body)
    else:
        raw = base64.b64decode(body, validate=True)
        if len(raw) < AES.block_size * 2 or len(raw) % AES.block_size:
            raise ValueError("移动云盘分享响应长度无效")
        iv, ciphertext = raw[:AES.block_size], raw[AES.block_size:]
        plaintext = unpad(AES.new(SHARE_AES_KEY, AES.MODE_CBC, iv).decrypt(ciphertext), AES.block_size)
        result = json.loads(plaintext)
    if not isinstance(result, dict):
        raise ValueError("移动云盘分享响应不是 JSON 对象")
    return result


def mcloud_sign(payload: Dict[str, Any], timestamp: str = "", nonce: str = "") -> str:
    """生成新版个人云及创建分享接口所需的签名请求头。"""
    timestamp = timestamp or time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    nonce = nonce or "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    # requests.post(json=...) 使用 json.dumps 的默认空格和 ASCII 转义；签名必须与请求体一致。
    body = json.dumps(payload)
    encoded = quote(body, safe="")
    sorted_body = base64.b64encode("".join(sorted(encoded)).encode("utf-8"))
    body_md5 = hashlib.md5(sorted_body).hexdigest()
    nonce_md5 = hashlib.md5(f"{timestamp}:{nonce}".encode("utf-8")).hexdigest()
    signature = hashlib.md5((body_md5 + nonce_md5).encode("ascii")).hexdigest().upper()
    return f"{timestamp},{nonce},{signature}"
