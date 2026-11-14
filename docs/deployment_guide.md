# pan-relay 生产环境部署与运维指南

本文档介绍 `pan-relay` 在生产服务器上的标准化容器部署、反向代理配置、数据备份与日常运维。

---

## 🚀 方式一：Docker Compose 生产部署（推荐）

### 1. 目录准备与克隆代码

```bash
git clone https://github.com/ucmao/pan-relay.git /opt/pan-relay
cd /opt/pan-relay
```

### 2. 环境变量配置 (`.env`)

复制环境变量模板：
```bash
cp .env.example .env
```

按需编辑 `.env` 文件：
```ini
# 服务端口
PORT=5004

# 系统时区
TZ=Asia/Shanghai

# 管理后台管理员登录凭据 (建议修改默认密码)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=YourStrongPasswordHere

# JWT 安全密钥
SECRET_KEY=your_random_secret_key_here
```

### 3. 启动容器

```bash
# 构建镜像并后台启动容器
docker compose up -d --build

# 检查运行状态与健康检查
docker compose ps

# 查看实时运行日志
docker compose logs -f
```

---

## 🔒 生产环境反向代理配置 (Nginx / HTTPS)

建议在生产环境使用 Nginx 反向代理并配置 SSL 证书。

### Nginx 虚拟主机配置示例

```nginx
server {
    listen 80;
    server_name search.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name search.yourdomain.com;

    # SSL 证书路径
    ssl_certificate /etc/letsencrypt/live/search.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/search.yourdomain.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 客户端上传与请求体限制
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:5004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 支持 SSE 流式搜索推流 (GET /api/v1/search/stream)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
    }
}
```

> ⚠️ **重要提示**：因为系统支持流式搜索接口（SSE：`/api/v1/search/stream`），请务必在 Nginx 中配置 `proxy_buffering off;`，避免服务端推流被 Nginx 缓冲区拦截导致前端卡顿。

---

## 💾 数据持久化与备份策略

所有系统数据（账号池、转存资源、搜索源、系统配置、审计日志）均持久化保存在 SQLite 数据库：
* **数据目录**：`./data/pan_relay.db`
* **日志目录**：`./logs/`

### 自动热备份脚本示例 (crontab)

可配置 Linux 定时任务每天定时备份 SQLite 数据库文件：

```bash
#!/bin/bash
# /opt/scripts/backup_panrelay.sh
BACKUP_DIR="/opt/backups/pan-relay"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

# 使用 sqlite3 命令安全热备份（避免写入冲突）
sqlite3 /opt/pan-relay/data/pan_relay.db ".backup '$BACKUP_DIR/pan_relay_$DATE.db'"

# 清理 30 天前的旧备份
find "$BACKUP_DIR" -type f -name "pan_relay_*.db" -mtime +30 -delete
```

添加至系统定时任务：
```bash
# 每天凌晨 3 点自动备份
0 3 * * * /bin/bash /opt/scripts/backup_panrelay.sh
```

---

## 🌐 出站网络代理（可选）

链接测活、API 搜索源和 Telegram 抓取都会频繁访问第三方服务。为避免服务器 IP 被限流或封禁，可以分别为三类请求配置独立代理，**留空即直连**。三项配置均由前台 Web 与开放 API 两层共用：

| 请求类型 | 生效范围 | 后台入口 | 环境变量 |
| :--- | :--- | :--- | :--- |
| 网盘链接测活 | 前台实时测活、开放 API 测活、转存前置测活、资源库定时巡检 | 系统配置 → 搜索与风控 → 测活网络代理 | `LINK_CHECK_PROXY` |
| API 接口搜索源 | API 源搜索、后台「测试接口」 | 搜索源 → 搜索调度参数设置 | `API_PROXY` |
| Telegram 频道 | TG 频道抓取与连通性测试 | 搜索源 → 搜索调度参数设置 | `TG_PROXY` |

