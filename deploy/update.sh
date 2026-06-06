#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/jcc/jcc_git"
BACKUP_DIR="/opt/jcc/backups"
SERVICE_NAME="jcc"
HEALTH_URL="https://jcc.np5.top/api/health"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

cd "$PROJECT_DIR"

"$PYTHON_BIN" scripts/maintenance/backup_database.py \
  --database "instance/lineups.sqlite3" \
  --backup-dir "$BACKUP_DIR"

git fetch origin main
git reset --hard origin/main

source .venv/bin/activate
pip install -r requirements.txt
python migrate.py

systemctl restart "$SERVICE_NAME"
curl -fsS "$HEALTH_URL"
echo "JCC update completed"
