<div align="center">

<img src="static/images/hero_search_top.webp" width="480" height="auto" alt="Pan-Relay Logo">

**基于 Python 的多网盘聚合中继与自动化变现管理系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/) [![Framework](https://img.shields.io/badge/Framework-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![Database](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/) [![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#-部署指南) [![Telegram](https://img.shields.io/badge/Telegram-Ready-26A5E4?logo=telegram&logoColor=white)](#-部署指南) [![Support](https://img.shields.io/badge/Support-5%20Major%20Clouds-brightgreen.svg)](#-支持的网盘矩阵)

<p align="center">
  <a href="#-核心业务逻辑">业务逻辑</a> •
  <a href="#-支持的网盘矩阵">支持网盘</a> •
  <a href="#-部署指南">部署指南</a> •
  <a href="#-网盘凭证说明">凭证配置</a> •
  <a href="#-开放接口可选">开放接口</a> •
  <a href="#-项目结构">项目结构</a> •
  <a href="#-联系作者">联系作者</a>
</p>

Pan-Relay 是一款专为网盘推广员、资源站长打造的**全自动化收益与聚合分发系统**。

通过“资源聚合 -> 自动转存 -> 链接洗白 -> 裂变分发”的闭环，助你实现拉新与转存收益最大化。

**内置 SQLite 数据库，零配置一键启动；原生集成 Telegram 公开频道与多上游 API 搜索。**

</div>

---

## 💎 核心业务逻辑

* **自动化链接洗白**：已接入 **夸克网盘、百度网盘、阿里云盘、UC网盘、迅雷网盘**。批量导入他人分享链接，系统自动执行“转存至个人盘 -> 生成个人分享链 -> 替换入库”，实现收益权转移。
* **私有资源库管理**：资源统一存入本地 SQLite 数据库，支持后台批量增删查改、按类型标注、关键词检索及一键导出 Excel，方便全网分发。
* **多渠道聚合搜索**：
  * **前台搜索**：极简响应式搜索首页，优先展示内部收益资源，随后并发聚合 Telegram 公开频道及第三方 API 搜索结果。
  * **公开接口**：提供标准 RESTful JSON 搜索接口，无缝对接公众号、小程序、微信机器人或资源导航站。

## ✨ 项目特点

* **零外部依赖**：持久化层内置 SQLite 数据库，自带 WAL 模式与并发读优化，无需安装配置 MySQL 等外部服务。
* **开箱即用**：应用启动时**自动检测并初始化表结构与 16+ 预置 API 搜索源**，克隆源码或运行 Docker 即可直接启动。
* **免凭证 TG 搜索**：直接抓取 Telegram 公开频道 Web 预览页，无需申请 Bot Token 或海外账号，自动提取提取码并拼接访问链接。
* **容器化部署**：提供精简轻量 Dockerfile 与 Docker Compose 编排，支持数据持久化挂载与健康检查。

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

> 💡 **提示**：如需自定义后台密码或 TG 代理，可复制 `cp .env.example .env` 后按需修改。

---

## ⚙️ 网盘凭证说明

登录管理后台（`/admin`）进入 **配置中心 -> 云盘凭证** 即可配置各平台登录态：

* **夸克 / 百度 / UC 网盘**：登录网页版，从浏览器开发者工具（F12）网络请求标头中复制完整 `Cookie` 填入。
* **阿里云盘**：从登录会话中提取并填入 `refresh_token`。
* **迅雷网盘**：需同时填入 `Refresh Token`、`Captcha Sign` 与 `User ID` 三项参数（缺一不可）。

> 💡 **安全提示**：所有凭证仅在服务端本地存储，用于自动化转存与动态出链，绝不上传至任何第三方。

---

## 🔌 开放接口（可选）

系统提供轻量标准搜索接口，便于接入微信公众号、机器人或外部导航站：

```http
GET /api?keyword={关键词}&cloud_name={可选网盘平台}&limit=20
```

响应示例：
```json
{
  "success": true,
  "total": 1,
  "results": [
    {
      "source": "hot",
      "name": "凡人修仙传.4K",
      "share_link": "https://pan.quark.cn/s/xxxx",
      "cloud_name": "夸克网盘"
    }
  ]
}
```

---

## 📂 项目结构

```text
pan-relay/
├── app.py                     # 应用主入口 (Flask 路由注册与调度器启动)
├── Dockerfile                 # Docker 轻量镜像构建定义
├── docker-compose.yml         # 容器化一键部署编排
├── requirements.txt           # Python 核心依赖清单
├── schema_sqlite.sql          # SQLite 数据库表结构与预置数据
├── src/                       # 应用核心包
│   ├── clients/               # 夸克/百度/阿里/UC/迅雷底层 API 客户端
│   ├── configs/               # 应用配置与日志管理
│   │   ├── app_config.py      # 环境变量与核心配置读取
│   │   └── logging_setup.py   # 日志格式与输出配置
│   ├── db/                    # SQLite 数据库交互层 (resources, api_configs, credentials 等)
│   ├── models/                # 搜索结果等领域数据模型 (SearchResultItem)
│   ├── routes/                # Web 蓝图路由层
│   │   ├── search_routes.py   # 前台搜索与公开 API 路由
│   │   ├── resource_routes.py # 后台私有资源管理路由
│   │   ├── api_config_routes.py # 第三方 API 搜索源管理路由
│   │   ├── system_config_routes.py # 系统配置与网盘凭证管理
│   │   └── auth_routes.py     # 后台鉴权与 JWT 认证
│   ├── services/              # 搜索聚合服务、TG 爬虫、转存调度
│   ├── utils/                 # 权限校验、网盘链接正则提取等通用工具
│   └── pan_operator.py        # 核心转存与链接洗白操作引擎
├── static/                    # 前端 CSS、JS 及图片素材
├── templates/                 # Jinja2 HTML 页面模板
└── tests/                     # 自动化单元测试套件
```

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
