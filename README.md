<div align="center">

<img src="static/images/hero_search_top.webp" width="480" height="auto" alt="Pan-Relay Logo">

**基于 Python 的多网盘聚合中继与自动化变现管理系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/) [![Framework](https://img.shields.io/badge/Framework-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![Database](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/) [![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#-部署指南) [![REST API](https://img.shields.io/badge/REST__API-v1.0-purple.svg)](#-开放-rest-api-与无头部署) [![Telegram](https://img.shields.io/badge/Telegram-Ready-26A5E4?logo=telegram&logoColor=white)](#-部署指南) [![Support](https://img.shields.io/badge/Support-8%20Major%20Clouds-brightgreen.svg)](#-支持的网盘矩阵)

<p align="center">
  <a href="#-核心业务逻辑">业务逻辑</a> •
  <a href="#-支持的网盘矩阵">支持网盘</a> •
  <a href="#-部署指南">部署指南</a> •
  <a href="#-开放-rest-api-与无头部署">开放 API</a> •
  <a href="#-网盘凭证说明">凭证配置</a> •
  <a href="#-联系作者">联系作者</a>
</p>

Pan-Relay 是一款专为网盘推广员、资源站长打造的**全自动化收益与聚合分发系统**。

通过‘资源聚合 → 自动转存 → 换链变现 → 优先分发’闭环，将外部资源高效转换为专属收益链接，显著提升拉新与转存收益。

**支持本地资源、第三方API、Telegram公开频道与可扩展插件聚合搜索。支持完全解耦的开放REST API与小程序、APP快速接入。**

</div>

---

## 💎 核心业务逻辑

### 🔄 变现与转存闭环流程

* **自动化转存换链**：已接入**夸克网盘、百度网盘、阿里云盘、UC网盘、迅雷网盘、光鸭云盘、悟空网盘、移动云盘** 8 大主流网盘。
  * **模式一：批量转存 (入库)**：后台批量导入外部链接，自动“转存 $\rightarrow$ 换链 $\rightarrow$ 入库”，构建私有核心收益资源库。
  * **模式二：实时转存 (出链)**：前台或API搜索外部资源时按需实时转存并生成收益链接返回给用户，过期由系统定时任务自动清理释放网盘空间。
* **私有收益资源库**：资源统一存入本地SQLite数据库，支持后台批量导入、转存、增删改查、类型标注、关键词检索和导出，方便持续维护与全网分发。
* **多渠道聚合搜索**：
  * **前台搜索**：优先展示私有资源库中的收益链接，再并发聚合第三方API、Telegram公开频道和搜索插件的结果。
  * **两步走REST API**：提供规范的 `/api/v1` REST接口（步骤1 聚合查询 -> 步骤2 自动转存替换），便于无缝对接微信小程序、Flutter / React Native APP、Telegram机器人或资源导航站。

## ✨ 项目特点

* **8大网盘能力全覆盖**：全量支持目录自动归档、上游垃圾广告文件智能过滤、以及专属引流文件自动植入。
* **REST API独立开关**：前台搜索界面与开放API服务完全解耦，可按需独立启闭，支持作为纯后端中转服务运行。
* **开箱即用**：启动时自动初始化表结构及预置API、TG频道和插件搜索源，支持源码与Docker部署。
* **免凭证TG搜索**：直接抓取Telegram公开频道，无需Bot Token，并自动提取网盘链接与提取码。
* **搜索源可扩展**：后台统一管理API、TG频道和Python搜索插件，支持启停、测试与调度配置。
* **容器化部署**：提供Dockerfile与Docker Compose，支持数据持久化和健康检查。

---

## 💾 支持的网盘矩阵

| 网盘平台 | 转存换链 | 目录归档 | 广告净化 | 引流植入 | 过期清理 | 凭证类型 |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **夸克网盘** | ✓ | ✓ | ✓ | ✓ | ✓ | Cookie |
| **UC 网盘** | ✓ | ✓ | ✓ | ✓ | ✓ | Cookie |
| **百度网盘** | ✓ | ✓ | ✓ | ✓ | ✓ | Cookie |
| **阿里云盘** | ✓ | ✓ | ✓ | ✓ | ✓ | Refresh Token |
| **迅雷网盘** | ✓ | ✓ | ✓ | ✓ | ✓ | Token / Sign / User ID |
| **移动云盘** | ✓ | ✓ | ✓ | ✓ | ✓ | Authorization Token |
| **光鸭云盘** | ✓ | ✓ | ✓ | ✓ | ✓ | Access / Refresh Token |
| **悟空网盘** | ✓ | ✓ | ✓ | ✓ | ✓ | Cookie / Session Token |


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

## 🔌 开放 REST API 与无头部署
 
针对需要接入自定义机器人、小程序、APP的开发者，`pan-relay` 提供了完善的管理后台开关与标准化 `/api/v1` REST API。

### 1. 通道与 API 开关控制

可在管理后台（**系统设置 → API与通道配置**）中进行热配置（即时生效，无需重启）：

- **前台搜索开关**：可开启/关闭前台 Web 搜索界面（关闭后访客访问 `GET /` 自动重定向至登录页 `/login`）。
- **默认参数预设**：灵活配置默认搜索范围（`own` 仅收益库 / `all` 全网并发）、单次结果上限 (`limit`)、死链清洗 (`filter_bad`) 与实时健康探针 (`check_status`)。
- **🔒 防护锁 (Lock) 防穿透**：勾选“锁定”后，外部请求即使显式传参亦无法覆盖站长预设，确保服务器资源安全。
- **转存 API 鉴权密钥**：可配置 `X-API-Key` 保护物理转存接口（`POST /api/v1/transfer`）。

*注：即使关闭前台 Web 界面，系统开放 API、管理后台及定时清理 Worker 依然独立运行。*

---

### 2. 标准两步走 API 交互流程

```bash
# 步骤 1 (强烈推荐 / UI首选): SSE 实时流式响应接口 (0等待，即时推流避免卡顿)
GET /api/v1/search/stream?keyword={关键词}

# 步骤 1 (传统同步): 一次性 JSON 响应接口
GET /api/v1/search?keyword={关键词}

# 步骤 2：转存并替换为专属网盘链接 (内置前置免登录测活校验，若链接失效/空文件夹返回 422 拦截)
POST /api/v1/transfer
Content-Type: application/json
X-API-Key: your_transfer_key

{
  "url": "https://pan.quark.cn/s/raw_public_link",
  "title": "电影标题",
  "netdisk_name": "夸克网盘",
  "skip_check": false
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

📖 完整的开发者API接口参数、流式SSE搜索、12大网盘免登录测活及响应Payload说明，请参阅 [docs/api_v1_docs.md](docs/api_v1_docs.md)。

---

## ⚙️ 网盘凭证说明

登录管理后台（`/admin`）进入 **系统配置 -> 云盘凭证** 即可配置8大网盘平台登录态：

* **夸克/百度/UC 网盘**：登录网页版，从浏览器开发者工具（F12）网络请求标头中复制完整 `Cookie` 填入。
* **阿里云盘**：从登录会话中提取并填入 `refresh_token`。
* **迅雷网盘**：需同时填入 `Refresh Token`、`Captcha Sign` 与 `User ID` 三项参数（缺一不可）。
* **光鸭云盘**：登录网页版提取 `access_token` 或填入 `refresh_token` 凭证。
* **悟空网盘**：从网页端开发者工具中复制网络请求标头中的 `Cookie` 或 Token 字符串。
* **移动云盘**：登录 `yun.139.com` 网页版，从请求标头中复制 `Authorization` 或 `jwtToken`。

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
