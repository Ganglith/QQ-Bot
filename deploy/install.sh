#!/usr/bin/env bash
# QQ AI Bot 一键部署脚本（Linux + Docker）
# 用法：在项目根目录执行  bash deploy/install.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="${SERVICE_NAME:-qqbot}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

log()  { printf '\033[1;32m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }

cd "$PROJECT_DIR"
log "项目目录：$PROJECT_DIR"

# ---------- 1. Docker ----------
if ! command -v docker >/dev/null 2>&1; then
  warn "未检测到 docker，正在尝试安装（需要 root/sudo 和网络）..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker >/dev/null 2>&1 || true
fi

# 兼容 docker compose(v2 插件) 与 docker-compose(v1 独立命令)
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  err "缺少 compose。请安装 docker-compose-plugin，或在宝塔 Docker 管理器的『Compose 模板』里图形化部署 NapCat。"
  exit 1
fi
log "Docker 就绪，Compose 命令：$COMPOSE"

# ---------- 2. 启动 NapCat ----------
if docker ps -a --format '{{.Names}}' | grep -qx "napcat"; then
  log "已存在名为 napcat 的容器，跳过创建，尝试启动它"
  docker start napcat >/dev/null 2>&1 || true
else
  log "启动 NapCat 容器 ..."
  $COMPOSE -f docker-compose.napcat.yml up -d
fi

# ---------- 3. Python 环境 ----------
if [ ! -d .venv ]; then
  log "创建 Python 虚拟环境 ..."
  "$PYTHON_BIN" -m venv .venv
fi
# 国内服务器直连 PyPI 常超时，默认走清华源；可用 PIP_INDEX_URL 覆盖
PIP_INDEX="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
log "安装 Python 依赖（源：$PIP_INDEX）..."
./.venv/bin/pip install --no-cache-dir -i "$PIP_INDEX" --upgrade pip
./.venv/bin/pip install --no-cache-dir -i "$PIP_INDEX" -r requirements.txt

./.venv/bin/python -c "import websockets, openai, yaml, dotenv" 2>/dev/null || {
  err "依赖安装失败。请检查网络，或换源后重跑："
  echo "    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple bash deploy/install.sh"
  exit 1
}
log "Python 依赖安装完成"

# ---------- 4. .env ----------
if [ ! -f .env ]; then
  cp .env.example .env
  warn "已生成 .env，请填入 DEEPSEEK_API_KEY 后重新运行：bash deploy/install.sh"
  exit 1
fi
if grep -q "sk-你的key" .env; then
  warn ".env 里的 DEEPSEEK_API_KEY 还是占位符，请修改后重跑。"
  exit 1
fi

# ---------- 5. 注册 systemd 服务 ----------
if command -v systemctl >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
  log "注册 systemd 服务：$SERVICE_NAME"
  sed "s#__PROJECT_DIR__#${PROJECT_DIR}#g" deploy/qqbot.service \
    > "/etc/systemd/system/${SERVICE_NAME}.service"
  systemctl daemon-reload
  systemctl enable --now "$SERVICE_NAME"
  log "服务已启动。查看日志： journalctl -u ${SERVICE_NAME} -f"
else
  warn "当前非 root 或无 systemd，跳过服务注册。可手动后台运行："
  echo "    nohup ./.venv/bin/python main.py >> bot.log 2>&1 &"
fi

cat <<'EOF'

================= 完成！还剩两步 =================
1) 在本地电脑开 SSH 隧道，看 NapCat 二维码：
     ssh -L 6099:127.0.0.1:6099 <用户>@<服务器IP>
   然后浏览器打开：  http://127.0.0.1:6099/webui
   用你的 QQ 小号扫码登录
2) 用另一个 QQ 私聊这个小号，收到回复即成功
=================================================
EOF
