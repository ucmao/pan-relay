<div align="center">

<img src="static/images/hero_search_top.webp" width="480" height="auto" alt="Pan-Relay Logo">

**基于 Python 的多网盘聚合中继与自动化变现管理系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/) [![Framework](https://img.shields.io/badge/Framework-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![Database](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/) [![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#-部署指南) [![API Mode](https://img.shields.io/badge/API__ONLY-Supported-purple.svg)](#-API_ONLY-无头模式) [![Telegram](https://img.shields.io/badge/Telegram-Ready-26A5E4?logo=telegram&logoColor=white)](#-部署指南) [![Support](https://img.shields.io/badge/Support-5%20Major%20Clouds-brightgreen.svg)](#-支持的网盘矩阵)

<p align="center">
  <a href="#-核心业务逻辑">业务逻辑</a> •
  <a href="#-支持的网盘矩阵">支持网盘</a> •
  <a href="#-部署指南">部署指南</a> •
  <a href="#-API_ONLY-无头模式与开发者-API">API/无头模式</a> •
  <a href="#-网盘凭证说明">凭证配置</a> •
  <a href="#-联系作者">联系作者</a>
</p>

Pan-Relay 是一款专为网盘推广员、资源站长打造的**全自动化收益与聚合分发系统**。

通过“资源聚合 -> 自动转存 -> 收益链接替换 -> 优先分发”的闭环，将外部资源转化为自己的分享链接，提升拉新与转存收益。

**内置 SQLite 数据库，支持本地资源、第三方 API、Telegram 公开频道与可扩展插件聚合搜索。支持完全解耦的 API_ONLY 无头模式与小程序/APP 快速接入。**

</div>

---

## 💎 核心业务逻辑

* **自动化链接洗白**：已接入 **夸克网盘、百度网盘、阿里云盘、UC 网盘、迅雷网盘**。选择批量转存入库后，系统自动执行“转存至个人盘 -> 生成个人分享链 -> 替换入库”，将外部链接转化为自己的收益链接。
* **私有收益资源库**：资源统一存入本地 SQLite 数据库，支持后台批量导入、转存、增删改查、类型标注、关键词检索和导出，方便持续维护与全网分发。
* **多渠道聚合搜索**：
  * **前台搜索**：优先展示私有资源库中的收益链接，再并发聚合第三方 API、Telegram 公开频道和搜索插件的结果。
  * **动态收益出链**：外部搜索结果可在用户访问时按需转存，生成临时个人分享链；转存失败时自动回退原链接，过期分享由系统定时清理。
  * **两步走 REST API**：提供规范的 `/api/v1` REST 接口（步骤 1 聚合查询 -> 步骤 2 自动转存替换），便于无缝对接微信小程序、Flutter/React Native APP、Telegram 机器人或资源导航站。

## ✨ 项目特点

* **无需外部数据库**：内置 SQLite 与 WAL 模式，无需安装配置 MySQL 等数据库服务。
* **支持API_ONLY无头模式**：支持一键关闭 Web 前前端界面，充当无头（Headless）中转服务，由环境变量或后台自由控制。
* **开箱即用**：启动时自动初始化表结构及预置 API、TG 频道和插件搜索源，支持源码与 Docker 部署。
* **免凭证TG搜索**：直接抓取 Telegram 公开频道，无需 Bot Token，并自动提取网盘链接与提取码。
* **搜索源可扩展**：后台统一管理 API、TG 频道和 Python 搜索插件，支持启停、测试与调度配置。
* **容器化部署**：提供 Dockerfile 与 Docker Compose，支持数据持久化和健康检查。

---

## 💾 支持的网盘矩阵

| 网盘平台 | 识别状态 | 自动转存/洗白 | 动态查看/临时分享 | 凭证类型 |
| :--- | :------: | :-----------: | :---------------: | :------- |
| **夸克网盘** | ✓ | ✓ | ✓ | Cookie |
| **百度网盘** | ✓ | ✓ | ✓ | Cookie |
| **阿里云盘** | ✓ | ✓ | ✓ | Refresh Token |
| **UC网盘** | ✓ | ✓ | ✓ | Cookie |
| **迅雷网盘** | ✓ | ✓ | ✓ | Refresh Token + Captcha Sign + User ID |
| **其他网盘** | ✓ | 🚧 | 🚧 | 视平台而定 |

---

## 🚀 部署指南

### 方式一：Docker 部署（强烈推荐，开箱即用）

内置 SQLite 数据库，无需安装任何数据库软件，一键启动：

```bash
# 1. 克隆代码并进入目录
git clone https://github.com/ucmao/pan-relay.git
cd pan-relay

# 2. 启动服务（自动构建镜像，数据持久化挂载至本地 ./data 目录）
docker compose up -d

# 3. 查看实时运行日志
docker compose logs -f
```

---

### 方式二：本地 Python 环境运行

适用于本地二次开发或无 Docker 环境的宿主机：

```bash
# 1. 创建并激活虚拟环境 (Python 3.8+)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖并启动
pip install -r requirements.txt
python app.py
```

---

### 🌐 服务访问与管理后台

服务启动后，在浏览器直接访问：

* **前台搜索**：[http://localhost:5004](http://localhost:5004)
* **管理后台**：[http://localhost:5004/admin](http://localhost:5004/admin)（默认账号 `admin` / 密码 `admin123`）

> 💡 **提示**：如需自定义后台账号密码，可复制 `cp .env.example .env` 后按需修改；TG 代理、超时和并发数在后台搜索源管理中配置。

---

## 🔌 API_ONLY 无头模式与开发者 API

针对需要接入自定义微信小程序、Mobile APP 或使用无头 (Headless) 模式的开发者，`pan-relay` 提供了完善的环境变量开关与标准化 `/api/v1` REST API。

### 1. 模式环境变量配置

可以通过环境变量控制前后台 UI 开关（可写在 `.env` 或 Docker 环境中）：

| 环境变量 | 示例 | 说明 |
| :--- | :--- | :--- |
| `API_ONLY` | `true` / `1` | 开启无头 API 模式，屏蔽前台 UI，仅作为后端中转 API 运行 |
| `ENABLE_FRONTEND` | `false` / `0` | 独立禁用前台 Web 搜索界面 (`GET /` 返回 API Status JSON) |
| `ENABLE_ADMIN_UI` | `false` / `0` | 独立禁用后台 Web 管理界面 (`/admin/*`) |
| `SEARCH_API_SCOPE` | `own` / `all` | API 搜索默认检索作用域 (`own`: 仅站长收益库 / `all`: 全网并发) |
| `TRANSFER_API_KEY` | `your_key` | API 转存鉴权密钥 (留空表示公开允许转存，设置后客户端请求需携带 `X-API-Key`) |

*注：即使 UI 完全关闭，系统后台的定时清理 Worker（`storage_cleanup_service`）依然会独立正常调度运行。*

---

### 2. 标准两步走 API 交互流程

```bash
# 步骤 1：查询全网与库内聚合资源
GET /api/v1/search?keyword={关键词}&cloud_name={可选网盘}

# 步骤 2：转存并替换为专属网盘链接
POST /api/v1/transfer
Content-Type: application/json

{
  "url": "https://pan.quark.cn/s/raw_public_link",
  "title": "电影标题",
  "netdisk_name": "夸克网盘"
}
```

响应示例：
```json
{
  "success": true,
  "message": "资源转换与链接生成成功",
  "data": {
    "url": "https://pan.quark.cn/s/my_relay_link",
    "mode": "temp_share",
    "netdisk_name": "夸克网盘"
  }
}
```

📖 完整的开发者 API 接口参数、流式 SSE 搜索及响应 Payload 说明，请参阅 [docs/api_v1_docs.md](docs/api_v1_docs.md)。

---

## ⚙️ 网盘凭证说明

登录管理后台（`/admin`）进入 **配置中心 -> 云盘凭证** 即可配置各平台登录态：

* **夸克 / 百度 / UC 网盘**：登录网页版，从浏览器开发者工具（F12）网络请求标头中复制完整 `Cookie` 填入。
* **阿里云盘**：从登录会话中提取并填入 `refresh_token`。
* **迅雷网盘**：需同时填入 `Refresh Token`、`Captcha Sign` 与 `User ID` 三项参数（缺一不可）。

> 💡 **安全提示**：所有凭证仅在服务端本地存储，用于自动化转存与动态出链，绝不上传至任何第三方。

---

## 📩 联系作者

如果您在安装、使用过程中遇到问题，或有定制需求，请通过以下方式联系：

* **微信**：csdnxr
* **QQ**：294323976
* **邮箱**：leoucmao@gmail.com
* **Bug反馈**：[GitHub Issues](https://github.com/ucmao/pan-relay/issues)

---

## ⚖️ 开源协议 & 免责声明

1. 本项目基于 **[MIT LICENSE](LICENSE)** 协议开源。
2. **免责声明**：本工具仅供技术交流与学习研究，严禁用于任何商业侵权或非法目的。因使用本工具造成的任何账号封禁或法律责任，均由使用者自行承担，与原作者无关。
