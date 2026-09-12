"""Run the reviewed Web worktree with disposable SQLite/files on loopback."""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve():
    with tempfile.TemporaryDirectory(prefix='jcc-openings-preview-') as temporary:
        directory = Path(temporary)
        os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
        os.environ['JCC_DATABASE_URL'] = 'sqlite:///' + (directory / 'preview.sqlite3').as_posix()
        from app import create_app
        app = create_app({
            'TESTING': True, 'DATABASE': str(directory / 'preview.sqlite3'),
            'DATABASE_URL': os.environ['JCC_DATABASE_URL'],
            'SECRET_KEY': 'local-openings-preview', 'SESSION_COOKIE_SECURE': False,
            'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'),
            'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'),
            'LIVE_COMPS_BACKUP_DIR': str(directory / 'backups'),
            'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'),
            'LIVE_COMPS_SEASON_MANIFEST_PATH': str(directory / 'manifest.json'),
            'LIVE_COMPS_SEASON_DIR': str(directory / 'seasons'),
            'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'),
            'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'),
            'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
            'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
        })
        port = int(os.environ.get('OPENINGS_PREVIEW_PORT', '5105'))
        print(f'Preview: http://127.0.0.1:{port}/tools/s16-5-lucky-openings', flush=True)
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    serve()
