#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/jcc/jcc-web-service"
SERVICE_NAME="jcc"
HEALTH_URL="http://127.0.0.1:5000/api/health"

cd "$PROJECT_DIR"

git fetch origin main
git reset --hard origin/main

source .venv/bin/activate
pip install -r requirements.txt

systemctl restart "$SERVICE_NAME"
sleep 2
curl -fsS "$HEALTH_URL"
echo "jcc-web-service update completed"
