#!/bin/bash
set -e

# ═══════════════════════════════════════════════
#   CloudMusic Manager 一键安装脚本
#   https://github.com/lillinlin/Cloudmusic-Manager
# ═══════════════════════════════════════════════

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

IMAGE="ghcr.io/lillinlin/cloudmusic-manager:latest"
INSTALL_DIR="/opt/cloudmusic"
CONTAINER="cloudmusic"
PORT=9000

log()     { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info()    { echo -e "${BLUE}[i]${NC} $1"; }
section() { echo -e "\n${CYAN}${BOLD}── $1 ──${NC}"; }

banner() {
cat << 'EOF'
  ____  _                 _   __  __           _
 / ___|| | ___  _   _  __| | |  \/  |_   _ ___(_) ___
| |    | |/ _ \| | | |/ _` | | |\/| | | | / __| |/ __|
| |___ | | (_) | |_| | (_| | | |  | | |_| \__ \ | (__
 \____||_|\___/ \__,_|\__,_| |_|  |_|\__,_|___/_|\___|

         Manager  —  自动分享面板
EOF
echo -e "${CYAN}         https://github.com/lillinlin/Cloudmusic-Manager${NC}\n"
}

# ── 检查 root ────────────────────────────────
check_root() {
    [[ $EUID -ne 0 ]] && error "请使用 root 权限运行：sudo bash install.sh"
}

# ── 检查/安装 Docker ─────────────────────────
check_docker() {
    section "检查 Docker"
    if command -v docker &>/dev/null; then
        log "Docker 已安装：$(docker --version)"
    else
        warn "未检测到 Docker，正在自动安装…"
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
        log "Docker 安装完成"
    fi

    if ! docker compose version &>/dev/null; then
        warn "未检测到 Docker Compose Plugin，正在安装…"
        apt-get install -y docker-compose-plugin 2>/dev/null || \
        yum install -y docker-compose-plugin 2>/dev/null || \
        warn "请手动安装 docker-compose-plugin"
    fi
    log "Docker Compose：$(docker compose version)"
}

# ── 创建目录 ─────────────────────────────────
setup_dir() {
    section "创建目录"
    mkdir -p "$INSTALL_DIR/data"
    log "安装目录：$INSTALL_DIR"
}

# ── 写 docker-compose.yml ────────────────────
write_compose() {
    section "写入配置"
    cat > "$INSTALL_DIR/docker-compose.yml" << EOF
services:
  cloudmusic:
    image: $IMAGE
    container_name: $CONTAINER
    restart: unless-stopped
    ports:
      - "127.0.0.1:$PORT:9000"
    volumes:
      - ./data:/app/data
EOF
    log "docker-compose.yml 已写入"
}

# ── 拉取镜像并启动 ────────────────────────────
start_container() {
    section "拉取镜像并启动"
    cd "$INSTALL_DIR"

    # 如果已有容器则先停止
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
        warn "检测到已有容器，停止并移除…"
        docker compose down
    fi

    info "拉取镜像（首次可能需要几分钟）…"
    docker compose pull
    docker compose up -d

    # 等待启动
    sleep 3
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
        log "容器启动成功"
    else
        error "容器启动失败，请运行：docker logs $CONTAINER"
    fi
}

# ── 配置 nginx ────────────────────────────────
setup_nginx() {
    section "配置 Nginx"

    if ! command -v nginx &>/dev/null; then
        info "未检测到 Nginx，跳过（你可以之后手动配置）"
        return
    fi

    echo -en "${YELLOW}是否自动配置 Nginx 反代？[y/N]${NC} "
    read -r ans
    [[ "$ans" != "y" && "$ans" != "Y" ]] && info "跳过 Nginx 配置" && return

    echo -en "${YELLOW}请输入域名（例如 cm.example.com）：${NC} "
    read -r DOMAIN
    [[ -z "$DOMAIN" ]] && warn "域名为空，跳过 Nginx 配置" && return

    cat > "/etc/nginx/sites-available/cloudmusic" << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/cloudmusic /etc/nginx/sites-enabled/cloudmusic
    nginx -t && systemctl reload nginx
    log "Nginx 配置完成：http://$DOMAIN"

    # 提示申请 SSL
    if command -v certbot &>/dev/null; then
        echo -en "${YELLOW}是否自动申请 SSL 证书？[y/N]${NC} "
        read -r ssl_ans
        if [[ "$ssl_ans" == "y" || "$ssl_ans" == "Y" ]]; then
            certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN"
            log "SSL 证书申请完成"
        fi
    else
        info "如需 HTTPS，请安装 certbot 后运行：certbot --nginx -d $DOMAIN"
    fi
}

# ── 完成 ─────────────────────────────────────
print_done() {
    section "安装完成"
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    echo -e "
${GREEN}${BOLD}🎉 CloudMusic Manager 已成功安装！${NC}

  访问面板：
    本机访问：  ${CYAN}http://127.0.0.1:$PORT${NC}
    局域网访问：${CYAN}http://$LOCAL_IP:$PORT${NC}

  首次使用：
    1. 打开面板，进入「设置」填写 API 地址和账号
    2. 在账号卡片点「扫码登录」完成登录
    3. 脚本将在每天 12:00 自动执行

  常用命令：
    查看日志：  ${YELLOW}docker logs -f $CONTAINER${NC}
    重启服务：  ${YELLOW}cd $INSTALL_DIR && docker compose restart${NC}
    更新镜像：  ${YELLOW}cd $INSTALL_DIR && docker compose pull && docker compose up -d${NC}
    卸载：      ${YELLOW}cd $INSTALL_DIR && docker compose down && rm -rf $INSTALL_DIR${NC}
"
}

# ── 主流程 ────────────────────────────────────
main() {
    clear
    banner
    check_root
    check_docker
    setup_dir
    write_compose
    start_container
    setup_nginx
    print_done
}

main
