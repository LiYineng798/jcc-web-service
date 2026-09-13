import json
from pathlib import Path

import pytest

from test_admin import login_admin
from test_live_comps import sample_live_comps_payload, write_live_comps_seed

ENDPOINT = '/api/admin/live-comps/seasons'
PUBLIC = {'active', 'archived'}


@pytest.mark.parametrize('status', ['hidden', 'disabled'])
def test_inactive_seasons_leave_order_and_restore_at_end(client, status):
    headers = login_admin(client)
    before = client.get(ENDPOINT).get_json()['seasons']
    target = before[1]['id']
    response = client.put(f'{ENDPOINT}/{target}', headers=headers, json={'status': status})
    assert response.status_code == 200
    assert next(s for s in response.get_json()['seasons'] if s['id'] == target)['order'] is None
    public = client.get('/api/live-comps/seasons').get_json()['seasons']
    assert [s['order'] for s in public] == list(range(1, len(public) + 1))
    assert client.put(f"{ENDPOINT}/{public[0]['id']}", headers=headers, json={'order': 2}).status_code == 200
    moved = client.get('/api/live-comps/seasons').get_json()['seasons']
    assert moved[0]['id'] == public[1]['id']
    assert [s['id'] for s in moved] == [s['id'] for s in client.get('/api/lineup-seasons').get_json()['seasons']]
    assert client.put(f'{ENDPOINT}/{target}', headers=headers, json={'order': 1}).status_code == 400
    assert client.put(f'{ENDPOINT}/{target}', headers=headers, json={'default_season_id': target}).status_code == 400
    restored = client.put(f'{ENDPOINT}/{target}', headers=headers, json={'status': 'archived'})
    assert restored.status_code == 200
    assert restored.get_json()['seasons'][-1]['id'] == target
    assert restored.get_json()['seasons'][-1]['order'] == len(before)


def test_default_fallback_empty_and_restore(client):
    headers = login_admin(client)
    before = client.get(ENDPOINT).get_json()['seasons']
    for index, season in enumerate(before):
        response = client.put(f"{ENDPOINT}/{season['id']}", headers=headers, json={'status': 'disabled'})
        expected = before[index + 1]['id'] if index + 1 < len(before) else None
        assert response.get_json()['default_season_id'] == expected
        assert client.get('/api/live-comps/seasons').get_json()['default_season_id'] == expected
    assert client.get('/api/live-comps/seasons').get_json()['seasons'] == []
    assert client.get('/api/lineup-seasons').get_json()['seasons'] == []
    assert client.get('/api/live-comps').status_code == 404
    assert client.get('/api/admin/live-comps', headers=headers).status_code == 200
    response = client.put(f"{ENDPOINT}/{before[-1]['id']}", headers=headers, json={'status': 'active'})
    assert response.get_json()['default_season_id'] == before[-1]['id']
    assert response.get_json()['seasons'][0]['order'] == 1


def test_default_switch_does_not_read_old_season_payload(client):
    headers = login_admin(client)
    write_live_comps_seed(client, sample_live_comps_payload())
    assert client.get('/api/live-comps').get_json()['total'] > 0
    response = client.put(f'{ENDPOINT}/s17-star-god', headers=headers, json={'status': 'hidden'})
    assert response.get_json()['default_season_id'] == 's16-5-legends'
    assert client.get('/api/live-comps').get_json()['items'] == []
    assert client.get('/api/live-comps?season=s17-star-god').status_code == 404
    client.put(f'{ENDPOINT}/s17-star-god', headers=headers, json={'status': 'active'})
    assert client.get('/api/live-comps?season=s17-star-god').get_json()['total'] > 0


def test_legacy_manifest_read_keeps_files_and_data_seasons_separate(client, app):
    login_admin(client)
    data_seasons = client.get('/api/admin/season-display/library').get_json()
    path = Path(app.config['LIVE_COMPS_SEASON_MANIFEST_PATH'])
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['seasons'][1]['status'] = 'disabled'
    manifest['seasons'][3]['status'] = 'hidden'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    before = path.read_bytes()
    items = client.get(ENDPOINT).get_json()['seasons']
    assert [s['order'] for s in items if s['status'] in PUBLIC] == [1, 2, 3]
    assert all(s['order'] is None for s in items if s['status'] not in PUBLIC)
    assert path.read_bytes() == before
    assert client.get('/api/admin/season-display/library').get_json() == data_seasons


@pytest.mark.parametrize('payload', [{'status': 'unknown'}, {'order': 'bad'}, {'status': 'hidden', 'order': 1}])
def test_invalid_update_does_not_change_manifest(client, app, payload):
    headers = login_admin(client)
    path = Path(app.config['LIVE_COMPS_SEASON_MANIFEST_PATH'])
    before = path.read_bytes()
    assert client.put(f'{ENDPOINT}/s17-star-god', headers=headers, json=payload).status_code == 400
    assert path.read_bytes() == before
