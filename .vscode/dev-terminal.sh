#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

killall konsole 2>/dev/null || true
sleep 0.5

nohup konsole --noclose --title "Dev Servers" &>/dev/null &
KONSOLE_PID=$!
sleep 2

SERVICE="org.kde.konsole-$KONSOLE_PID"
WIN="/Windows/1"
QDBUS="/usr/lib/qt6/bin/qdbus"

$QDBUS "$SERVICE" "$WIN" org.kde.konsole.Window.createSplit 0 true

$QDBUS "$SERVICE" /Sessions/1 org.kde.konsole.Session.runCommand \
  "cd '$SCRIPT_DIR/backend' && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000; exec bash"

$QDBUS "$SERVICE" /Sessions/2 org.kde.konsole.Session.runCommand \
  "cd '$SCRIPT_DIR/frontend' && npm run dev; exec bash"

sleep 1
$QDBUS "$SERVICE" "/Sessions/1" org.kde.konsole.Session.setTitle 0 "Backend"
$QDBUS "$SERVICE" "/Sessions/2" org.kde.konsole.Session.setTitle 0 "Frontend"
