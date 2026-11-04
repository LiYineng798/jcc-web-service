"""Loopback-only deck review with isolated, fictional data and quick account switching."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def create_preview():
    directory = ROOT / 'instance' / 'deck-review-preview'
    directory.mkdir(parents=True, exist_ok=True)
    os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
    os.environ['JCC_DATABASE_URL'] = 'sqlite:///' + (directory / 'preview.sqlite3').as_posix()
    from app import create_app
    from auth import start_user_session
    from automation_service import create_account
    from db import get_db, now_text
    from flask import abort, redirect, request
    from orange_deck_service import create_deck
    from werkzeug.security import generate_password_hash

    app = create_app({
        'TESTING': True, 'DATABASE': str(directory / 'preview.sqlite3'),
        'DATABASE_URL': os.environ['JCC_DATABASE_URL'], 'SECRET_KEY': 'isolated-deck-review-preview',
        'ADMIN_USERNAME': 'previewadmin', 'ADMIN_PASSWORD': 'Preview1234', 'SESSION_COOKIE_SECURE': False,
        'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'), 'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'),
        'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'), 'LIVE_COMPS_SEASON_MANIFEST_PATH': str(directory / 'seasons.json'),
        'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'), 'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'),
        'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'), 'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
        'SEASON_PACKAGE_ROOT': str(directory / 'packages'), 'RESEND_API_KEY': '',
    })
    with app.test_request_context('/'):
        db, now = get_db(), now_text()
        if not db.execute("SELECT 1 FROM users WHERE username='previewuser'").fetchone():
            db.execute("""INSERT INTO users(username,email,nickname,password_hash,role,status,created_at,updated_at)
                          VALUES('previewuser','preview@example.test','卡组验收作者',?,'user','active',?,?)""",
                       (generate_password_hash('Preview1234'), now, now))
            db.commit()
        user = db.execute("SELECT * FROM users WHERE username='previewuser'").fetchone()
        if not db.execute("SELECT 1 FROM orange_decks WHERE name='旧卡组·待补充方案码'").fetchone():
            base = {'action': 'publish', 'portal': 'stable', 'cards': ['7230005', '7220015', '7210014'],
                    'note': '本地验收示例，用于检查排版与交互。方案码沿用提供的样例，未核验其游戏内内容与选卡是否一致。'}
            if not db.execute("SELECT 1 FROM orange_decks WHERE name='德玛时光速9流·验收示例'").fetchone():
                create_deck(user, {**base, 'name': '德玛时光速9流·验收示例',
                                  'plan_code': '德玛时光速9流-大橘大利-MjE5OTY4Mzc0NDMyOTI3OTQxNzkzNzU0NzMyMTczNQ=='})
            create_deck(user, {**base, 'name': '旧卡组·待补充方案码'})
            create_deck(user, {**base, 'name': '未知门·三传说', 'portal': 'unknown',
                              'cards': ['7250010', '7250011', '7250013']})
            create_deck(user, {**base, 'name': '待完善草稿', 'action': 'draft', 'cards': ['7230005']})
        admin = db.execute("SELECT id FROM users WHERE username='previewadmin'").fetchone()
        if not db.execute("SELECT 1 FROM users WHERE username='previewbot'").fetchone():
            create_account(db, admin['id'], {'username': 'previewbot', 'nickname': '卡组上传助手', 'password': 'PreviewBot1234',
                                          'can_upload_decks': True, 'deck_seasons': ['orange_s400001']})

    @app.get('/__preview/login')
    def preview_login():
        if request.remote_addr not in ('127.0.0.1', '::1'):
            abort(403)
        role = request.args.get('user', 'author')
        username = {'author': 'previewuser', 'admin': 'previewadmin', 'ai': 'previewbot'}.get(role)
        if not username:
            abort(400)
        start_user_session(get_db().execute('SELECT * FROM users WHERE username=?', (username,)).fetchone())
        return redirect('/admin#decks' if role == 'ai' else '/admin' if role == 'admin' else '/?library=decks')

    return app


def prepare_time_card_package(app):
    """Prepare a clearly labelled baseline fixture, never claim it is a new official patch."""
    import json
    import shutil
    from datetime import datetime
    from db import get_db
    from orange_fortune_service import CATALOG, parse_catalog
    from season_package_format import dump
    from season_package_service import receive_package, run_one_job, release_payload
    from scripts.season_library.build_upload_package import build_package

    directory = ROOT / 'instance/deck-review-preview'
    with app.app_context():
        old = get_db().execute("SELECT id FROM season_release_packages WHERE package_id='time-card-review-baseline'").fetchone()
        if old:
            rid = old['id']
        else:
            fixture = directory / 'time-card-fixtures' / datetime.now().strftime('%Y%m%d-%H%M%S')
            source = fixture / 'source'
            shutil.copytree(ROOT / 'static/season-data/orange_s400001', source)
            index = json.loads((source / 'index.json').read_text('utf8'))
            legacy = parse_catalog(json.loads(CATALOG.read_text('utf8')))
            for card in legacy['cards']:
                if card['image']:
                    image = ROOT / 'static' / card['image']
                    target = source / 'assets/time-cards' / image.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(image, target)
                    card['image'] = 'assets/time-cards/' + image.name
            doc = {key: legacy[key] for key in ('version', 'season', 'setId', 'time')}
            doc.update(season_id=index['season_id'], version_id=index['version_id'], time_cards=legacy['cards'])
            dump(source / 'time_cards.json', doc)
            path = fixture / 'time-cards-baseline.zip'
            build_package(source, path, 1, {'title': '本地时间卡片联动验收', 'summary': '由仓库现有基准生成；不是新官方补丁', 'sections': []},
                          package_id='time-card-review-baseline')
            actor = get_db().execute("SELECT id FROM users WHERE username='previewadmin'").fetchone()['id']
            with path.open('rb') as stream:
                result, _ = receive_package(stream, path.name, actor)
            rid = result['id']
        while release_payload(rid)['state'] in ('queued', 'validating'):
            if not run_one_job():
                break
        state = release_payload(rid)['state']
        dump(directory / 'time-card-package.json', {'id': rid, 'state': state})
        if state != 'ready':
            raise RuntimeError(f'Time-card fixture is not ready: {state}')
        print(f'Time-card review package: {rid}', flush=True)


if __name__ == '__main__':
    app = create_preview()
    if '--prepare-time-cards' in sys.argv:
        prepare_time_card_package(app)
    app.run(host='127.0.0.1', port=int(os.environ.get('DECK_REVIEW_PORT', '5137')), debug=False, use_reloader=False)
