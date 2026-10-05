"""Local worktree preview, using only this checkout's independent instance."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
os.environ['JCC_SECRET_KEY'] = 's11-artifacts-local-preview-only'

from app import app

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('S11_ARTIFACTS_PREVIEW_PORT', '5171')), debug=False, use_reloader=False)
