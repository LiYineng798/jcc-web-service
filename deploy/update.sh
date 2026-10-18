#!/usr/bin/env bash
set -euo pipefail

# Run only after the backup/maintenance steps in docs/operations.md.
: "${JCC_WEB_SERVICE:?Set the Web service name explicitly}"
: "${JCC_SEASON_WORKER_SERVICE:?Set the worker service name explicitly}"
: "${JCC_HEALTH_URL:?Set the health check URL explicitly}"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_DIR"
git pull --ff-only origin main
source .venv/bin/activate
pip install -r requirements.txt

systemctl restart "$JCC_WEB_SERVICE" "$JCC_SEASON_WORKER_SERVICE"
sleep 2
systemctl is-active "$JCC_WEB_SERVICE" "$JCC_SEASON_WORKER_SERVICE"
curl -fsS "$JCC_HEALTH_URL"
echo "jcc-web-service update completed"
