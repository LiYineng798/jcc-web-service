from admin_live_comp_service import (
    add_admin_live_comp_manual_code,
    build_admin_live_comps_payload,
    update_admin_live_comps_season,
)
from test_live_comps import sample_live_comps_payload, write_live_comps_seed


def test_build_admin_live_comps_payload_returns_selected_season_items(client):
    headers = {'X-CSRF-Token': client.get('/api/me').get_json()['csrf_token']}
    del headers
    path_cls = __import__('pathlib').Path
    json_module = __import__('json')
    season_dir = path_cls(client.application.config['LIVE_COMPS_SEASON_DIR'])
    season_dir.mkdir(parents=True, exist_ok=True)
    payload = sample_live_comps_payload()
    payload['tiers']['S'][0]['jccCode'] = ''
    (season_dir / 's16-legends.json').write_text(json_module.dumps(payload, ensure_ascii=False), encoding='utf-8')

    with client.application.app_context():
        data = build_admin_live_comps_payload('s16-legends', page=1, page_size=10)

    assert data['season']['id'] == 's16-legends'
    assert data['total'] == 1
    assert [item['id'] for item in data['items']] == ['s-01']
    assert data['items'][0]['codeSource'] == 'none'


def test_add_admin_live_comp_manual_code_adds_resolved_code(client):
    path_cls = __import__('pathlib').Path
    json_module = __import__('json')
    season_dir = path_cls(client.application.config['LIVE_COMPS_SEASON_DIR'])
    season_dir.mkdir(parents=True, exist_ok=True)
    payload = sample_live_comps_payload()
    payload['tiers']['S'][0]['jccCode'] = ''
    (season_dir / 's16-legends.json').write_text(json_module.dumps(payload, ensure_ascii=False), encoding='utf-8')

    with client.application.app_context():
        item, error, status_code = add_admin_live_comp_manual_code(
            admin_id=1,
            season_id='s16-legends',
            live_comp_id='s-01',
            data={'code': '【阵容码】##ADMIN001'},
        )
        refreshed = build_admin_live_comps_payload('s16-legends', page=1, page_size=10)

    assert error is None
    assert status_code == 200
    assert item['resolvedJccCode'] == '#ADMIN001'
    assert refreshed['items'] == []
    assert refreshed['total'] == 0


def test_add_admin_live_comp_manual_code_rejects_original_code_entry(client):
    write_live_comps_seed(client, sample_live_comps_payload())

    with client.application.app_context():
        item, error, status_code = add_admin_live_comp_manual_code(
            admin_id=1,
            season_id='s17-star-god',
            live_comp_id='s-01',
            data={'code': '【阵容码】##SHOULDFAIL'},
        )

    assert item is None
    assert status_code == 400
    assert error == '当前条目已有原始阵容码，无需补码'


def test_update_admin_live_comps_season_updates_manifest(client):
    manifest_path = client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH']
    path_cls = __import__('pathlib').Path
    path_cls(manifest_path).write_text(__import__('json').dumps({
        'default_season_id': 's17-star-god',
        'seasons': [{'id': 's17-star-god', 'name': 'S17 · 星神', 'status': 'active', 'order': 1, 'description': ''}],
    }, ensure_ascii=False), encoding='utf-8')

    with client.application.app_context():
        payload, error, status_code = update_admin_live_comps_season(
            admin_id=1,
            season_id='s17-star-god',
            data={'status': 'archived', 'description': '已归档'},
        )

    assert error is None
    assert status_code == 200
    assert payload['seasons'][0]['status'] == 'archived'
    assert payload['seasons'][0]['description'] == '已归档'


def test_update_admin_live_comps_season_moves_target_and_compacts_order(client):
    manifest_path = client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH']
    path_cls = __import__('pathlib').Path
    json_module = __import__('json')
    path_cls(manifest_path).write_text(json_module.dumps({
        'default_season_id': 's17-star-god',
        'seasons': [
            {'id': 's17-star-god', 'name': 'S17 · 星神', 'status': 'active', 'order': 1, 'description': ''},
            {'id': 's16-legends', 'name': 'S16 · 英雄联盟传奇', 'status': 'active', 'order': 2, 'description': ''},
            {'id': 'lucky-lantern', 'name': '天选福星', 'status': 'active', 'order': 3, 'description': ''},
            {'id': 's8-monsters-attack', 'name': 'S8·怪兽入侵', 'status': 'active', 'order': 4, 'description': ''},
        ],
    }, ensure_ascii=False), encoding='utf-8')

    with client.application.app_context():
        payload, error, status_code = update_admin_live_comps_season(
            admin_id=1,
            season_id='s8-monsters-attack',
            data={'order': 1},
        )

    assert error is None
    assert status_code == 200
    assert [season['id'] for season in payload['seasons']] == [
        's8-monsters-attack',
        's17-star-god',
        's16-5-legends',
        's16-legends',
        'lucky-lantern',
    ]
    assert [season['order'] for season in payload['seasons']] == [1, 2, 3, 4, 5]
