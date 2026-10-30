"""Loopback-only preview with disposable data for notice and audit review."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve():
    os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
    with tempfile.TemporaryDirectory(prefix='jcc-notice-preview-') as temporary:
        directory = Path(temporary)
        from app import create_app
        from db import get_db
        from notice_service import create_notice, activate_notice
        app = create_app({
            'TESTING': True, 'DATABASE': str(directory / 'preview.sqlite3'),
            'DATABASE_URL': 'sqlite:///' + (directory / 'preview.sqlite3').as_posix(),
            'SECRET_KEY': 'isolated-notice-preview-only',
            'ADMIN_USERNAME': 'previewadmin', 'ADMIN_PASSWORD': 'Preview1234',
            'SESSION_COOKIE_SECURE': False,
            'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
            'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
            'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'),
            'LIVE_COMPS_SEASON_MANIFEST_PATH': str(directory / 'seasons.json'),
            'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'),
        })
        with app.app_context():
            db = get_db()
            actor = db.execute("SELECT id FROM users WHERE username='previewadmin'").fetchone()['id']
            notice, _, _ = create_notice(db, actor, {
                'title': '时间卡片图鉴已上线', 'message': '查阅五大品阶、传送门规则与完整效果，让每一次选择更有把握。',
                'target_kind': 'tool', 'tool_id': 'orange-fortune', 'link_text': '打开时间卡片图鉴',
                'marquee_enabled': False,
            })
            activate_notice(db, actor, notice['id'])
            create_notice(db, actor, {'title': '一起完善阵容库', 'message': '有想要的工具或改进建议？欢迎告诉我们。', 'target_kind': 'guestbook'})
        print('Notice preview: http://127.0.0.1:5138/admin — previewadmin / Preview1234', flush=True)
        app.run(host='127.0.0.1', port=int(os.environ.get('NOTICE_PREVIEW_PORT', '5138')), debug=False, use_reloader=False)


if __name__ == '__main__':
    serve()
