"""Loopback-only PBE preview with its own SQLite and visibility policy.

    python tests/serve_pbe_preview.py --port 5190
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def preview_app():
    directory = ROOT / 'instance/pbe-preview'
    directory.mkdir(parents=True, exist_ok=True)
    os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
    os.environ.setdefault('JCC_ADMIN_USERNAME', 'pbe-preview-admin')
    os.environ.setdefault('JCC_ADMIN_PASSWORD', 'LocalPbePreview1234')
    from app import create_app
    visibility = directory / 'visibility.json'
    visibility.write_text(json.dumps({
        'library': {'s19': {'status': 'active', 'order': 1}},
        'simulator': {'s19': {'status': 'active', 'order': 1}},
        'simulator_default_season_id': 's19',
    }), encoding='utf-8')
    return create_app({'DATABASE': str(directory / 'preview.sqlite3'),
                       'DATABASE_URL': 'sqlite:///' + (directory / 'preview.sqlite3').as_posix(),
                       'SECRET_KEY': 'local-pbe-preview-only', 'SESSION_COOKIE_SECURE': False,
                       'SEASON_VISIBILITY_PATH': str(visibility),
                       'SEASON_PACKAGE_ROOT': str(directory / 'packages')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5190)
    args = parser.parse_args()
    preview_app().run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)
