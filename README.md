<div align="center">

# 🎵 CloudMusic Manager

**网易云音乐人自动发布动态面板**

每月自动发布 5 次动态，满足网易云音乐人免费领会员条件

[![Docker](https://img.shields.io/badge/Docker-ghcr.io-blue?logo=docker)](https://github.com/lillinlin/Cloudmusic-Manager/pkgs/container/cloudmusic-manager)
[![GitHub](https://img.shields.io/badge/GitHub-lillinlin-black?logo=github)](https://github.com/lillinlin/Cloudmusic-Manager)

</div>

---

## ✨ 功能

- 📅 每月 1-5 号自动发布动态，未完成时自动补发
- 🗑 下月 1 号自动删除上月发的动态
- 👥 支持多账号，各自独立管理
- 📱 网页扫码登录，无需手动填写 Cookie
- ⚠️ Cookie 失效时面板红色警告 + Telegram 推送
- 🔔 Telegram 通知：发布成功 / 失败 / 月度完成 / Cookie 过期
- ⚙️ 所有配置在面板中完成，无需修改任何文件

---

## 🚀 一键安装

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/lillinlin/Cloudmusic-Manager/main/install.sh)
```

脚本会自动完成：
- 安装 Docker（如未安装）
- 拉取镜像并启动容器（安装到 `/app/cloudmusic`）
- 交互式配置 Nginx 反代 + SSL 证书

---

## 🛠 手动安装

### 1. 创建目录

```bash
mkdir -p /app/cloudmusic/data
cd /app/cloudmusic
```

### 2. 创建 docker-compose.yml

```yaml
services:
  cloudmusic:
    image: ghcr.io/lillinlin/cloudmusic-manager:latest
    container_name: cloudmusic
    restart: unless-stopped
    ports:
      - "127.0.0.1:9000:9000"
    volumes:
      - ./data:/app/data
```

### 3. 启动

```bash
docker compose up -d
```

### 4. 配置 Nginx

将以下内容保存为 `/etc/nginx/sites-available/cloudmusic`，并按实际情况替换域名和证书路径：

```nginx
server {
    listen 443 ssl;
    server_name cm.example.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/cert.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 禁止访问数据目录
    location ^~ /data/ {
        deny all;
        return 403;
    }

    # 禁止访问隐藏文件
    location ~ /\. {
        deny all;
        return 403;
    }

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }
}

server {
    listen 80;
    server_name cm.example.com;
    return 301 https://$host$request_uri;
}
```

```bash
ln -s /etc/nginx/sites-available/cloudmusic /etc/nginx/sites-enabled/cloudmusic
nginx -t && systemctl reload nginx
```

---

## ⚙️ 首次使用

1. 浏览器打开面板（`https://你的域名` 或 `http://服务器IP:9000`）
2. 进入「设置」，填写：
   - **API 地址**：你部署的 NeteaseCloudMusicApi 地址
   - **账号列表**：账号名称（唯一标识，用于区分多账号）
   - **Telegram**（可选）：Bot Token 和 Chat ID
3. 点「保存配置」
4. 在账号卡片点「扫码登录」，用网易云 App 扫码
5. 登录成功后自动开始运行

---

## 📋 常用命令

```bash
# 查看实时日志
docker logs -f cloudmusic

# 重启服务
cd /app/cloudmusic && docker compose restart

# 更新到最新镜像
cd /app/cloudmusic && docker compose pull && docker compose up -d

# 停止服务
cd /app/cloudmusic && docker compose down

# 卸载（保留数据）
cd /app/cloudmusic && docker compose down

# 彻底卸载（含数据）
cd /app/cloudmusic && docker compose down && rm -rf /app/cloudmusic
```

---

## 📁 数据目录

所有数据存储在 `/app/cloudmusic/data/`：

| 文件 | 说明 |
|------|------|
| `config.json` | 配置文件（面板保存后自动生成） |
| `state.json` | 运行状态（发布记录、event_id） |
| `cookie_账号名.txt` | 各账号的登录 Cookie |

> 备份只需备份 `data/` 目录

---

## 🔔 Telegram 通知配置

1. 向 [@BotFather](https://t.me/BotFather) 发送 `/newbot` 创建机器人，获取 **Token**
2. 向 [@userinfobot](https://t.me/userinfobot) 发送任意消息，获取你的 **Chat ID**
3. 在面板设置中填入即可

通知类型：

| 通知 | 触发时机 |
|------|----------|
| ✅ 发布成功 | 每次动态发布后 |
| ❌ 发布失败 | API 返回错误时 |
| ⚠️ Cookie 过期 | 检测到登录失效时 |
| 🗑 删除完成 | 月初删除上月动态后 |
| 🎉 月度完成 | 本月 5 次全部发完时 |

---

## 🏗 自行构建

```bash
git clone https://github.com/lillinlin/Cloudmusic-Manager.git
cd Cloudmusic-Manager

# 构建前端
cd frontend && npm install && npm run build && cd ..

# 构建镜像
docker build -t cloudmusic-manager .

# 运行
docker run -d \
  --name cloudmusic \
  -p 127.0.0.1:9000:9000 \
  -v $(pwd)/data:/app/data \
  cloudmusic-manager
```

---
