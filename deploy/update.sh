#!/usr/bin/env bash
set -euo pipefail

# Run only after the backup/maintenance steps in docs/operations.md.

PROJECT_DIR="/opt/jcc/jcc-web-service"
SERVICE_NAME="jcc"
HEALTH_URL="http://127.0.0.1:5054/api/health"

cd "$PROJECT_DIR"

git pull --ff-only origin main

source .venv/bin/activate
pip install -r requirements.txt

systemctl restart "$SERVICE_NAME" jcc-season-worker
sleep 2
systemctl is-active "$SERVICE_NAME" jcc-season-worker
curl -fsS "$HEALTH_URL"
echo "jcc-web-service update completed"
