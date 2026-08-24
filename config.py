import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def apply_config(app, test_config=None):
    default_sqlite_path = os.path.join(app.instance_path, 'lineups.sqlite3')
    default_database_url = 'sqlite:///' + default_sqlite_path.replace('\\', '/')
    database_url = os.environ.get('JCC_DATABASE_URL', default_database_url)
    app.config.from_mapping(
        DATABASE=default_sqlite_path,
        DATABASE_URL=database_url,
        LIVE_COMPS_DATA_PATH=os.path.join(app.instance_path, 'live-comps.json'),
        LIVE_COMPS_BACKUP_PATH=os.path.join(app.instance_path, 'live-comps.previous.json'),
        LIVE_COMPS_BACKUP_DIR=os.path.join(app.instance_path, 'live-comps-backups'),
        LIVE_COMPS_ASSET_DIR=os.path.join(app.instance_path, 'live-comps-assets'),
        LIVE_COMPS_SEASON_MANIFEST_PATH=os.path.join(app.instance_path, 'live-comps-seasons.json'),
        LIVE_COMPS_SEASON_DIR=os.path.join(app.instance_path, 'live-comps-seasons'),
        LIVE_COMPS_MANUAL_CODE_DIR=os.path.join(app.instance_path, 'live-comps-manual-codes'),
        SEASON_VISIBILITY_PATH=os.path.join(app.instance_path, 'season-visibility.json'),
        LIVE_COMPS_DEFAULT_SEASON_ID=os.environ.get('JCC_LIVE_COMPS_DEFAULT_SEASON_ID', 's17-star-god'),
        LIVE_COMPS_PAGE_SIZE=6,
        LIVE_COMPS_MAX_UPLOAD_BYTES=5 * 1024 * 1024,
        LIVE_COMPS_UPLOAD_JOB_DIR=os.path.join(app.instance_path, 'live-comps-upload-jobs'),
        LIVE_COMPS_UPLOAD_WORKER_ENABLED=True,
        LIVE_COMPS_UPLOAD_TOKEN=os.environ.get('JCC_LIVE_COMPS_UPLOAD_TOKEN', ''),
        SECRET_KEY=os.environ.get('JCC_SECRET_KEY', 'dev-secret-change-me'),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=False,
        ADMIN_USERNAME=os.environ.get('JCC_ADMIN_USERNAME', 'adminxlx'),
        ADMIN_PASSWORD=os.environ.get('JCC_ADMIN_PASSWORD', 'Admin1234'),
    )
    if test_config:
        app.config.update(test_config)
