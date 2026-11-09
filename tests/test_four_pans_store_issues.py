import json
import unittest
from unittest.mock import patch, MagicMock

from src.clients.aliyun_client import AliyunPanClient
from src.clients.xunlei_client import XunleiPanClient
from src.clients.uc_client import UcPanClient
from src.clients.guangya_client import GuangyaPanClient


class TestFourPansStoreVerification(unittest.TestCase):
    """
    针对用户反馈的四大网盘（阿里、迅雷、UC、光鸭）转存失败问题进行的系统测试与验证：
    1. 阿里云盘：变量未定义修复、提取码传递、广告过滤回退、新分享创建
    2. 迅雷网盘：粉丝服务器/Docker环境自动降级切换至有效移动端签名体系、提取码传递、异步任务状态兼容
    3. UC网盘：提取码 passcode 正确注入与解析、广告过滤回退、新分享创建
    4. 光鸭云盘：转存后文件 ID 正确匹配、广告过滤清理、新分享创建
    """

    def test_aliyun_store_success_with_pwd_and_ad_clean(self):
        """验证阿里云盘：支持提取码、广告过滤正常工作且 cleaned_file_ids 无未定义异常"""
        with patch.object(AliyunPanClient, "_refresh_access_token"), \
             patch.object(AliyunPanClient, "add_ad"):
            client = AliyunPanClient("fake_token")
            client.drive_id = "test_drive"

            with patch.object(client, "_post_anonymous") as mock_anon, \
                 patch.object(client, "_request") as mock_req, \
                 patch.object(client, "_clean_ad_files_and_folders") as mock_clean:

                mock_anon.return_value = {
                    "file_infos": [{"file_id": "ali_file_1", "name": "剧集01.mp4"}],
                    "share_name": "测试剧集",
                }
                mock_req.side_effect = [
                    {"share_token": "token_123"},
                    {"responses": [{"body": {"file_id": "ali_copied_1"}}]},
                    {"share_url": "https://www.alipan.com/s/new_share_link"},
                ]
                mock_clean.return_value = ["ali_copied_1"]

                fid, title, url = client.store(
                    "https://www.alipan.com/s/abc12345 提取码: 6666",
                    to_dir="root"
                )

                anon_call = mock_anon.call_args[0][1]
                self.assertEqual(anon_call.get("share_pwd"), "6666")

                token_call = mock_req.call_args_list[0][0][2]
                self.assertEqual(token_call.get("share_pwd"), "6666")

                self.assertIsNotNone(fid)
                self.assertEqual(url, "https://www.alipan.com/s/new_share_link")
                self.assertEqual(title, "测试剧集")

    def test_xunlei_captcha_token_fallback_and_store(self):
        """验证迅雷网盘：在非本机/Linux/Docker环境下无本地 Mac db 时，自动降级切换 Android 移动端签名体系"""
        pc_cred = {
            "refresh_token": "xl_refresh_token_test",
            "client_id": "YBJdb1UyFQJwh_nS",
            "device_id": "08c6b0f4b0a64c4f8901413d917eb64c",
            "user_id": "",
        }
        client = XunleiPanClient(pc_cred)

        with patch("os.path.exists", return_value=False), \
             patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"captcha_token": "test_valid_captcha_token", "expires_in": 300}
            mock_post.return_value = mock_resp

            token = client._get_captcha_token("GET:/drive/v1/share")
            self.assertEqual(token, "test_valid_captcha_token")
            sent_json = mock_post.call_args[1]["json"]
            self.assertEqual(sent_json["client_id"], "Xp6vsxz_7IYVw2BB")

    def test_xunlei_store_with_password(self):
        """验证迅雷网盘转存支持提取码以及兼容字符串 progress="100" 的任务完成状态"""
        client = XunleiPanClient({"refresh_token": "token"})
        with patch.object(client, "_get_access_token", return_value="acc_token"), \
             patch.object(client, "_request_pan") as mock_pan, \
             patch.object(client, "add_ad"), \
             patch.object(client, "_clean_ad_files_and_folders", return_value=["new_f1"]):

            mock_pan.side_effect = [
                # 1. GET /drive/v1/share
                {
                    "share_status": "OK",
                    "title": "迅雷电影",
                    "pass_code_token": "pct_123",
                    "files": [{"id": "f_1", "name": "movie.mp4"}],
                },
                # 2. POST /drive/v1/share/restore
                {"restore_task_id": "task_123"},
                # 3. GET /drive/v1/tasks/{task_id} (返回字符串 progress="100")
                {
                    "progress": "100",
                    "status": "TASK_STATUS_COMPLETE",
                    "params": {"file_ids": ["new_f1"]},
                },
                # 4. POST /drive/v1/share (创建新分享)
                {
                    "share_url": "https://pan.xunlei.com/s/new_xl",
                    "pass_code": "8888",
                },
            ]

            fid, title, url = client.store(
                "https://pan.xunlei.com/s/VN12345?pwd=5678",
                password="5678"
            )

            first_call_params = mock_pan.call_args_list[0][1]["params"]
            self.assertEqual(first_call_params.get("pass_code"), "5678")
            self.assertEqual(title, "迅雷电影")
            self.assertIn("https://pan.xunlei.com/s/new_xl", url)

    def test_uc_store_with_passcode(self):
        """验证 UC 网盘提取码正确透传到 v2/detail 接口"""
        client = UcPanClient("fake_uc_cookie")
        with patch.object(client, "_request") as mock_req, \
             patch.object(client, "_wait_task") as mock_wait, \
             patch.object(client, "add_ad"), \
             patch.object(client, "_clean_ad_files_and_folders", return_value=["uc_copied_1"]):

            mock_req.side_effect = [
                # 1. v2/detail
                {"status": 200, "data": {"token_info": {"stoken": "stok_abc"}}},
                # 2. detail
                {"status": 200, "data": {"list": [{"fid": "uc_1", "share_fid_token": "tok_1"}], "share": {"title": "UC视频"}}},
                # 3. save
                {"status": 200, "data": {"task_id": "save_t1"}},
                # 4. get_dir_file before add_ad
                {"status": 200, "data": {"list": []}},
                # 5. create share
                {"status": 200, "data": {"task_id": "share_t1"}},
                # 6. password
                {"status": 200, "data": {"share_url": "https://drive.uc.cn/s/new_uc", "pass_code": "abcd"}},
            ]
            mock_wait.side_effect = [
                {"save_as": {"save_as_top_fids": ["uc_copied_1"]}},
                {"share_id": "share_999"},
            ]

            fid, title, url = client.store(
                "https://drive.uc.cn/s/uc12345?pwd=9999",
                password="9999"
            )

            first_payload = mock_req.call_args_list[0][0][2]
            self.assertEqual(first_payload.get("passcode"), "9999")
            self.assertIn("https://drive.uc.cn/s/new_uc?pwd=abcd", url)

    def test_guangya_store_with_proper_file_id_and_cleaning(self):
        """验证光鸭云盘转存后使用转存后的文件 ID 创建分享并过滤广告"""
        client = GuangyaPanClient("fake_token")
        with patch.object(client, "_request_api") as mock_api, \
             patch.object(client, "add_ad"):
            mock_api.side_effect = [
                # 1. get_share_access_token
                {"code": 0, "msg": "success", "data": {"accessToken": "share_tok_1"}},
                # 2. get_share_page_files_list
                {"code": 0, "msg": "success", "data": {"list": [{"fileId": "ext_fid_999", "fileName": "movie.mkv"}]}},
                # 3. list_dir (before restore)
                {"code": 0, "msg": "success", "data": {"list": [], "total": 0}},
                # 4. restore_share
                {"code": 0, "msg": "success", "data": {"taskId": "task_999"}},
                # 5. get_task_status
                {"code": 0, "msg": "success", "data": {"status": 2}},
                # 6. list_dir (after restore)
                {"code": 0, "msg": "success", "data": {"list": [{"fileId": "my_saved_fid_123", "fileName": "movie.mkv"}], "total": 1}},
                # 7. create share
                {"code": 0, "msg": "success", "data": {"shareUrl": "https://www.guangyapan.com/s/new_gy"}},
            ]
            fid, name, url = client.store("https://www.guangyapan.com/s/gy123?pwd=6666", password="6666")
            share_payload = mock_api.call_args_list[6][1]["payload"]
            self.assertEqual(share_payload.get("fileIds"), ["my_saved_fid_123"])
            self.assertEqual(url, "https://www.guangyapan.com/s/new_gy")
            self.assertEqual(name, "movie.mkv")


if __name__ == "__main__":
    unittest.main()
