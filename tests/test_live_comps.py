import json
import base64
from datetime import datetime, timedelta
from pathlib import Path

from db import get_db
import live_comps
import live_comps_helpers
from live_comp_manual_codes import set_manual_code_overlay_value


def sample_live_comps_payload():
    return {
        'meta': {'source': 'unit-test'},
        'tiers': {
            'S': [
                {
                    'id': f's-{index:02d}',
                    'title': f'S 阵容 {index}',
                    'tier': 'S',
                    'jccCode': f'#SCODE{index:02d}',
                    'mainAvatar': f'https://example.com/s-{index}.png',
                    'heroImages': [f'https://example.com/s-{index}-1.png'],
                }
                for index in range(1, 3)
            ],
            'A': [
                {
                    'id': f'a-{index:02d}',
                    'title': f'A 阵容 {index}',
                    'tier': 'A',
                    'jccCode': f'#ACODE{index:02d}',
                    'mainAvatar': f'https://example.com/a-{index}.png',
                    'heroImages': [f'https://example.com/a-{index}-1.png'],
                }
                for index in range(1, 3)
            ],
            'B': [
                {
                    'id': 'b-01',
                    'title': 'B 阵容 1',
                    'tier': 'B',
                    'jccCode': '#BCODE01',
                    'mainAvatar': 'https://example.com/b-1.png',
                    'heroImages': ['https://example.com/b-1-1.png'],
                }
            ],
            'C': [
                {
                    'id': 'c-01',
                    'title': 'C 阵容 1',
                    'tier': 'C',
                    'jccCode': '#CCODE01',
                    'mainAvatar': 'https://example.com/c-1.png',
                    'heroImages': ['https://example.com/c-1-1.png'],
                }
            ],
            'D': [
                {
                    'id': 'd-01',
                    'title': 'D 阵容 1',
                    'tier': 'D',
                    'jccCode': '#DCODE01',
                    'mainAvatar': 'https://example.com/d-1.png',
                    'heroImages': ['https://example.com/d-1-1.png'],
                }
            ],
        },
    }


def write_live_comps_seed(client, payload):
    data_path = Path(client.application.config['LIVE_COMPS_DATA_PATH'])
    data_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def test_live_comps_summary_returns_empty_totals_when_file_missing(client):
    data = client.get('/api/live-comps/summary').get_json()
    assert data['tiers'] == [
        {'tier': 'S', 'total': 0},
        {'tier': 'A', 'total': 0},
        {'tier': 'B', 'total': 0},
        {'tier': 'C', 'total': 0},
        {'tier': 'D', 'total': 0},
    ]
    assert data['updated_at'] is None


def test_live_comps_seasons_falls_back_to_default_manifest(client):
    data = client.get('/api/live-comps/seasons').get_json()

    assert data['default_season_id'] == 's17-star-god'
    assert [season['id'] for season in data['seasons']] == ['s17-star-god', 's16-legends', 'lucky-lantern', 's8-monsters-attack']
    assert data['seasons'][0]['id'] == 's17-star-god'
    assert data['seasons'][0]['status'] == 'active'


