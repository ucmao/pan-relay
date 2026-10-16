<div align="center">

<img src="static/images/hero_search_top.webp" width="480" height="auto" alt="Pan-Relay Logo">

**基于 Python 的多网盘聚合与自动化变现管理系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/) [![Framework](https://img.shields.io/badge/Framework-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![Database](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/) [![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#-部署指南) [![REST API](https://img.shields.io/badge/REST__API-v1.0-purple.svg)](#-开放-rest-api-与无头部署) [![Support](https://img.shields.io/badge/Support-8%20Major%20Clouds-brightgreen.svg)](#-支持的网盘矩阵)

<p align="center">
  <a href="#-为什么需要-pan-relay">核心价值</a> •
  <a href="#-支持的网盘矩阵">支持网盘</a> •
  <a href="#-部署指南">部署指南</a> •
  <a href="#-开放-rest-api-与无头部署">开放 API</a> •
  <a href="#-网盘凭据快速配置">凭据配置</a> •
  <a href="#-联系作者">联系作者</a>
</p>

Pan-Relay 是一款专为网盘推广员、资源站长打造的**全自动化收益与聚合分发系统**。

通过“资源聚合 → 智能号池调度 → 自动转存 → 换链变现 → 优先分发”全链路闭环，将全网外部公开资源高效转换为您的专属收益链接，成倍放大拉新与转存收益。

</div>

---

## 💡 为什么需要 Pan-Relay？

在网盘拉新推广、影视/学习资源站运营、或搭建私域社群机器人时，站长和推广员通常面临以下**核心痛点**：

1. **手动转存换链耗时耗力**：全网搜集了海量热门资源，却需要人工逐个登录网盘、转存、复制分享链，效率极低且无法应对大批量爆发式需求；
2. **为他人作嫁衣（引流与广告污染）**：上游公开分享的压缩包、文档中往往充斥着其他站长的引流水印、广告文件，直接分发等于帮别人拉新；
3. **单账号容量报警与风控封禁**：单个网盘空间有限，高频转存极易触发平台风控熔断或限速，缺乏跨账号/多网盘的负载分流机制；
4. **链接失效无法感知**：外部引用的第三方链接极易被举报或和谐，没有免登录的自动化实时测活机制，导致用户大量流失；
5. **系统封闭难以与外部业务打通**：传统工具通常与特定前端强绑定，缺乏标准化的 OpenAPI，难以快速接入自建的小程序、Telegram Bot 或移动端 APP。

---

### 🎯 Pan-Relay 的破局方案（变现与转存闭环）

* **企业级多账号池调度**：已接入**夸克网盘、百度网盘、阿里云盘、UC网盘、迅雷网盘、光鸭云盘、悟空网盘、移动云盘** 8 大主流网盘，支持无限添加子账号，内置加权轮询负载均衡、容量熔断、自动故障转移与后台静默保活。
* **自动化转存与净网植入**：
  * **模式一：批量转存 (入库)**：后台批量导入外部链接，自动“多号分流转存 $\rightarrow$ 智能过滤垃圾广告 $\rightarrow$ 植入站长引流信息 $\rightarrow$ 换链持久化入库”，打造私有核心收益资源库。
  * **模式二：实时转存 (出链)**：前台或 API 搜索外部资源时按需实时调用账号池转存并生成收益链接返回给用户，过期由系统定时任务自动清理释放空间。
* **私有收益资源库**：零外部数据库依赖（内置轻量 SQLite），支持后台批量导入、转存、增删改查、类型标注、精准账号关联与 Excel 导出。
* **全网多源聚合搜索**：优先展示私有收益库，并并发聚合第三方 API、115+ Telegram 公开频道（免 Token）与 Python 插件源，支持异步免登录实时测活。
* **完全解耦与两步走 REST API**：提供规范的 `/api/v1` 开放接口（步骤 1 聚合查询 / SSE 流式推流 $\rightarrow$ 步骤 2 自动转存替换），支持无头模式，秒级对接微信小程序、Web 站与 Telegram 机器人。

> 📖 关于 API 接口源 JMESPath 字段映射、TG 频道免密抓取与编写 Python 搜索插件，详见 [搜索源体系与插件扩展指南](docs/plugins_and_sources_guide.md)。

---

## 💾 支持的网盘矩阵

| 网盘平台 | 自动转存 | 号池调度 | 链接测活 | 凭据保活 | 容量熔断 | 广告净化 | 引流植入 | 过期清理 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **夸克网盘** | ✓ | ✓ | ✓ | - | ✓ | ✓ | ✓ | ✓ |
| **UC 网盘** | ✓ | ✓ | ✓ | - | ✓ | ✓ | ✓ | ✓ |
| **百度网盘** | ✓ | ✓ | ✓ | - | ✓ | ✓ | ✓ | ✓ |
| **阿里云盘** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **迅雷网盘** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **光鸭云盘** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **移动云盘** | ✓ | ✓ | ✓ | ✓ | - | ✓ | ✓ | ✓ |
| **悟空网盘** | ✓ | ✓ | ✓ | - | - | ✓ | ✓ | ✓ |
| **123 云盘** | - | - | ✓ | - | - | - | - | - |
| **115 网盘** | - | - | ✓ | - | - | - | - | - |
| **天翼云盘** | - | - | ✓ | - | - | - | - | - |
| **联通云盘** | - | - | ✓ | - | - | - | - | - |


---

## 🚀 部署指南

### 方式一：Docker 部署（强烈推荐，开箱即用）

内置 SQLite 数据库，无需安装任何外部数据库软件，一键拉起：

```bash
# 1. 克隆代码并进入目录
git clone https://github.com/ucmao/pan-relay.git
cd pan-relay

# 2. 启动服务（自动构建镜像，数据持久化挂载至本地 ./data 目录）
docker compose up -d --build

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

* **前台 Web 搜索**：[http://localhost:5004](http://localhost:5004)
* **管理后台**：[http://localhost:5004/admin](http://localhost:5004/admin)（默认账号 `admin` / 密码 `admin123`）

> 💡 **提示**：如需自定义后台账号密码，可复制 `cp .env.example .env` 后按需修改。

> 📖 关于生产环境 Nginx 反代配置（SSE 支持）、SSL 证书与 SQLite 自动热备份，详见 [生产环境部署与运维手册](docs/deployment_guide.md)。

---

## 🔌 开放 REST API 与无头部署

针对需要接入自定义机器人、小程序、APP 的开发者，`pan-relay` 提供了完善的管理后台开关与标准化 `/api/v1` REST API。

```bash
# 步骤 1 (推荐 / 前端首选): SSE 实时流式响应接口 (0 等待，即时推流避免卡顿)
GET /api/v1/search/stream?keyword={关键词}

# 步骤 1 (传统同步): 一次性 JSON 响应接口
GET /api/v1/search?keyword={关键词}

# 步骤 2：多账号池自动调度转存并替换为专属网盘链接 (内置免登录测活校验)
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

> 📖 完整的 OpenAPI 接口参数、流式 SSE 搜索推流与响应 Payload 字典，详见 [REST API 开发者接入规范](docs/api_v1_docs.md)。

搜索结果会在原有标题、链接、网盘和提取码字段外，按来源提供时间、简介、封面、来源分类及具体来源标识；上游安全的额外字段保存在 `metadata` 中。字段详情和可选性见 API 指南。

---

## ⚙️ 网盘凭据快速配置

登录管理后台（`/admin`）进入 **系统配置 → 网盘账号池** 点击 **【+ 添加账号】** 即可配置各网盘登录态：

* **夸克 / 百度 / UC网盘**：登录网页版，从浏览器开发者工具（`F12`）网络请求标头中复制完整 `Cookie` 填入。
* **阿里云盘**：从登录会话本地存储（Local Storage）中提取并填入 `refresh_token`。
* **迅雷网盘**：
  * **一键提取（推荐，支持 Win / Mac / Linux）**：电脑登录官方迅雷客户端后，在项目根目录运行 `python3 scripts/extract_xunlei_token.py` 即可自动读取并导出。
  * **手动配置**：填入提取的 JSON 凭证或移动端抓包获取的 `refresh_token`。
* **光鸭云盘**：登录网页版提取 `access_token` 或填入 `refresh_token` 凭证。
* **悟空网盘**：从网页端开发者工具中复制网络请求标头中的 `Cookie` 或 Token。
* **移动云盘**：登录 `yun.139.com` 网页版，从请求标头中复制 `Authorization`。

> 📖 详细的多账号配置步骤、完整抓包图文教程与故障自愈机制，详见 [网盘多账号池配置指南](docs/account_pool_guide.md)。

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
