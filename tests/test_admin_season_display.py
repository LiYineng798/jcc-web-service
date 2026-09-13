"""Public ordering is independent per surface and excludes inactive seasons."""
import json
from pathlib import Path

import pytest

from test_admin import login_admin


@pytest.mark.parametrize('kind', ['library', 'simulator'])
@pytest.mark.parametrize('status', ['hidden', 'disabled'])
def test_remove_reorder_and_restore_public_season(client, kind, status):
    headers = login_admin(client)
    endpoint = f'/api/admin/season-display/{kind}'
    original = client.get(endpoint).get_json()['items']
    other_kind = 'simulator' if kind == 'library' else 'library'
    other = client.get(f'/api/admin/season-display/{other_kind}').get_json()
    target = original[1]['season_id']
    response = client.put(f'{endpoint}/{target}', headers=headers, json={'status': status})
    assert response.status_code == 200
    assert response.get_json()['season']['order'] is None
    public = client.get(f'/api/season-catalog?surface={kind}').get_json()['seasons']
    assert [s['order'] for s in public] == list(range(1, len(public) + 1))
    assert target not in [s['season_id'] for s in public]
    # One downward move crosses to the next public season, never a hidden row.
    moved = client.put(f"{endpoint}/{public[0]['season_id']}", headers=headers, json={'order': 2})
    assert moved.status_code == 200
    assert moved.get_json()['items'][0]['season_id'] == public[1]['season_id']
    assert client.put(f'{endpoint}/{target}', headers=headers, json={'order': 1}).status_code == 400
    restored = client.put(f'{endpoint}/{target}', headers=headers, json={'status': 'archived'})
    assert restored.status_code == 200
    assert restored.get_json()['season']['order'] == len(original)
    assert client.get(endpoint).get_json()['items'][-1]['season_id'] == target
    assert client.get(f'/api/admin/season-display/{other_kind}').get_json() == other


def test_legacy_policy_compacts_without_writing_or_reexposing(client, app):
    headers = login_admin(client)
    path = Path(app.config['SEASON_VISIBILITY_PATH'])
    legacy = {'library': {
        's18': {'status': 'active', 'order': 10},
        's17': {'status': 'disabled', 'order': 20},
        's16_5': {'status': 'archived', 'order': 30},
        's8': {'status': 'hidden', 'order': 40},
    }}
    path.write_text(json.dumps(legacy), encoding='utf-8')
    before = path.read_bytes()
    items = client.get('/api/admin/season-display/library', headers=headers).get_json()['items']
    assert [(s['season_id'], s['order']) for s in items[:2]] == [('s18', 1), ('s16_5', 2)]
    assert all(s['order'] is None for s in items[2:])
    assert path.read_bytes() == before
    assert client.get('/tools/seasons/s17').status_code == 404
    assert client.get('/tools/seasons/s8').status_code == 404


def test_default_follows_remaining_public_seasons_and_first_restoration(client):
    headers = login_admin(client)
    endpoint = '/api/admin/season-display/simulator'
    items = client.get(endpoint).get_json()['items']
    for index, item in enumerate(items):
        response = client.put(f"{endpoint}/{item['season_id']}", headers=headers, json={'status': 'disabled'})
        assert response.status_code == 200
        expected = items[index + 1]['season_id'] if index + 1 < len(items) else None
        assert response.get_json()['default_season_id'] == expected
    assert client.get('/api/season-catalog?surface=simulator').get_json()['seasons'] == []
    response = client.put(f"{endpoint}/{items[-1]['season_id']}", headers=headers, json={'status': 'active'})
    assert response.get_json()['default_season_id'] == items[-1]['season_id']
    assert response.get_json()['season']['order'] == 1


def test_admin_navigation_has_one_shared_season_workspace(client):
    login_admin(client)
    html = client.get('/admin').get_data(as_text=True)
    assert html.count('data-admin-tab="season-display"') == 2  # Desktop and mobile.
    assert 'data-admin-tab="library-seasons"' not in html
    assert 'data-admin-tab="simulator-seasons"' not in html
    assert 'admin/season-display.js' in html
