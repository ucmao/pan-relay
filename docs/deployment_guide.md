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

## ⏰ 内置后台定时任务说明

服务启动时，内置的 `APScheduler` 调度器会自动在后台并发执行以下定时工作：

| 任务名称 | 执行周期 | 功能说明 |
| :--- | :--- | :--- |
| **`cleanup_expired_temp_shares`** | 每 30 分钟 | 扫描并物理删除已过期的动态转存临时分享链接 |
| **`cleanup_all_storage`** | 每 12 小时 | 根据后台设置的超期保留策略，自动批量清理旧转存落盘资源 |
| **`scheduled_account_keepalive_job`** | 每 24 小时 | 对多账号池中所有有效账号执行静默保活与 Token 自动续期 |
| **`scheduled_resource_health_audit_job`** | 每 24 小时 | 对库内存量资源进行免登录批量健康巡检，标记死链与失效状态 |
