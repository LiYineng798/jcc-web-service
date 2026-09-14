"""Loopback-only, fictional data and disposable SQLite; no production services."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve():
    with tempfile.TemporaryDirectory(prefix='jcc-moderation-preview-') as temporary:
        directory = Path(temporary)
        os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
        os.environ['JCC_DATABASE_URL'] = 'sqlite:///' + (directory / 'preview.sqlite3').as_posix()
        from app import create_app
        from db import get_db, now_text
        from lineup_moderation_service import moderate_lineup, submit_revision
        from werkzeug.security import generate_password_hash
        app = create_app({
            'TESTING': True, 'DATABASE': str(directory / 'preview.sqlite3'),
            'DATABASE_URL': os.environ['JCC_DATABASE_URL'], 'SECRET_KEY': 'local-moderation-preview-only',
            'ADMIN_USERNAME': 'previewadmin', 'ADMIN_PASSWORD': 'Preview1234', 'SESSION_COOKIE_SECURE': False,
            'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'), 'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'),
            'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'), 'LIVE_COMPS_SEASON_MANIFEST_PATH': str(directory / 'seasons.json'),
            'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'), 'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'),
            'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'), 'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
            'SEASON_PACKAGE_ROOT': str(directory / 'packages'), 'RESEND_API_KEY': '',
        })
        with app.app_context():
            db = get_db(); now = now_text()
            admin = db.execute("SELECT * FROM users WHERE username='previewadmin'").fetchone()
            for username, nickname, color in [('previewuser', '弈起上分', '#7c3aed'), ('previewother', '小小铲铲', '#059669')]:
                db.execute('''INSERT INTO users (username,email,nickname,avatar_color,password_hash,role,status,created_at,updated_at)
                              VALUES (?,?,?,?,?,'user','active',?,?)''',
                           (username, username + '@example.test', nickname, color, generate_password_hash('Preview1234'), now, now))
            db.commit()
            owner = db.execute("SELECT * FROM users WHERE username='previewuser'").fetchone()
            other = db.execute("SELECT * FROM users WHERE username='previewother'").fetchone()
            names = ['仙灵九五', '七斗卡莎', '冰龙九五', '星神法师', '重装射手', '灵风秘术', '斗士上分', '决斗大师', '自然之力', '福星连胜', '游侠阵线', '巨像守卫', '迅捷射手', '仙灵秘境', '重装九五', '法师进阶', '护卫阵线', '七峡谷鸡哥', '小法', '摇头乌鸦', '冰龙重装', '灵能卡莎', '九五至尊', '仙灵奇遇']
            for i, name in enumerate(names):
                user = other if i % 5 == 0 else owner
                db.execute("INSERT INTO lineups (user_id,name,code,season_id,status,created_at,updated_at) VALUES (?,?,?,'s17-star-god',?,?,?)",
                           (user['id'], name, '#JCCPreview' + str(i + 1001) + 'MjEwMDI4OTM2NDAxNzg3NZM4', 'hidden' if i % 6 == 0 else 'normal', now, now))
            db.commit()
            for i in [3, 7, 17, 18, 19, 20, 21, 22, 23, 24]:
                row = db.execute('SELECT * FROM lineups WHERE id=?', (i,)).fetchone()
                user = owner if row['user_id'] == owner['id'] else other
                result, error, _ = moderate_lineup(admin, i, 'ban', {'version': row['version'], 'reason': '阵容码与名称描述不一致，请核对阵容码，并选择正确的所属赛季后重新提交。'})
                if error: raise RuntimeError(error)
                if i in [7, 19, 20, 21, 23, 24]:
                    result, error, _ = submit_revision(user, i, {'version': result['lineup']['version'], 'name': row['name'] + ' · 修正版', 'code': '#Corrected' + str(i) + 'MjM4OT', 'season_id': 's16-legends'})
                    if error: raise RuntimeError(error)
                    if i in [7, 20]:
                        result, error, _ = moderate_lineup(admin, i, 'reject', {'version': result['lineup']['version'], 'reason': '阵容码已修正，但所属赛季仍不匹配，请再次核对。'})
                    if i == 19:
                        result, error, _ = moderate_lineup(admin, i, 'approve', {'version': result['lineup']['version'], 'reason': '修改后的阵容码与赛季一致，已恢复原展示状态。'})
                if i == 3:
                    db.execute("UPDATE lineup_moderation SET notice_state='archived' WHERE lineup_id=?", (i,)); db.commit()
        port = int(os.environ.get('LINEUP_MODERATION_PREVIEW_PORT', '5112'))
        print(f'Moderation preview: http://127.0.0.1:{port}/admin | previewadmin / previewuser | Preview1234', flush=True)
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    serve()
