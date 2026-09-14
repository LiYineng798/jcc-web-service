"""Loopback profile preview with fictional users and disposable runtime data."""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve():
    with tempfile.TemporaryDirectory(prefix='jcc-profile-preview-') as temporary:
        directory = Path(temporary)
        os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
        os.environ['JCC_DATABASE_URL'] = 'sqlite:///' + (directory / 'preview.sqlite3').as_posix()
        from app import create_app
        from auth import start_user_session
        from db import get_db, now_text
        from flask import redirect, request
        from lineup_moderation_service import moderate_lineup
        from werkzeug.security import generate_password_hash

        app = create_app({
            'TESTING': True, 'DATABASE': str(directory / 'preview.sqlite3'),
            'DATABASE_URL': os.environ['JCC_DATABASE_URL'], 'SECRET_KEY': 'local-profile-preview-only',
            'ADMIN_USERNAME': 'previewadmin', 'ADMIN_PASSWORD': 'Preview1234', 'SESSION_COOKIE_SECURE': False,
            'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'), 'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'),
            'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'), 'LIVE_COMPS_SEASON_MANIFEST_PATH': str(directory / 'seasons.json'),
            'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'), 'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'),
            'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'), 'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
            'SEASON_PACKAGE_ROOT': str(directory / 'packages'), 'RESEND_API_KEY': '',
        })
        with app.app_context():
            db = get_db()
            now = now_text()
            for username, nickname, color in [('previewuser', '弈起上分', '#b56949'), ('previewother', '小小铲铲', '#059669'), ('previewempty', '新来的弈士', '#637bb2')]:
                db.execute('''INSERT INTO users (username,email,nickname,avatar_color,password_hash,role,status,created_at,updated_at)
                              VALUES (?,?,?,?,?,'user','active',?,?)''',
                           (username, username + '@example.test', nickname, color, generate_password_hash('Preview1234'), now, now))
            db.commit()
            owner = db.execute("SELECT * FROM users WHERE username='previewuser'").fetchone()
            other = db.execute("SELECT * FROM users WHERE username='previewother'").fetchone()
            admin = db.execute("SELECT * FROM users WHERE username='previewadmin'").fetchone()
            names = ['仙灵九五', '斗士卡莎', '冰龙九五', '星神法师', '重装射手', '灵风秘术', '斗士上分', '决斗大师', '自然之力', '福星连胜', '游侠阵线', '巨像守卫', '迅捷射手', '仙灵秘境', '重装九五', '法师进阶', '护卫阵线', '峡谷奇兵', '小法进阶', '摇头乌鸦', '冰龙重装', '灵能卡莎', '九五至尊', '仙灵奇遇', '最后一页的上分灵感', '月蚀九五']
            for i, name in enumerate(names):
                at = (datetime.now() - timedelta(hours=i * 5)).strftime('%Y-%m-%d %H:%M:%S')
                db.execute("INSERT INTO lineups (user_id,name,code,season_id,status,created_at,updated_at) VALUES (?,?,?,'s17-star-god',?,?,?)",
                           (owner['id'], name, '#PROFILEDEMO' + str(i + 1000), 'hidden' if i in [5, 13, 22] else 'normal', at, at))
            for i, name in enumerate(['山海九五', '重装卡莎', '斗士连胜', '秘术法师', '星神射手', '天选福星', '灵能大师', '护卫九五']):
                db.execute("INSERT INTO lineups (user_id,name,code,season_id,status,created_at,updated_at) VALUES (?,?,?,'s17-star-god','normal',?,?)",
                           (other['id'], name, '#OTHERDEMO' + str(i + 1000), now, now))
            db.commit()
            own_ids = [row['id'] for row in db.execute('SELECT id FROM lineups WHERE user_id=?', (owner['id'],))]
            public_ids = [row['id'] for row in db.execute('SELECT id FROM lineups WHERE user_id=?', (other['id'],))]
            for i, lineup_id in enumerate(public_ids):
                at = (datetime.now() - timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S')
                for table in ['recent_lineup_views', 'recent_lineup_copies']:
                    db.execute(f'INSERT INTO {table} (user_id,lineup_id,created_at,updated_at) VALUES (?,?,?,?)', (owner['id'], lineup_id, at, at))
                db.execute('INSERT INTO favorites (user_id,lineup_id,created_at) VALUES (?,?,?)', (owner['id'], lineup_id, at))
                status = ['pending', 'resolved', 'dismissed'][i % 3]
                db.execute('INSERT INTO reports (reporter_user_id,lineup_id,reason,status,created_at,handled_at) VALUES (?,?,?,?,?,?)',
                           (owner['id'], lineup_id, '这个阵容的装备描述与当前版本不一致，希望核对后更新。', status, at, at if status != 'pending' else None))
            for i, lineup_id in enumerate(own_ids[:13]):
                db.execute('INSERT INTO likes (user_id,lineup_id,like_date,created_at) VALUES (?,?,?,?)', (other['id'], lineup_id, now[:10], now))
                for n in range(3):
                    db.execute('INSERT INTO copy_events (lineup_id,user_id,copy_key,bucket_start,created_at) VALUES (?,?,?,?,?)', (lineup_id, other['id'], f'preview:{i}:{n}', now, now))
                if i < 4:
                    db.execute('INSERT INTO favorites (user_id,lineup_id,created_at) VALUES (?,?,?)', (other['id'], lineup_id, now))
            db.execute("INSERT INTO reports (reporter_user_id,lineup_id,reason,status,created_at) VALUES (?,?,?,'pending',?)", (other['id'], own_ids[0], '请检查当前阵容码。', now))
            db.commit()
            row = db.execute('SELECT * FROM lineups WHERE id=?', (own_ids[2],)).fetchone()
            _, error, _ = moderate_lineup(admin, row['id'], 'ban', {'version': row['version'], 'reason': '本地演示：阵容码与所属赛季不一致，请核对后提交重审。'})
            if error:
                raise RuntimeError(error)

        @app.get('/__preview/login')
        def preview_login():
            # This convenience route exists only in this loopback preview process.
            username = {'empty': 'previewempty', 'admin': 'previewadmin'}.get(request.args.get('user'), 'previewuser')
            user = get_db().execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            start_user_session(user)
            return redirect('/me')

        port = int(os.environ.get('ACCOUNT_PROFILE_PREVIEW_PORT', '5113'))
        print(f'Profile preview: http://127.0.0.1:{port}/__preview/login', flush=True)
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    serve()
