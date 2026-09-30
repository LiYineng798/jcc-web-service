"""Loopback-only preview with fictional lineups and visitor activity."""
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve():
    os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
    from app import create_app
    from db import get_db, now_text
    from daily_report_service import ensure_daily_report

    directory = ROOT / 'instance' / 'mobile-admin-report-preview'
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / 'seasons.json'
    seasons = [
        {'id': 's11-inkborn-fables', 'name': 'S11 · 画之灵', 'status': 'active', 'order': 1, 'data_file': 's11-inkborn-fables.json'},
        {'id': 's17-star-god', 'name': 'S17 · 星神', 'status': 'active', 'order': 2, 'data_file': 's17-star-god.json'},
    ]
    manifest.write_text(json.dumps({'default_season_id': seasons[0]['id'], 'seasons': seasons}, ensure_ascii=False), encoding='utf-8')
    season_dir = directory / 'seasons'
    season_dir.mkdir(exist_ok=True)
    portraits = sorted((ROOT / 'static/season-data/s11/assets/optimized').glob('*/champions/*.webp'))[:8]
    assets = directory / 'assets'
    assets.mkdir(exist_ok=True)
    image_urls = []
    for index, path in enumerate(portraits):
        filename = f'preview-champion-{index}.webp'
        shutil.copyfile(path, assets / filename)
        image_urls.append('/api/live-comps/assets/' + filename)
    image_urls = image_urls or ['/static/favicon.png']
    names = ['天龙九五', '七灵魂莲华', '山海克格莫', '斗射卡莎', '吉星九五', '青花瓷艾希']
    payload = {'meta': {'source': 'local-preview'}, 'tiers': {'S': [
        {'id': f'preview-{index}', 'title': name, 'tier': 'S', 'jccCode': f'#Preview{index}JCC1234',
         'mainAvatar': image_urls[index % len(image_urls)], 'heroImages': image_urls[:6]}
        for index, name in enumerate(names)
    ], 'A': [], 'B': [], 'C': [], 'D': []}}
    (season_dir / seasons[0]['data_file']).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    app = create_app({
        'TESTING': True, 'DATABASE': str(directory / 'preview.sqlite3'), 'DATABASE_URL': 'sqlite:///preview',
        'SECRET_KEY': 'local-mobile-admin-report-preview-only', 'ADMIN_USERNAME': 'previewadmin',
        'ADMIN_PASSWORD': 'Preview1234', 'SESSION_COOKIE_SECURE': False,
        'DAILY_REPORT_WORKER_ENABLED': False, 'RESEND_API_KEY': '',
        'LIVE_COMPS_SEASON_MANIFEST_PATH': str(manifest), 'LIVE_COMPS_SEASON_DIR': str(season_dir),
        'LIVE_COMPS_DEFAULT_SEASON_ID': seasons[0]['id'], 'LIVE_COMPS_DATA_PATH': str(directory / 'live.json'),
        'LIVE_COMPS_BACKUP_PATH': str(directory / 'previous.json'), 'LIVE_COMPS_ASSET_DIR': str(directory / 'assets'),
        'LIVE_COMPS_MANUAL_CODE_DIR': str(directory / 'codes'), 'LIVE_COMPS_UPLOAD_JOB_DIR': str(directory / 'jobs'),
        'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'), 'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
    })
    with app.app_context():
        db = get_db()
        owner = db.execute("SELECT id FROM users WHERE username='previewadmin'").fetchone()['id']
        if not db.execute('SELECT id FROM lineups LIMIT 1').fetchone():
            now = now_text()
            for index in range(28):
                db.execute('''INSERT INTO lineups
                    (user_id,name,code,season_id,status,admin_like_adjustment,admin_copy_adjustment,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (owner, names[index % len(names)] + (f' · {index + 1}' if index > 5 else ''),
                     f'#PreviewLineup{index}JCC1234', seasons[index % 2]['id'], 'hidden' if index % 9 == 0 else 'normal',
                     (index * 7) % 31, (index * 13) % 67, now, now))
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            page_keys = ['home', 'live_comp_detail', 'season_reference', 'trait_ladder', 'witch_rewards',
                         'lineup_detail', 'auth', 'season_champion_detail', 'golden_egg', 's11_items']
            for ip_index, count in enumerate([10, 7, 4]):
                ip = f'192.0.2.{ip_index + 10}'
                for visitor in range(2 if ip_index == 0 else 1):
                    for page_index, key in enumerate(page_keys[:count]):
                        timestamp = f'{date} {8 + page_index:02d}:{visitor * 15:02d}:00'
                        db.execute('''INSERT INTO visit_events
                            (visit_date,visitor_key,visitor_kind,visitor_token,ip_address,page_key,created_at)
                            VALUES (?,?,'guest_token',?,?,?,?)''',
                            (date, f'preview-{ip_index}-{visitor}', f'token-{ip_index}-{visitor}', ip, key, timestamp))
                db.execute('''INSERT INTO copy_action_events
                    (target_type,target_id,season_id,lineup_id,visitor_token,ip_address,source_page,success,counted,created_at)
                    VALUES ('lineup',?, ?, ?, ?, ?, 'home', 1, 1, ?)''',
                    (str(ip_index + 1), seasons[0]['id'], ip_index + 1, f'token-{ip_index}-0', ip, f'{date} 12:30:00'))
            db.commit()
            ensure_daily_report(date)
    port = int(os.environ.get('MOBILE_ADMIN_REPORT_PREVIEW_PORT', '5127'))
    print(f'Preview: http://127.0.0.1:{port} | previewadmin / Preview1234', flush=True)
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    serve()
