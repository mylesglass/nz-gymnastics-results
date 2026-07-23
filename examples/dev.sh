# this was in main dir

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[…]${NC} $1"; }
fail()  { echo -e "${RED}[✗]${NC} $1"; }

wait_for_db() {
  local max_attempts=40
  local attempt=1
  warn "Waiting for PostgreSQL to be ready…"
  while [ $attempt -le $max_attempts ]; do
    if docker compose -f "$SCRIPT_DIR/docker-compose.yml" exec -T db pg_isready -U amplitude &>/dev/null; then
      info "PostgreSQL is ready"
      return 0
    fi
    printf "."
    sleep 3
    attempt=$((attempt + 1))
  done
  fail "PostgreSQL did not become ready within $((max_attempts * 3)) seconds."
  fail "Run 'docker compose logs db' for details."
  return 1
}

run_migrations() {
  local max_attempts=3
  local attempt=1
  cd "$SCRIPT_DIR/backend"
  while [ $attempt -le $max_attempts ]; do
    if source .venv/bin/activate && alembic upgrade head; then
      deactivate
      cd "$SCRIPT_DIR"
      return 0
    fi
    deactivate 2>/dev/null || true
    if [ $attempt -lt $max_attempts ]; then
      warn "Migration attempt $attempt failed, retrying in 5s…"
      sleep 5
    fi
    attempt=$((attempt + 1))
  done
  cd "$SCRIPT_DIR"
  fail "Database migrations failed after $max_attempts attempts."
  return 1
}

verify_migrations() {
  cd "$SCRIPT_DIR/backend"
  if source .venv/bin/activate && alembic current 2>/dev/null; then
    deactivate
    cd "$SCRIPT_DIR"
  else
    deactivate 2>/dev/null || true
    cd "$SCRIPT_DIR"
    warn "Could not verify migration state (non-fatal)"
  fi
}

cmd_start() {
  echo "Starting PostgreSQL…"
  docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d

  wait_for_db || { fail "Aborting startup."; exit 1; }

  echo "Running database migrations…"
  run_migrations || { fail "Aborting startup."; exit 1; }
  verify_migrations

  if command -v code &>/dev/null; then
    code "$SCRIPT_DIR"
  else
    echo "VS Code 'code' CLI not found — open the project manually."
  fi

  cat <<'EOF'
── Amplitude Dev ──────────────────────────────────────────
  VS Code tasks (Ctrl+Shift+B) to start:
    • Backend   — uvicorn
    • Frontend  — npm run dev
    • DB Logs   — docker logs -f db
    • OpenCode  — opencode

  Run:  ./dev.sh stop   to stop PostgreSQL
────────────────────────────────────────────────────────────
EOF
}

cmd_stop() {
  echo "Stopping PostgreSQL…"
  docker compose -f "$SCRIPT_DIR/docker-compose.yml" down
  echo "Done."
}

cmd_status() {
  echo "── Docker containers ─────"
  docker compose -f "$SCRIPT_DIR/docker-compose.yml" ps --services --status running 2>/dev/null || echo "  Not running"
  echo ""
  echo "── Migration status ─────"
  cd "$SCRIPT_DIR/backend"
  if source .venv/bin/activate && alembic current 2>/dev/null; then
    deactivate
  else
    deactivate 2>/dev/null || true
    echo "  (unable to check — is PostgreSQL running?)"
  fi
  cd "$SCRIPT_DIR"
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

case "${1:-help}" in
  start)   cmd_start   ;;
  stop)    cmd_stop    ;;
  status)  cmd_status  ;;
  restart) cmd_restart ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