def test_live_comps_seasons_hides_private_entries_from_public(client):
    manifest_path = Path(client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH'])
    manifest_path.write_text(json.dumps({
        'default_season_id': 's17-star-god',
        'seasons': [
            {'id': 's17-star-god', 'name': 'S17 · 星神', 'status': 'active', 'order': 1},
            {'id': 's16-legends', 'name': 'S16 · 英雄联盟传奇', 'status': 'active', 'order': 2},
            {'id': 'secret', 'name': '隐藏赛季', 'status': 'hidden', 'order': 2},
        ],
    }, ensure_ascii=False), encoding='utf-8')

    data = client.get('/api/live-comps/seasons').get_json()

    assert [season['id'] for season in data['seasons']] == ['s17-star-god', 's16-legends', 'lucky-lantern', 's8-monsters-attack']


def test_live_comps_summary_returns_empty_for_public_season_without_payload(client):
    summary = client.get('/api/live-comps/summary?season=s16-legends').get_json()
    listing = client.get('/api/live-comps?season=s16-legends').get_json()

    assert summary['season']['id'] == 's16-legends'
    assert summary['tiers'] == [
        {'tier': 'S', 'total': 0},
        {'tier': 'A', 'total': 0},
        {'tier': 'B', 'total': 0},
        {'tier': 'C', 'total': 0},
        {'tier': 'D', 'total': 0},
    ]
    assert listing['total'] == 0
    assert listing['items'] == []


def test_upload_live_comps_registers_missing_season(client):
    payload = sample_live_comps_payload()
    import live_comps
    def fake_download(url):
        return b'image-bytes', 'image/jpeg'
    live_comps_helpers.download_live_comp_image = fake_download
    response = client.post(
        '/api/live-comps/upload?season=s18-new-season',
        json=payload,
        headers={'X-Upload-Token': 'upload-secret'},
    )

    assert response.status_code == 200
    manifest = json.loads(Path(client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH']).read_text(encoding='utf-8'))
    assert any(season['id'] == 's18-new-season' for season in manifest['seasons'])


def test_live_comps_season_query_reads_separate_payload(client):
    season_dir = Path(client.application.config['LIVE_COMPS_SEASON_DIR'])
    season_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH'])
    manifest_path.write_text(json.dumps({
        'default_season_id': 's17-star-god',
        'seasons': [
            {'id': 's17-star-god', 'name': 'S17 · 星神', 'status': 'active', 'order': 1},
            {'id': 's16-legends', 'name': 'S16 · 英雄联盟传奇', 'status': 'active', 'order': 2},
        ],
    }, ensure_ascii=False), encoding='utf-8')
    s17_payload = sample_live_comps_payload()
    s16_payload = sample_live_comps_payload()
    s16_payload['tiers']['S'] = [s16_payload['tiers']['S'][0]]
    (season_dir / 's17-star-god.json').write_text(json.dumps(s17_payload, ensure_ascii=False), encoding='utf-8')
    (season_dir / 's16-legends.json').write_text(json.dumps(s16_payload, ensure_ascii=False), encoding='utf-8')

    summary = client.get('/api/live-comps/summary?season=s16-legends').get_json()
    data = client.get('/api/live-comps?season=s16-legends').get_json()

    assert summary['season']['id'] == 's16-legends'
    assert summary['tiers'][0] == {'tier': 'S', 'total': 1}
    assert data['total'] == 6


def test_live_comps_list_returns_second_page_for_combined_ranking(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    data = client.get('/api/live-comps?page=2').get_json()
    assert data['page'] == 2
    assert data['page_size'] == 6
    assert data['total'] == 7
    assert data['total_pages'] == 2
    assert [item['id'] for item in data['items']] == ['d-01']


def test_live_comps_list_rejects_unknown_tier(client):
    response = client.get('/api/live-comps?tier=Z&page=1')
    assert response.status_code == 400
    assert response.get_json()['error'] == '无效段位'


def test_live_comps_summary_falls_back_to_empty_when_payload_invalid(client):
    data_path = Path(client.application.config['LIVE_COMPS_DATA_PATH'])
    data_path.write_text('{"tiers":{"S":"broken"}}', encoding='utf-8')
    payload = client.get('/api/live-comps/summary').get_json()
    assert payload['tiers'][0] == {'tier': 'S', 'total': 0}
    assert payload['source_meta']['is_valid'] is False


def test_live_comps_summary_exposes_meta_and_totals(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    payload = client.get('/api/live-comps/summary').get_json()
    assert payload['tiers'][0] == {'tier': 'S', 'total': 2}
    assert payload['source_meta']['source'] == 'unit-test'


def test_live_comps_list_uses_combined_default_page_size_and_tier_order(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    payload = client.get('/api/live-comps').get_json()
    assert len(payload['items']) == 6
    assert payload['page_size'] == 6
    assert [item['tier'] for item in payload['items']] == ['S', 'S', 'A', 'A', 'B', 'C']


def test_live_comps_tier_filter_still_available_for_debugging(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    payload = client.get('/api/live-comps?tier=S').get_json()
    assert payload['tier'] == 'S'
    assert payload['total'] == 2
    assert [item['id'] for item in payload['items']] == ['s-01', 's-02']


def test_live_comps_list_normalizes_wrapped_lineup_code_for_copying(client):
    payload = sample_live_comps_payload()
    payload['tiers']['S'][0]['jccCode'] = '【阵容码】##MjIwMDIzMzMzOTU3NzQ4MzcxNzc3OTAxNzUwMDU4'
    write_live_comps_seed(client, payload)

    response = client.get('/api/live-comps').get_json()

    assert response['items'][0]['jccCode'] == '#MjIwMDIzMzMzOTU3NzQ4MzcxNzc3OTAxNzUwMDU4'


def test_live_comps_upload_allows_items_without_jcc_code(client):
    payload = {
        'meta': {'source': 's16-no-code'},
        'tiers': {
            'S': [{
                'id': 's16-s-01',
                'title': 'S16 阵容 1',
                'tier': 'S',
                'jccCode': '',
                'mainAvatar': 'https://example.com/s16-s-1.png',
                'heroImages': ['https://example.com/s16-s-1-1.png'],
            }],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }
    import live_comps

    def fake_download(url):
        return b'image-bytes', 'image/png'

    live_comps_helpers.download_live_comp_image = fake_download
    response = client.post(
        '/api/live-comps/upload?season=s16-legends',
        json=payload,
        headers={'X-Upload-Token': 'upload-secret'},
    )

    assert response.status_code == 200
    summary = client.get('/api/live-comps/summary?season=s16-legends').get_json()
    listing = client.get('/api/live-comps?season=s16-legends').get_json()
    assert summary['tiers'][0] == {'tier': 'S', 'total': 1}
    assert listing['items'][0]['id'] == 's16-s-01'
    assert listing['items'][0]['jccCode'] == ''


def test_live_comps_upload_requires_valid_token(client):
    response = client.post('/api/live-comps/upload', json={'tiers': {}})
    assert response.status_code == 401
    assert response.get_json()['error'] == '上传令牌无效'


def test_live_comps_upload_replaces_data_and_keeps_previous_backup(client):
    old_payload = {
        'meta': {'source': 'old'},
        'tiers': {
            'S': [{'id': 'old-s', 'title': '旧 S', 'tier': 'S', 'jccCode': '#OLD001', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [], 'B': [], 'C': [], 'D': [],
        },
    }
    new_payload = {
        'meta': {'source': 'new'},
        'tiers': {
            'S': [{'id': 'new-s', 'title': '新 S', 'tier': 'S', 'jccCode': '#NEW001', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [], 'B': [], 'C': [], 'D': [],
        },
    }
    data_path = Path(client.application.config['LIVE_COMPS_DATA_PATH'])
    backup_path = Path(client.application.config['LIVE_COMPS_BACKUP_PATH'])
    data_path.write_text(json.dumps(old_payload, ensure_ascii=False), encoding='utf-8')

    response = client.post(
        '/api/live-comps/upload',
        json=new_payload,
        headers={'X-Upload-Token': 'upload-secret'},
    )

    assert response.status_code == 200
    assert response.get_json()['ok'] is True
    assert json.loads(data_path.read_text(encoding='utf-8'))['meta']['source'] == 'new'
    assert json.loads(backup_path.read_text(encoding='utf-8'))['meta']['source'] == 'old'


def test_live_comps_upload_rejects_invalid_payload_without_overwriting_existing_data(client):
    original = {
        'meta': {'source': 'safe'},
        'tiers': {
            'S': [{'id': 'safe-s', 'title': '保留 S', 'tier': 'S', 'jccCode': '#SAFE001', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [], 'B': [], 'C': [], 'D': [],
        },
    }
    data_path = Path(client.application.config['LIVE_COMPS_DATA_PATH'])
    data_path.write_text(json.dumps(original, ensure_ascii=False), encoding='utf-8')

    response = client.post(
        '/api/live-comps/upload',
        json={'meta': {'source': 'broken'}, 'tiers': {'S': 'bad'}},
        headers={'X-Upload-Token': 'upload-secret'},
    )

    assert response.status_code == 400
    assert 'S 段位必须是数组' in response.get_json()['error']


def test_live_comps_list_uses_manual_code_when_original_code_is_missing(client):
    payload = sample_live_comps_payload()
    payload['tiers']['A'][0]['jccCode'] = ''
    write_live_comps_seed(client, payload)
    set_manual_code_overlay_value(
        client.application.config['LIVE_COMPS_MANUAL_CODE_DIR'],
        's17-star-god',
        'a-01',
        '【阵容码】##MANUALA01',
        admin_id=1,
        now_value='2026-05-24T10:00:00',
    )

    data = client.get('/api/live-comps').get_json()
    item = next(row for row in data['items'] if row['id'] == 'a-01')

    assert item['jccCode'] == '#MANUALA01'
    assert item['resolvedJccCode'] == '#MANUALA01'
    assert item['originalJccCode'] == ''
    assert item['codeSource'] == 'manual'
    assert item['hasCode'] is True


def test_live_comps_upload_prunes_manual_code_only_when_new_upload_provides_original_code(client):
    def fake_download(url):
        return b'image-bytes', 'image/png'

    live_comps_helpers.download_live_comp_image = fake_download
    set_manual_code_overlay_value(
        client.application.config['LIVE_COMPS_MANUAL_CODE_DIR'],
        's16-legends',
        's16-s-01',
        '【阵容码】##MANUALS16',
        admin_id=3,
        now_value='2026-05-24T10:00:00',
    )
    keep_payload = {
        'meta': {'source': 'keep'},
        'tiers': {
            'S': [{
                'id': 's16-s-01',
                'title': 'S16 阵容 1',
                'tier': 'S',
                'jccCode': '',
                'mainAvatar': 'https://example.com/a.png',
                'heroImages': ['https://example.com/b.png'],
            }],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }
    replace_payload = {
        'meta': {'source': 'replace'},
        'tiers': {
            'S': [{
                'id': 's16-s-01',
                'title': 'S16 阵容 1',
                'tier': 'S',
                'jccCode': '#UPLOADED001',
                'mainAvatar': 'https://example.com/a.png',
                'heroImages': ['https://example.com/b.png'],
            }],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }

    keep = client.post('/api/live-comps/upload?season=s16-legends', json=keep_payload, headers={'X-Upload-Token': 'upload-secret'})
    keep_listing = client.get('/api/live-comps?season=s16-legends').get_json()
    replace = client.post('/api/live-comps/upload?season=s16-legends', json=replace_payload, headers={'X-Upload-Token': 'upload-secret'})
    replace_listing = client.get('/api/live-comps?season=s16-legends').get_json()

    assert keep.status_code == 200
    assert next(row for row in keep_listing['items'] if row['id'] == 's16-s-01')['jccCode'] == '#MANUALS16'
    assert replace.status_code == 200
    assert next(row for row in replace_listing['items'] if row['id'] == 's16-s-01')['jccCode'] == '#UPLOADED001'


def test_live_comps_upload_rejects_oversized_request(client):
    client.application.config['LIVE_COMPS_MAX_UPLOAD_BYTES'] = 20
    response = client.post(
        '/api/live-comps/upload',
        data='x' * 21,
        headers={
            'Content-Type': 'application/json',
            'X-Upload-Token': 'upload-secret',
        },
    )
    assert response.status_code == 413
    assert response.get_json()['error'] == '上传文件过大'


def test_live_comps_upload_returns_tier_counts(client):
    payload = {
        'meta': {'source': 'summary-check'},
        'tiers': {
            'S': [{'id': 's1', 'title': 'S1', 'tier': 'S', 'jccCode': '#S1', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [{'id': 'a1', 'title': 'A1', 'tier': 'A', 'jccCode': '#A1', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'B': [], 'C': [], 'D': [],
        },
    }
    response = client.post(
        '/api/live-comps/upload',
        json=payload,
        headers={'X-Upload-Token': 'upload-secret'},
    )
    data = response.get_json()
    assert data['tiers'] == {'S': 1, 'A': 1, 'B': 0, 'C': 0, 'D': 0}
    assert data['total'] == 2


def test_live_comps_upload_caches_remote_images_and_rewrites_urls(client, monkeypatch):
    payload = {
        'meta': {'source': 'image-cache'},
        'tiers': {
            'S': [{
                'id': 's-cache',
                'title': '缓存图片阵容',
                'tier': 'S',
                'jccCode': '#CACHE001',
                'mainAvatar': 'https://static.datatft.com/images/heros/default/917033.jpg',
                'heroImages': ['https://static.datatft.com/images/heros/default/917034.jpg'],
            }],
            'A': [], 'B': [], 'C': [], 'D': [],
        },
    }

    def fake_download(url):
        return b'image-bytes', 'image/jpeg'

    monkeypatch.setattr(live_comps_helpers, 'download_live_comp_image', fake_download)

    response = client.post(
        '/api/live-comps/upload',
        json=payload,
        headers={'X-Upload-Token': 'upload-secret'},
    )
    saved = json.loads(Path(client.application.config['LIVE_COMPS_DATA_PATH']).read_text(encoding='utf-8'))
    item = saved['tiers']['S'][0]

    assert response.status_code == 200
    assert item['mainAvatar'].startswith('/api/live-comps/assets/')
    assert item['heroImages'][0].startswith('/api/live-comps/assets/')
    assert not item['mainAvatar'].startswith('https://static.datatft.com')
    assert client.get(item['mainAvatar']).data == b'image-bytes'


def test_live_comp_asset_upload_accepts_pre_cached_image(client):
    response = client.post(
        '/api/live-comps/assets/upload',
        json={
            'filename': 'abc123.jpg',
            'content_base64': base64.b64encode(b'asset-bytes').decode('ascii'),
        },
        headers={'X-Upload-Token': 'upload-secret'},
    )

    assert response.status_code == 200
    assert response.get_json()['url'] == '/api/live-comps/assets/abc123.jpg'
    assert client.get('/api/live-comps/assets/abc123.jpg').data == b'asset-bytes'


def test_live_comp_copy_endpoint_increments_copy_count(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    csrf = client.get('/api/me').get_json()['csrf_token']

    first = client.post('/api/live-comps/s-01/copy', headers={'X-CSRF-Token': csrf})
    second = client.post('/api/live-comps/a-02/copy', headers={'X-CSRF-Token': csrf})

    assert first.status_code == 200
    assert first.get_json()['today_copy_count'] == 1
    assert first.get_json()['total_copy_count'] == 1
    assert second.status_code == 200
    assert second.get_json()['today_copy_count'] == 2
    assert second.get_json()['total_copy_count'] == 2


def test_live_comp_copy_records_raw_copy_action_with_season(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    csrf = client.get('/api/me').get_json()['csrf_token']

    response = client.post('/api/live-comps/s-01/copy?season=s17-star-god&source=home', headers={'X-CSRF-Token': csrf})

    assert response.status_code == 200
    with client.application.app_context():
        row = get_db().execute(
            'SELECT target_type, target_id, season_id, source_page, success, counted FROM copy_action_events'
        ).fetchone()
    assert dict(row) == {
        'target_type': 'live_comp',
        'target_id': 's-01',
        'season_id': 's17-star-god',
        'source_page': 'home',
        'success': 1,
        'counted': 1,
    }


def test_live_comp_copy_endpoint_resets_today_count_but_keeps_total_count(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    with client.application.app_context():
        db = get_db()
        db.execute(
            '''INSERT INTO live_comp_global_stats (stats_key, total_copy_count, created_at, updated_at)
               VALUES ('global', 5, ?, ?)''',
            (f'{yesterday} 10:00:00', f'{yesterday} 10:00:00'),
        )
        db.execute(
            '''INSERT INTO live_comp_global_daily_stats (copy_date, copy_count, created_at, updated_at)
               VALUES (?, 5, ?, ?)''',
            (yesterday, f'{yesterday} 10:00:00', f'{yesterday} 10:00:00'),
        )
        db.commit()
    csrf = client.get('/api/me').get_json()['csrf_token']

    response = client.post('/api/live-comps/s-01/copy', headers={'X-CSRF-Token': csrf})

    assert response.status_code == 200
    assert response.get_json()['today_copy_count'] == 1
    assert response.get_json()['total_copy_count'] == 6


def test_live_comp_copy_endpoint_rejects_unknown_live_comp_id(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    csrf = client.get('/api/me').get_json()['csrf_token']

    response = client.post('/api/live-comps/not-found/copy', headers={'X-CSRF-Token': csrf})

    assert response.status_code == 404
    assert response.get_json()['error'] == '实时阵容不存在'


def test_live_comp_copy_endpoint_rejects_live_comp_without_jcc_code(client):
    payload = sample_live_comps_payload()
    payload['tiers']['S'][0]['jccCode'] = ''
    write_live_comps_seed(client, payload)
    csrf = client.get('/api/me').get_json()['csrf_token']

    response = client.post('/api/live-comps/s-01/copy', headers={'X-CSRF-Token': csrf})

    assert response.status_code == 400
    assert response.get_json()['error'] == '当前阵容暂无可复制的阵容码'
