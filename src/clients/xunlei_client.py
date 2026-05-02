import requests
import json
import time
import re


class XunleiFinalBot:
    def __init__(self, access_token, captcha_sign, user_id):
        self.access_token = access_token
        self.captcha_sign = captcha_sign
        self.user_id = user_id  # 刚才抓包看到的 1409868053

        self.client_id = "Xqp0kJBXWhwaTpB6"
        self.device_id = "579dad27c8640632b55cd2eaa3df9d47"

        self.base_headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'x-client-id': self.client_id,
            'x-device-id': self.device_id,
        }

    def _get_fresh_token(self, action):
        """核心：用 Sign 自动换取最新的 Token"""
        url = "https://xluser-ssl.xunlei.com/v1/shield/captcha/init"
        payload = {
            "client_id": self.client_id,
            "action": action,
            "device_id": self.device_id,
            "meta": {
                "package_name": "pan.xunlei.com",
                "client_version": "1.92.23",
                "captcha_sign": self.captcha_sign,
                "timestamp": str(int(time.time() * 1000)),
                "user_id": self.user_id
            }
        }
        res = requests.post(url, json=payload, headers=self.base_headers).json()
        token = res.get('captcha_token')
        if not token:
            print(f"❌ 换取 Token 失败，Sign 可能已过期: {res}")
        return token

    def run_transfer(self, target_url):
        # 1. 自动生成第一个操作的 Token
        token = self._get_fresh_token("get:/drive/v1/share")
        headers = self.base_headers.copy()
        headers['Authorization'] = f"Bearer {self.access_token}"
        headers['x-captcha-token'] = token

        # 2. 解析链接
        sid = re.search(r'/s/([^?#/]+)', target_url).group(1)
        pwd = re.search(r'pwd=([a-zA-Z0-9]+)', target_url).group(1) if 'pwd=' in target_url else ""

        # 3. 获取详情
        print(f"📡 正在获取资源信息...")
        detail = requests.get(f"https://api-pan.xunlei.com/drive/v1/share?share_id={sid}&pass_code={pwd}",
                              headers=headers).json()

        if 'pass_code_token' not in detail:
            print(f"❌ 获取失败: {detail}")
            return

        # 4. 执行转存 (需要重新换一个 Restore 动作的 Token)
        print(f"📦 正在转存文件: {detail['files'][0]['name']}")
        headers['x-captcha-token'] = self._get_fresh_token("post:/drive/v1/share/restore")

        restore_payload = {
            "parent_id": "", "share_id": sid, "pass_code_token": detail['pass_code_token'],
            "file_ids": [f['id'] for f in detail['files']], "specify_parent_id": True
        }
        res_restore = requests.post("https://api-pan.xunlei.com/drive/v1/share/restore", json=restore_payload,
                                    headers=headers).json()

        # 5. 检查结果 (空间不足或异步等待)
        if 'error' in res_restore:
            print(f"❌ 转存失败: {res_restore.get('error_description')}")
            return

        print("✅ 任务已提交！请在 5 分钟后检查云盘。")


# --- 填入你的真实数据 ---
# 注意：captcha_sign 建议使用你刚抓到的那个
ACCESS_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjFhOGQ5NWE3LTEyN2ItNDQwNC1hY2E5LWEyNWVkMGVlNzE0ZSJ9.eyJpc3MiOiJodHRwczovL3hsdXNlci1zc2wueHVubGVpLmNvbSIsInN1YiI6IjE0MDk4NjgwNTMiLCJhdWQiOiJYcXAwa0pCWFdod2FUcEI2IiwiZXhwIjoxNzY2NjIwNTM5LCJpYXQiOjE3NjY1NzczMzksImF0X2hhc2giOiJyLmZoakdVZWw2UjlPU0YtT29wVG1wZnciLCJzY29wZSI6InByb2ZpbGUgcGFuIHNzbyB1c2VyIiwicHJvamVjdF9pZCI6IjJydms0ZTNna2RubDd1MWtsMGsiLCJtZXRhIjp7ImEiOiIwdlo0akhhdWF1WC9KY0pjRzNHbDhqYUU1TjVBeGwraGxjK25nWWdkZU5rPSJ9fQ.Gw-ryA1QT2zj1FXXd9w6Hu8w7lb1m1EVIacx6A0XaEnwqDJ7rBrgjEljP35mYcY1IV5q3_cWhnq80TWjIOF5O6cC38Zux6rKIFLjD1ncvwvbW3pchKduMutDkvMcRJZNV8cQrgO-0bHuVDuYMuXBOTjIa_uV2IbKcAeA8Fx26Ie_MCCxPMd3zMFxFOKMfk_q-nRgIxDpwxb5aqnKB6ECFHAanvprAtVa0hx6wLvIeeH3WKSiKiOAZKwvaTjEkmdD_46fZYUX4gd1EFwMNkf6xM76nocnuCZEq9ZiZRqjJeDFV085FO2N3K0dhmuWWId8ZkRBSdqeMBNQgNSgZD-Kjg"
CAPTCHA_SIGN = "1.6da918dc3271201eba8168c3b0f2ca8e"
USER_ID = "1409868053"

bot = XunleiFinalBot(ACCESS_TOKEN, CAPTCHA_SIGN, USER_ID)
bot.run_transfer("https://pan.xunlei.com/s/VOMBtWJjnAyAySJUsQTGuMdhA1?pwd=fprf")