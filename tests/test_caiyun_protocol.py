import base64
import json
import unittest
from unittest.mock import MagicMock, patch

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from src.clients.caiyun_client import CaiyunPanClient
from src.clients.caiyun_protocol import SHARE_AES_KEY, decode_share_response, encode_share_payload


class CaiyunProtocolTests(unittest.TestCase):
    def test_share_payload_round_trip(self):
        payload = {"getOutLinkInfoReq": {"linkID": "2yrhPJgg1Nd7g", "pCaID": "root"}}
        raw = base64.b64decode(encode_share_payload(payload))
        body = unpad(AES.new(SHARE_AES_KEY, AES.MODE_CBC, raw[:16]).decrypt(raw[16:]), 16)
        self.assertEqual(json.loads(body), payload)

        response = {"success": True, "data": {"caLst": [{"caId": "folder-1", "caName": "专辑"}]}}
        iv = bytes(range(16))
        ciphertext = AES.new(SHARE_AES_KEY, AES.MODE_CBC, iv).encrypt(pad(json.dumps(response).encode(), 16))
        self.assertEqual(decode_share_response(base64.b64encode(iv + ciphertext)), response)
        self.assertEqual(decode_share_response(json.dumps(response).encode()), response)

    @patch("requests.Session.post")
    def test_public_share_request_uses_new_endpoint(self, post):
        response = MagicMock()
        response.content = b'{"success":true,"code":"0","data":{"caLst":[{"caID":"folder-1"}]}}'
        post.return_value = response

        client = CaiyunPanClient("Basic example")
        result = client.get_share_items("https://yun.139.com/shareweb/#/w/i/2yrhPJgg1Nd7g")

        self.assertEqual(result["data"]["caLst"][0]["caID"], "folder-1")
        args, kwargs = post.call_args
        self.assertIn("/richlifeApp/devapp/IOutLink/getOutLinkInfoV6", args[0])
        self.assertEqual(kwargs["headers"]["Authorization"], "Basic example")
        raw = base64.b64decode(kwargs["data"])
        body = unpad(AES.new(SHARE_AES_KEY, AES.MODE_CBC, raw[:16]).decrypt(raw[16:]), 16)
        self.assertEqual(json.loads(body)["getOutLinkInfoReq"]["linkID"], "2yrhPJgg1Nd7g")

    def test_business_error_is_rejected_even_when_success_true(self):
        self.assertFalse(CaiyunPanClient._ok({"success": True, "code": "9530"}))


if __name__ == "__main__":
    unittest.main()
