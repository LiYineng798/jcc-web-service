"""Loopback-only release-management demo with isolated, persistent sample data."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['JCC_PROCESS_ROLE'] = 'season-worker'


def serve():
    from app import create_app
    from flask import redirect, jsonify
    from auth import start_user_session
    from db import get_db
    from live_comp_version_service import save_version, list_versions
    from live_comp_upload_service import start_live_comp_upload_worker
    directory = ROOT / 'instance' / 'live-versions-preview'
    directory.mkdir(parents=True, exist_ok=True)
    app = create_app({
        'TESTING': False, 'DATABASE': str(directory / 'preview.sqlite3'),
        'DATABASE_URL': 'sqlite:///' + (directory / 'preview.sqlite3').as_posix(),
        'SECRET_KEY': 'loopback-release-demo-only', 'ADMIN_USERNAME': 'previewadmin',
        'ADMIN_PASSWORD': 'Preview1234', 'SESSION_COOKIE_SECURE': False, 'RESEND_API_KEY': '',
        'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'),
        'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'),
        'LIVE_COMPS_BACKUP_DIR': str(directory / 'backups'),
        'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'),
        'LIVE_COMPS_SEASON_MANIFEST_PATH': str(directory / 'seasons.json'),
        'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'),
        'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'),
        'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'),
        'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
        'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
    })
    heroes = ['/static/' + path.relative_to(ROOT / 'static').as_posix()
              for path in sorted((ROOT / 'static' / 'artifacts-guide' / 'heroes').glob('*.png'))[:8]]

    def sample(missing=3):
        names = ['星神九五', '重装神谕', '斗士双枪', '灵能法师', '迅捷射手', '护卫秘术', '决斗大师', '福星连胜']
        tiers = {tier: [] for tier in 'SABCD'}
        for i, name in enumerate(names):
            tier = 'S' if i < 4 else 'A'
            tiers[tier].append({'id': f'demo-{i + 1}', 'title': name + ' · 演示', 'tier': tier,
                                'jccCode': '' if i < missing else f'#DEMO{i + 1}',
                                'mainAvatar': heroes[i], 'heroImages': heroes[i:] + heroes[:i]})
        return {'meta': {'source': '本地演示数据，非真实游戏推荐'}, 'tiers': tiers}

    with app.app_context():
        if not list_versions('s17-star-god')['items']:
            save_version('s17-star-god', sample(0), '10-13_历史榜单_演示.json', publish=True)
            save_version('s17-star-god', sample(0), '10-14_正式榜单_演示.json', publish=True)
            save_version('s17-star-god', sample(3), '10-15_待补码榜单_演示.json')

    @app.get('/__preview/login')
    def login():
        start_user_session(get_db().execute("SELECT * FROM users WHERE username='previewadmin'").fetchone())
        return redirect('/admin')

    @app.get('/__preview/sample.json')
    def download():
        response = jsonify(sample(3))
        response.headers['Content-Disposition'] = 'attachment; filename="live-lineups-demo.json"'
        return response

    start_live_comp_upload_worker(app)
    app.run(host='127.0.0.1', port=int(os.environ.get('LIVE_VERSIONS_PREVIEW_PORT', '5127')),
            debug=False, use_reloader=False)


if __name__ == '__main__':
    serve()
