<div align="center">

<img src="static/images/hero_search_top.webp" width="auto" height="280" alt="小青搜剧 Logo">

**全能网盘推广与自动化变现管理系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/) [![SQLite](https://img.shields.io/badge/database-SQLite-blue.svg)](https://www.sqlite.org/) [![Support](https://img.shields.io/badge/support-Quark%20%7C%20Baidu%20%7C%20Aliyun%20%7C%20UC%20%7C%20Xunlei-brightgreen.svg)](#💾-网盘支持矩阵)

<p align="center">
  <a href="#-在线演示-demo">在线演示</a> •
  <a href="#-核心变现逻辑">变现逻辑</a> •
  <a href="#-快速开始">部署指南</a> •
  <a href="https://github.com/ucmao/search-ucmao/issues">提交Bug</a>
</p>

小青搜剧是一款专为网盘推广员、资源站长打造的**自动化收益工具**。<br>通过“资源聚合 -> 自动转存 -> 链接洗白 -> 裂变分发”的闭环，助你实现拉新与转存收益最大化。

</div>

---

## 🌐 在线演示 (Demo)

为了方便您快速了解系统逻辑，我们提供了全功能的在线测试环境：

* **🔍 用户搜索端**：[https://so.ucmao.cn](https://so.ucmao.cn)
* **⚙️ 管理后台**: [https://so.ucmao.cn/admin](https://so.ucmao.cn/admin)
  * **管理账号**: `admin`
  * **管理密码**: `admin123`

> **安全提示**：演示环境仅供功能体验。为了您的账号安全，请勿在演示站后台填入您真实的云盘凭证。

---

## 💎 核心变现逻辑

* **自动化链接洗白**：已接入 **夸克网盘、百度网盘、阿里云盘、UC网盘、迅雷网盘**。批量导入他人分享链接，系统自动执行“转存至个人盘 -> 生成个人分享链 -> 替换入库”，实现收益权转移。
* **私有资源池**：资源存入本地 SQLite 数据库（开箱即用，免配数据库），支持后台批量管理、资源标注及一键导出 Excel，方便全网分发。
* **多维分发模式**：
    * **前台搜索**：极简搜索首页，优先展示您的收益链接，后聚合展示第三方 API 结果。
    * **标准接口**：提供公开 API，可对接微信机器人、小程序或其他资源导航站。

---

## 💾 网盘支持矩阵

| 平台 | 识别状态 | 自动转存/洗白 | 动态查看/临时分享 | 凭证类型 |
| :--- | :------: | :-----------: | :---------------: | :------- |
| **夸克网盘** | ✅ 识别 | ✅ 已支持 | ✅ 已支持 | Cookie |
| **百度网盘** | ✅ 识别 | ✅ 已支持 | ✅ 已支持 | Cookie |
| **阿里云盘** | ✅ 识别 | ✅ 已支持 | ✅ 已支持 | Refresh Token |
| **UC网盘** | ✅ 识别 | ✅ 已支持 | ✅ 已支持 | Cookie |
| **迅雷网盘** | ✅ 识别 | ✅ 已支持 | ✅ 已支持 | Refresh Token + Captcha Sign + User ID |
| **其他网盘** | ✅ 识别 | 🚧 持续开发中 | 🚧 持续开发中 | 视平台而定 |


---

## 🔌 API 接口说明

**公共搜索接口**：`GET /api`

| 参数 | 描述 | 示例值 |
| --- | --- | --- |
| `keyword` | 搜索关键词 | `凡人修仙传` |
| `cloud_name` | 筛选网盘 | `夸克网盘` |
| `type` | 资源类型 | `电影` |
| `limit` | 返回数量 | `100` |
| `sort` | 排序方式 | `default`(时间倒序) / `random`(随机) / `asc` / `desc` |

返回示例：

```json
{
  "success": true,
  "total": 2,
  "results": [
    {
      "source": "hot",
      "name": "凡人修仙传",
      "share_link": "https://pan.quark.cn/s/xxxx",
      "cloud_name": "夸克网盘"
    }
  ]
}
```

---

## 🚀 快速开始

### 0. 环境要求

* **Python**: 3.8 及以上版本
* **数据库**: 内置 SQLite（无需安装配置任何数据库软件，开箱即用）

### 1. 获取源码

首先，将项目克隆到本地服务器或电脑：

```bash
git clone https://github.com/ucmao/search-ucmao.git
cd search-ucmao
```

### 2. 创建虚拟环境 (推荐)

```bash
# 创建虚拟环境
python3 -m venv venv
# 激活环境 (Linux/Mac)
source venv/bin/activate
# 激活环境 (Windows)
# venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 环境配置 (.env)

将项目根目录的 `.env.example` 文件重命名为 `.env` 文件，填入以下基础配置：

```ini
# 系统密钥 (用于JWT签名)
SECRET_KEY = 请替换为你的JWT签名密钥（如随机字符串）

# SQLite 数据库配置（可选，留空则默认保存在 data/ucmao_search.db）
# SQLITE_DB_PATH = data/ucmao_search.db

# Telegram 公开频道搜索（多个频道使用英文逗号分隔）
TG_SEARCH_ENABLED = true
TG_CHANNELS = tgsearchers7,tgsearchers3,tgsearchers6
TG_SEARCH_TIMEOUT = 10
TG_SEARCH_MAX_WORKERS = 4
# 海外服务器通常留空；无法直连 t.me 时填写 HTTP/SOCKS5 代理
TG_PROXY =

# 管理员账号配置
ADMIN_USERNAME = admin
ADMIN_PASSWORD = 请替换为你的管理员密码
```

Telegram 搜索直接请求公开频道页面 `https://t.me/s/<频道>?q=<关键词>`，不需要
Bot Token、`api_id` 或 Telegram 账号。部署服务器必须能够访问 `t.me`；失效、私有或
无法提供公开预览的频道会被自动跳过。

> **无需手动建库**：应用启动时会**自动创建 SQLite 数据库并初始化预置搜索源**，零配置直接运行。

### 5. 启动应用

```bash
python app.py
```

访问 `http://localhost:5004` 即可进入系统。

---

## ⚙️ 部署后第一件事

启动成功后，请先登录后台完成以下配置：

1. 进入 `配置中心`
2. 填写你准备启用的网盘凭证
3. 保存后再去 `我的资源管理` 测试转存入库
4. 最后去前台搜索页测试动态查看

---

## 🔐 云盘凭证说明

项目后台现在统一使用“云盘凭证”概念，而不再只限定为 Cookie。不同平台需要填写的内容如下：

| 平台 | 后台字段 | 说明 |
| --- | --- | --- |
| 百度网盘 | `百度网盘 Cookie` | 登录网页版后复制整段 Cookie |
| 夸克网盘 | `夸克网盘 Cookie` | 登录网页版后复制整段 Cookie |
| 阿里云盘 | `阿里云盘 Refresh Token` | 使用阿里云盘登录态提取 refresh_token |
| UC网盘 | `UC网盘 Cookie` | 登录网页版后复制整段 Cookie |
| 迅雷网盘 | `Refresh Token` + `Captcha Sign` + `User ID` | 3 个字段必须同时填写，缺一不可 |

---

## 💡 如何获取 Cookie / Token？

### 百度网盘 / 夸克网盘 / UC 网盘 Cookie

1. **登录网页版**：在浏览器打开对应平台官网并登录。
2. **进入开发者模式**：按下 `F12`，切换到 **Network (网络)** 标签页。
3. **刷新页面**：按 `F5` 刷新，在左侧列表中找到第一个请求。
4. **复制 Cookie**：在右侧 **Headers (标头)** 中找到 `Cookie:` 字段，复制整段字符串。
5. **完成配置**：登录后台，进入 `配置中心`，粘贴保存。

### 阿里云盘 Refresh Token

阿里云盘不是直接使用 Cookie，而是使用 `refresh_token`。你需要通过自己的抓包方式或现有工具提取登录态中的 refresh token，然后填入后台的 `阿里云盘 Refresh Token`。

### 迅雷网盘三件套

迅雷网盘需要同时准备：`refresh_token`、`captcha_sign`、`user_id`

---

## 📂 项目结构

```text
search-ucmao/
├── app.py                # 程序入口
├── configs/              # 应用与日志配置
├── routes/               # 路由层 (API、认证、搜索、资源管理)
├── src/
│   ├── clients/          # 网盘底层客户端 (夸克/百度/阿里/UC/迅雷)
│   ├── db/               # 数据库交互层 (DAO模式)
│   ├── services/         # 业务逻辑层 (API聚合、资源处理)
│   └── pan_operator.py   # 核心操作器：执行转存与洗白逻辑
├── templates/            # 前端页面模板
├── static/               # 静态资源 (CSS/JS)
├── utils/                # 工具类 (权限校验、链接识别)
└── schema.sql            # 数据库初始化脚本

```

---

## 📩 联系作者

如果您在安装、使用过程中遇到问题，或有定制需求，请通过以下方式联系：

* **微信**：csdnxr
* **QQ**：294323976
* **邮箱**：leoucmao@gmail.com
* **Bug反馈**：[GitHub Issues](https://github.com/ucmao/search-ucmao/issues)

---

## ⚖️ 开源协议 & 免责声明

1. 本项目基于 **[MIT LICENSE](LICENSE)** 协议开源。
2. **免责声明**：本工具仅供技术交流学习，严禁用于任何非法目的。因使用本工具造成的任何账号封禁或法律风险，均与原作者无关。

**小青搜剧** - 让每一份网盘资源都为你创造价值。

---
