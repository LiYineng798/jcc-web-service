"""Loopback-only acceptance server. All accounts and activity are fictional."""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['JCC_PROCESS_ROLE'] = 'season-worker'


def serve():
    from app import create_app
    from auth import start_user_session
    from daily_report_service import ensure_daily_report
    from db import get_db, now_text
    from flask import redirect
    from live_comp_version_service import save_version
    from patch_note_service import create_patch_note

    directory = ROOT / 'instance' / 'admin-experience-preview'
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / 'seasons.json'
    if not manifest.exists():
        manifest.write_text(json.dumps({
            'default_season_id': 's18',
            'seasons': [
                {'id': 's18', 'name': 'S18 · 仙灵', 'status': 'active', 'order': 1, 'data_file': 's18.json'},
                {'id': 's17-star-god', 'name': 'S17 · 星神', 'status': 'archived', 'order': 2, 'data_file': 's17-star-god.json'},
            ],
        }, ensure_ascii=False), encoding='utf-8')
    app = create_app({
        'DATABASE': str(directory / 'preview.sqlite3'),
        'DATABASE_URL': 'sqlite:///' + (directory / 'preview.sqlite3').as_posix(),
        'SECRET_KEY': 'loopback-admin-experience-preview-only',
        'ADMIN_USERNAME': 'previewadmin', 'ADMIN_PASSWORD': 'Preview1234',
        'SESSION_COOKIE_SECURE': False, 'RESEND_API_KEY': '',
        'DAILY_REPORT_WORKER_ENABLED': False,
        'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'),
        'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'),
        'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'),
        'LIVE_COMPS_SEASON_MANIFEST_PATH': str(manifest),
        'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'),
        'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'),
        'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'),
        'LIVE_COMPS_DEFAULT_SEASON_ID': 's18',
        'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
        'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
    })
    with app.app_context():
        db = get_db()
        admin = db.execute("SELECT id FROM users WHERE username='previewadmin'").fetchone()['id']
        if not db.execute("SELECT id FROM users WHERE username='demo_author'").fetchone():
            now = now_text()
            db.execute("""INSERT INTO users (username,email,nickname,password_hash,role,status,created_at,updated_at)
                          VALUES ('demo_author','demo@example.com','演示上传者','disabled-demo-password','user','active',?,?)""", (now, now))
            author = db.execute("SELECT id FROM users WHERE username='demo_author'").fetchone()['id']
            for index in range(1, 25):
                db.execute("""INSERT INTO users (username,email,nickname,password_hash,role,status,created_at,updated_at)
                              VALUES (?,?,?,'disabled-demo-password','user','active',?,?)""",
                           (f'demo_user_{index}', f'user{index}@example.com', f'演示用户 {index}', now, now))
            for index, name in enumerate(['仙灵九五', '重装斗士', '秘术法师', '迅捷射手', '护卫神谕', '决斗大师', '法师九五', '斗士连胜', '灵能秘术', '重装连胜', '迅捷九五', '仙灵法师'], 1):
                cursor = db.execute("""INSERT INTO lineups (user_id,name,code,season_id,status,created_at,updated_at)
                                       VALUES (?,?,?,'s18','normal',?,?)""",
                                    (author, name + ' · 演示', f'#LOCALDEMO{index:03d}', now, now))
                lineup_id = cursor.lastrowid
                for day in (datetime.now(), datetime.now() - timedelta(days=1)):
                    for offset in range(max(1, 8 - index)):
                        db.execute("""INSERT INTO copy_action_events
                            (target_type,target_id,lineup_id,season_id,visitor_token,ip_address,source_page,success,counted,created_at)
                            VALUES ('lineup',?,?,'s18',?,'127.0.0.1','home',1,1,?)""",
                                   (str(lineup_id), lineup_id, f'demo-{offset}', day.strftime('%Y-%m-%d') + ' 10:30:00'))
            db.commit()
            create_patch_note(admin, {
                'title': 'S18 版本更新 · 演示公告', 'version': '18.1',
                'published_at': datetime.now().strftime('%Y-%m-%d'),
                'summary_markdown': '## 英雄调整\n- [buff] 演示英雄：伤害 220 => 240\n- [nerf] 演示英雄：护盾 500 => 450\n## 玩法调整\n- [adjust] 演示内容，请勿作为游戏建议。',
                'source_url': 'https://example.com/update', 'original_text': '这是本地演示原文。', 'status': 'draft',
            })
            ensure_daily_report((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
            heroes = ['/static/' + path.relative_to(ROOT / 'static').as_posix()
                      for path in sorted((ROOT / 'static/artifacts-guide/heroes').glob('*.png'))[:3]]
            payload = {'meta': {'source': '本地虚构预览'}, 'tiers': {
                'S': [{'id': f'demo-{i}', 'title': name + ' · 演示', 'tier': 'S', 'jccCode': f'#DEMO{i}',
                       'mainAvatar': heroes[i] if len(heroes) > i else '', 'heroImages': heroes}
                      for i, name in enumerate(['仙灵九五', '重装斗士', '秘术法师'])],
                'A': [], 'B': [], 'C': [], 'D': [],
            }}
            save_version('s18', payload, 'local-demo.json', admin_id=admin, publish=True)

        if not db.execute("SELECT id FROM users WHERE username='previewassistant'").fetchone():
            from automation_service import create_account
            create_account(db, admin, {'username': 'previewassistant', 'nickname': '协作演示助手',
                           'password': 'PreviewAssistant1234', 'can_import': True, 'allowed_seasons': ['s18'],
                           'can_touch': True, 'touch_seasons': ['s18']})

    @app.get('/__preview/login')
    def preview_login():
        start_user_session(get_db().execute("SELECT * FROM users WHERE username='previewadmin'").fetchone())
        return redirect('/admin')

    app.run(host='127.0.0.1', port=int(os.environ.get('ADMIN_EXPERIENCE_PREVIEW_PORT', '5138')),
            debug=False, use_reloader=False)


if __name__ == '__main__':
    serve()
