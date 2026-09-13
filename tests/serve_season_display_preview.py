"""Isolated loopback preview: sample visibility settings, temporary SQLite."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5100)
    parser.add_argument('--stdio-control', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='jcc-season-display-') as temp:
        directory = Path(temp)
        os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
        os.environ['JCC_DATABASE_URL'] = 'sqlite:///' + (directory / 'bootstrap.sqlite3').as_posix()
        os.environ['JCC_ADMIN_USERNAME'] = 'previewadmin'
        os.environ['JCC_ADMIN_PASSWORD'] = 'Preview1234'
        from app import create_app
        from werkzeug.serving import make_server

        settings = {
            's18': {'status': 'active', 'order': 1},
            's17': {'status': 'disabled', 'order': 2},
            's16_5': {'status': 'active', 'order': 3},
            's8': {'status': 'disabled', 'order': 4},
        }
        simulator = {sid: dict(value) for sid, value in settings.items()}
        simulator['s16_5']['status'] = 'archived'
        simulator['s8']['status'] = 'hidden'
        (directory / 'visibility.json').write_text(json.dumps({
            'library': settings, 'simulator': simulator, 'simulator_default_season_id': 's18',
        }), encoding='utf-8')
        from seasons import season_catalog
        live_seasons = [{'id': 's18', 'name': 'S18 · 自然之力', 'status': 'active', 'order': 1, 'description': '当前赛季', 'data_file': 's18.json'}]
        live_statuses = {'s17-star-god': 'disabled', 's16-5-legends': 'active', 's16-legends': 'disabled', 'lucky-lantern': 'hidden', 's8-monsters-attack': 'archived'}
        for index, season in enumerate(season_catalog(), 2):
            live_seasons.append({**season, 'order': index, 'status': live_statuses[season['id']]})
        (directory / 'seasons.json').write_text(json.dumps({'default_season_id': 's18', 'seasons': live_seasons}), encoding='utf-8')
        app = create_app({
            'TESTING': True,
            'DATABASE': str(directory / 'preview.sqlite3'),
            'DATABASE_URL': 'sqlite:///' + (directory / 'preview.sqlite3').as_posix(),
            'SECRET_KEY': 'isolated-season-display-preview-only',
            'ADMIN_USERNAME': 'previewadmin', 'ADMIN_PASSWORD': 'Preview1234',
            'SESSION_COOKIE_SECURE': False,
            'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'),
            'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'),
            'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'),
            'LIVE_COMPS_SEASON_MANIFEST_PATH': str(directory / 'seasons.json'),
            'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'),
            'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'),
            'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'),
            'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
            'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
        })
        server = make_server('127.0.0.1', args.port, app, threaded=True)
        if args.stdio_control:
            def control():
                sys.stdin.read()
                server.shutdown()
            threading.Thread(target=control, daemon=True).start()
        print('SEASON_DISPLAY_READY=' + json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
