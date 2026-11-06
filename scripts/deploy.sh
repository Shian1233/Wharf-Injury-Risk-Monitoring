#!/usr/bin/env bash
# Risk Agent 部署辅助脚本（openEuler 22.03）
# 用法：sudo bash scripts/deploy.sh <命令>
# 命令：check | deps | start | stop | restart | status | health | entry | logs | secret

set -uo pipefail

APP_DIR="${APP_DIR:-/opt/risk-agent}"
DATA_DIR="${DATA_DIR:-/data/risk-agent}"
SERVICE="${SERVICE:-risk-agent}"
PY312="${PY312:-/usr/local/python3.12/bin/python3.12}"
RUN_USER="${RUN_USER:-risk}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"

ok()   { printf '  [OK]   %s\n' "$*"; }
miss() { printf '  [MISS] %s\n' "$*"; }
info() { printf '\n== %s ==\n' "$*"; }

need_root() {
  [ "$(id -u)" -eq 0 ] || { echo "请用 sudo 执行"; exit 1; }
}

as_user() {
  if id "$RUN_USER" >/dev/null 2>&1; then
    sudo -u "$RUN_USER" "$@"
  else
    "$@"
  fi
}

cmd_check() {
  local problems=0

  info "系统"
  cat /etc/openEuler-release 2>/dev/null || head -3 /etc/os-release
  printf '  架构: %s\n' "$(uname -m)"

  info "Python"
  if [ -x "$PY312" ]; then
    ok "$("$PY312" --version 2>&1)  ($PY312)"
  else
    miss "未找到 $PY312（需按文档第 3 章安装 Python 3.12）"
    problems=$((problems + 1))
  fi

  info "虚拟环境与依赖"
  if [ -x "$APP_DIR/.venv/bin/python" ]; then
    ok "$("$APP_DIR/.venv/bin/python" --version 2>&1)"
    if "$APP_DIR/.venv/bin/python" -c "import fastapi,uvicorn,psycopg,minio,defusedxml" 2>/dev/null; then
      ok "Python 依赖完整"
    else
      miss "Python 依赖缺失，执行: sudo bash $0 deps"
      problems=$((problems + 1))
    fi
  else
    miss "未创建虚拟环境，执行: sudo bash $0 deps"
    problems=$((problems + 1))
  fi

  info "Node"
  if command -v node >/dev/null 2>&1; then
    ok "node $(node --version)"
  else
    miss "未安装 Node（报告图表渲染与 PDF 导出需要，不影响登录与数据浏览）"
  fi

  info "服务"
  if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
    ok "$SERVICE active"
  else
    miss "$SERVICE 未运行，执行: sudo bash $0 start"
    problems=$((problems + 1))
  fi

  info "进程"
  ps -ef | grep -E 'uvicorn|app.main' | grep -v grep || echo "  (无 uvicorn 进程)"

  info "端口"
  ss -lntp 2>/dev/null | grep -E ":(80|443|$PORT|5432|9000)\b" || echo "  (相关端口未监听)"

  info "配置"
  if [ -f "$APP_DIR/.env" ]; then
    ok ".env 存在"
    grep -E '^(DB_BACKEND|STORAGE_BACKEND|AUTH_MODE|PG_HOST|PG_DATABASE|S3_ENDPOINT|S3_BUCKET|CAS_SERVER_URL_PREFIX|CAS_SERVICE_URL|PUBLIC_BASE_PATH)=' "$APP_DIR/.env" 2>/dev/null | sed 's/^/    /'
  else
    miss ".env 缺失，执行: cp .env.example .env 后按文档第 8 章填写"
    problems=$((problems + 1))
  fi

  info "磁盘"
  df -h / "$DATA_DIR" 2>/dev/null | sed 's/^/  /'

  info "内存"
  free -h | sed 's/^/  /'

  echo
  if [ "$problems" -eq 0 ]; then
    echo "检查完成：未发现阻塞项"
  else
    echo "检查完成：$problems 项需要处理"
  fi
}

cmd_deps() {
  need_root
  [ -x "$PY312" ] || { echo "缺少 Python 3.12: $PY312，请先按文档第 3 章安装"; exit 1; }
  mkdir -p "$APP_DIR" "$DATA_DIR"

  if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    as_user "$PY312" -m venv "$APP_DIR/.venv"
  fi
  as_user "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
  as_user "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
  ok "Python 依赖安装完成"

  if command -v npm >/dev/null 2>&1; then
    ( cd "$APP_DIR" && as_user npm install --omit=dev )
    ok "Node 依赖安装完成"
  else
    miss "未安装 Node，跳过 npm install"
  fi

  if id "$RUN_USER" >/dev/null 2>&1; then
    chown -R "$RUN_USER:$RUN_USER" "$APP_DIR" "$DATA_DIR"
  fi
  ok "目录属主已设置为 $RUN_USER"
}

cmd_start() {
  need_root
  if [ -f "/etc/systemd/system/$SERVICE.service" ]; then
    systemctl start "$SERVICE"
    systemctl --no-pager --lines=0 status "$SERVICE"
  else
    echo "未找到 /etc/systemd/system/$SERVICE.service"
    echo "请先按文档第 10 章创建服务单元"
    exit 1
  fi
}

cmd_stop() {
  need_root
  systemctl stop "$SERVICE" 2>/dev/null && echo "已停止 $SERVICE" || echo "$SERVICE 未运行"
}

cmd_restart() {
  need_root
  systemctl restart "$SERVICE"
  sleep 2
  systemctl --no-pager --lines=0 status "$SERVICE"
  cmd_health
}

cmd_status() {
  systemctl --no-pager --lines=5 status "$SERVICE" 2>/dev/null || echo "$SERVICE 未安装"
  echo
  ps -ef | grep -E 'uvicorn|app.main' | grep -v grep || echo "(无 uvicorn 进程)"
}

cmd_health() {
  local url="http://$HOST:$PORT/api/health"
  printf 'GET %s\n' "$url"
  if command -v curl >/dev/null 2>&1; then
    curl -s -w '\nHTTP %{http_code}\n' "$url"
  else
    miss "未安装 curl"
  fi
}

cmd_entry() {
  local next="${1:-/agent}"
  local url="http://$HOST:$PORT/api/auth/cas/entry?next=$next"
  printf 'GET %s\n' "$url"
  curl -s -w '\nHTTP %{http_code}\n' "$url"
}

cmd_logs() {
  tail -n 50 -f "$DATA_DIR/logs/app.log" 2>/dev/null || \
    journalctl -u "$SERVICE" -n 50 -f
}

cmd_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 48 | tr -d '\n'; echo
  else
    "$PY312" -c "import secrets;print(secrets.token_urlsafe(48))" 2>/dev/null || \
      head -c 48 /dev/urandom | base64 | tr -d '\n'; echo
  fi
}

case "${1:-check}" in
  check)   cmd_check ;;
  deps)    cmd_deps ;;
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_restart ;;
  status)  cmd_status ;;
  health)  cmd_health ;;
  entry)   shift; cmd_entry "${1:-/agent}" ;;
  logs)    cmd_logs ;;
  secret)  cmd_secret ;;
  *) echo "用法: sudo bash $0 {check|deps|start|stop|restart|status|health|entry|logs|secret}"; exit 1 ;;
esac
