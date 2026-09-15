"""Isolated season-picker acceptance server; only fictional local data."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve():
    with tempfile.TemporaryDirectory(prefix='jcc-season-picker-preview-') as temporary:
        directory = Path(temporary)
        os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
        os.environ['JCC_DATABASE_URL'] = 'sqlite:///' + (directory / 'preview.sqlite3').as_posix()
        from app import create_app
        from flask import jsonify, redirect
        from auth import start_user_session
        from db import get_db
        from live_comp_upload_service import start_live_comp_upload_worker, stop_live_comp_upload_worker
        from PIL import Image

        seasons = [
            {'id': 's18', 'name': 'S18 · 仙灵', 'status': 'active', 'order': 1},
            {'id': 's17-star-god', 'name': 'S17 · 星神', 'status': 'archived', 'order': 2},
            {'id': 's16-5-legends', 'name': 'S16.5 · 英雄联盟传奇', 'status': 'active', 'order': 3},
            {'id': 'preview-hidden', 'name': '验收用隐藏赛季', 'status': 'hidden'},
            {'id': 'preview-disabled', 'name': '验收用停用赛季', 'status': 'disabled'},
        ]
        (directory / 'seasons.json').write_text(json.dumps({
            'default_season_id': 's18', 'seasons': seasons,
        }, ensure_ascii=False), encoding='utf-8')
        app = create_app({
            'TESTING': False, 'DATABASE': str(directory / 'preview.sqlite3'),
            'DATABASE_URL': os.environ['JCC_DATABASE_URL'],
            'SECRET_KEY': 'local-season-picker-preview-only',
            'ADMIN_USERNAME': 'previewadmin', 'ADMIN_PASSWORD': 'Preview1234',
            'SESSION_COOKIE_SECURE': False, 'RESEND_API_KEY': '',
            'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'),
            'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'),
            'LIVE_COMPS_BACKUP_DIR': str(directory / 'backups'),
            'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'),
            'LIVE_COMPS_SEASON_MANIFEST_PATH': str(directory / 'seasons.json'),
            'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'),
            'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'),
            'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'),
            'LIVE_COMPS_DEFAULT_SEASON_ID': 's18',
            'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
            'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
        })
        (directory / 'assets').mkdir(exist_ok=True)
        Image.new('RGB', (32, 32), '#7c3aed').save(directory / 'assets' / 'preview.png')

        @app.get('/__preview/login')
        def preview_login():
            start_user_session(get_db().execute(
                "SELECT * FROM users WHERE username='previewadmin'"
            ).fetchone())
            return redirect('/admin')

        @app.get('/__preview/sample.json')
        def sample():
            response = jsonify({'meta': {'source': 'fictional-local-preview'}, 'tiers': {
                'S': [{'id': 'preview-1', 'title': '验收用测试阵容', 'tier': 'S',
                       'jccCode': '#PreviewSample001', 'mainAvatar': '/api/live-comps/assets/preview.png',
                       'heroImages': ['/api/live-comps/assets/preview.png']}], 'A': [], 'B': [], 'C': [], 'D': [],
            }})
            response.headers['Content-Disposition'] = 'attachment; filename="season-picker-sample.json"'
            return response

        host = os.environ.get('ADMIN_SEASON_PICKER_PREVIEW_HOST', '127.0.0.1')
        port = int(os.environ.get('ADMIN_SEASON_PICKER_PREVIEW_PORT', '5115'))
        print(f'Preview: http://127.0.0.1:{port}/__preview/login', flush=True)
        worker = start_live_comp_upload_worker(app)
        try:
            app.run(host=host, port=port, debug=False, use_reloader=False)
        finally:
            stop_live_comp_upload_worker(app)
            if worker:
                worker.join(timeout=5)


if __name__ == '__main__':
    serve()
