import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app


@pytest.fixture()
def app():
    db_path = ROOT / 'test-lineups.sqlite3'
    live_comps_path = ROOT / 'test-live-comps.json'
    live_comps_backup_path = ROOT / 'test-live-comps.previous.json'
    live_comps_asset_dir = ROOT / 'test-live-comps-assets'
    live_comps_manifest_path = ROOT / 'test-live-comps-seasons.json'
    live_comps_season_dir = ROOT / 'test-live-comps-seasons'
    live_comps_manual_code_dir = ROOT / 'test-live-comps-manual-codes'
    for path in [db_path, live_comps_path, live_comps_backup_path, live_comps_manifest_path]:
        if path.exists():
            path.unlink()
    for directory in [live_comps_asset_dir, live_comps_season_dir, live_comps_manual_code_dir]:
        import shutil
        if directory.exists():
            shutil.rmtree(directory)
    live_comps_manifest_path.write_text(
        '{"default_season_id":"s17-star-god","seasons":[{"id":"s17-star-god","name":"S17 · 星神","status":"active","order":1,"description":"当前赛季","data_file":"s17-star-god.json"},{"id":"s16-legends","name":"S16 · 英雄联盟传奇","status":"active","order":2,"description":"经典赛季","data_file":"s16-legends.json"},{"id":"lucky-lantern","name":"天选福星","status":"active","order":3,"description":"返场赛季","data_file":"lucky-lantern.json"},{"id":"s8-monsters-attack","name":"S8·怪兽入侵","status":"active","order":4,"description":"返场赛季","data_file":"s8-monsters-attack.json"}]}',
        encoding='utf-8',
    )
    app = create_app({
        'TESTING': True,
        'DATABASE': str(db_path),
        'SECRET_KEY': 'test-secret',
        'WTF_CSRF_ENABLED': True,
        'ADMIN_USERNAME': 'adminxlx',
        'ADMIN_PASSWORD': 'Admin1234',
        'LIVE_COMPS_DATA_PATH': str(live_comps_path),
        'LIVE_COMPS_BACKUP_PATH': str(live_comps_backup_path),
        'LIVE_COMPS_SEASON_MANIFEST_PATH': str(live_comps_manifest_path),
        'LIVE_COMPS_SEASON_DIR': str(live_comps_season_dir),
        'LIVE_COMPS_MANUAL_CODE_DIR': str(live_comps_manual_code_dir),
        'LIVE_COMPS_DEFAULT_SEASON_ID': 's17-star-god',
        'LIVE_COMPS_PAGE_SIZE': 6,
        'LIVE_COMPS_UPLOAD_TOKEN': 'upload-secret',
        'LIVE_COMPS_ASSET_DIR': str(live_comps_asset_dir),
    })
    yield app
    for path in [db_path, live_comps_path, live_comps_backup_path, live_comps_manifest_path]:
        if path.exists():
            path.unlink()
    for directory in [live_comps_asset_dir, live_comps_season_dir, live_comps_manual_code_dir]:
        import shutil
        if directory.exists():
            shutil.rmtree(directory)


@pytest.fixture()
def client(app):
    return app.test_client()