* **地址格式**：`协议://[用户名:密码@]主机:端口`，协议支持 `http`、`https`、`socks5`、`socks5h`（`socks5h` 由代理端解析域名）。
* **住宅代理网关**：服务商提供的固定地址和账号密码可以直接填入。测活每次检测都会新建连接，网关会为每次检测分配新的出口 IP。
* **优先级**：后台保存过（包括保存为空）则以后台为准，否则读取环境变量。
* **不回退直连**：配置了代理时请求一律经代理发出。代理不可用时，测活结果记为「不确定」（不会被判为失效、不会触发死链清理），API 搜索该源返回空结果。
* **不走代理的请求**：插件搜索、网盘转存与账号保活始终直连。网盘账号频繁切换 IP 容易触发异地登录风控。
* **Telegram 提示**：许多住宅代理只提供国内出口 IP，无法访问 Telegram。国内服务器的 TG 代理请单独填写可访问 TG 的代理。

> ⚠️ 请使用以上配置项，不要在容器中设置全局的 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量，否则网盘转存等账号请求也会被代理。

---

## 🔄 版本升级与回滚

### 升级步骤

```bash
cd /opt/pan-relay
git pull
docker compose up -d --build
docker compose logs -f --tail=100
```

服务启动时会自动检查数据库结构版本，需要升级时：

1. 先在 `./data/` 下生成升级前快照，例如 `pan_relay.db.bak-v0-20261114-221000`（最多保留最近 5 份）；
2. 再依次执行数据库迁移，日志中可以看到：

```text
检测到数据库需要升级（v0 → v2），已备份至: /app/data/pan_relay.db.bak-v0-20261114-221000
数据库迁移 v1 完成：基线：补齐历史字段与求片工单表
旧版凭据迁移：导入 3 个网盘账号，跳过 0 个（账号池中已存在该网盘账号）。
数据库迁移 v2 完成：旧版 cookie_config 凭据导入账号池
SQLite 数据库初始化与迁移完成（结构版本 v2）。
```

> 💡 从账号池之前的老版本升级时，原来配置的网盘凭据会自动导入账号池（每个网盘一个「网盘名-账号」）。如果你已经在账号池里手动重新添加过某个网盘，该网盘会被跳过，不会重复。

### 升级失败 / 需要回滚

迁移失败时服务不会启动，日志会提示 `数据库迁移 vX 失败，已回滚，升级前备份位于 ...`。此时数据库停留在上一个成功的版本，数据完好。可以把日志提交到 Issue，或按下面的步骤回到旧版本：

```bash
docker compose down
# 1. 用升级前快照还原数据库（先把当前库留一份）
mv data/pan_relay.db data/pan_relay.db.failed
rm -f data/pan_relay.db-wal data/pan_relay.db-shm
cp data/pan_relay.db.bak-v0-20261114-221000 data/pan_relay.db
# 2. 切回升级前的代码版本
git checkout <旧版本 tag 或 commit>
docker compose up -d --build
```

> ⚠️ 新版本迁移过的数据库不保证能被旧版本代码使用，回滚时请务必同时还原数据库快照。

开发者新增或修改表结构时，请遵循 [数据库迁移开发约定](database_migrations.md)。

---

## ⏰ 内置后台定时任务说明

服务启动时，内置的 `APScheduler` 调度器会自动在后台并发执行以下定时工作：

| 任务名称 | 执行周期 | 功能说明 |
| :--- | :--- | :--- |
| **`cleanup_expired_temp_shares`** | 每 30 分钟 | 扫描并物理删除已过期的动态转存临时分享链接 |
| **`cleanup_all_storage`** | 每 12 小时 | 根据后台设置的超期保留策略，自动批量清理旧转存落盘资源 |
| **`scheduled_account_keepalive_job`** | 默认每 24 小时（后台可配置） | 对多账号池中所有有效账号执行静默保活、Token 自动轮转与容量探测 |
| **`scheduled_resource_health_audit_job`** | 每 24 小时 | 对库内存量资源进行免登录批量健康巡检，标记死链与失效状态 |
