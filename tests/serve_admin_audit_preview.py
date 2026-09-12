"""Disposable loopback preview with fictional audit history, never production data."""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve():
    with tempfile.TemporaryDirectory(prefix='jcc-audit-preview-') as temporary:
        directory = Path(temporary)
        os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
        os.environ['JCC_DATABASE_URL'] = 'sqlite:///' + (directory / 'preview.sqlite3').as_posix()
        from app import create_app
        from audit import write_audit
        from db import get_db
        app = create_app({
            'TESTING': True, 'DATABASE': str(directory / 'preview.sqlite3'),
            'DATABASE_URL': os.environ['JCC_DATABASE_URL'],
            'SECRET_KEY': 'isolated-audit-preview-only', 'ADMIN_USERNAME': 'previewadmin',
            'ADMIN_PASSWORD': 'Preview1234', 'SESSION_COOKIE_SECURE': False,
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
        with app.app_context():
            db = get_db()
            db.execute("UPDATE users SET nickname = '站点管理员' WHERE username = 'previewadmin'")
            actor = db.execute("SELECT id FROM users WHERE username = 'previewadmin'").fetchone()['id']
            rows = [
                ('update_user', 'user', 26, None, {'nickname': '铲铲玩家', 'status': 'active', 'password_hash': 'preview-hash'}, {'nickname': '弈起上分', 'password': 'preview-secret'}),
                ('activate_notice', 'site_notice', 8, None, {'is_active': 0}, {'title': 'S18 资料库已更新', 'is_active': 1}),
                ('admin_update_lineup', 'lineup', 1286, None, {'title': '九五至尊', 'status': 'pending'}, {'status': 'published', 'description': '补充站位与装备说明'}),
                ('create_live_comps_season', 'live_comp_season', None, 's18', None, {'name': 'S18 · 仙灵奇遇', 'status': 'hidden'}),
                ('disable_user', 'user', 73, None, None, None),
                ('handle_report', 'report', 42, None, {'status': 'pending'}, {'status': 'resolved', 'hide_lineup': False}),
                ('admin_bulk_import_lineups', 'lineup_bulk_import', None, None, None, {'season_id': 's18', 'created_count': 12, 'duplicate_existing_count': 2}),
                ('generate_daily_report', 'daily_report', None, '2026-09-11', None, {'report_date': '2026-09-11'}),
                ('update_setting', 'app_setting', None, None, {'setting_key': 'site_title', 'setting_value': '阵容库'}, {'setting_key': 'site_title', 'setting_value': '金铲铲阵容库'}),
                ('delete_saved_notice', 'site_notice', 3, None, {'title': '过期维护通知'}, None),
                ('fail_live_comp_upload', 'live_comp_upload_job', None, 's18:demo-upload-22', None, {'error': '演示记录：上传文件格式不正确'}),
                ('create_lineup', 'lineup', 1290, None, None, {'title': '仙灵奇遇 · 九五', 'description': '<img src=x onerror=alert(1)>'}),
            ]
            for index in range(66):
                action, kind, target_id, key, before, after = rows[index % len(rows)]
                write_audit(actor, action, kind, target_id, before=before, after=after, target_key=key)
                log_id = db.execute('SELECT MAX(id) AS id FROM audit_logs').fetchone()['id']
                stamp = (datetime.now() - timedelta(minutes=(65 - index) * 17)).strftime('%Y-%m-%d %H:%M:%S')
                db.execute('UPDATE audit_logs SET created_at = ? WHERE id = ?', (stamp, log_id))
            # The first visible entry showcases the detailed, redacted field layout.
            write_audit(actor, *rows[0][:3], target_key=rows[0][3], before=rows[0][4], after=rows[0][5])
            db.commit()
        print('Audit preview: http://127.0.0.1:5098/admin — previewadmin / Preview1234', flush=True)
        app.run(host='127.0.0.1', port=int(os.environ.get('AUDIT_PREVIEW_PORT', '5098')), debug=False, use_reloader=False)


if __name__ == '__main__':
    serve()
