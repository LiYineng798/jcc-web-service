import json
from pathlib import Path

from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_system_lineup_does_not_link_to_private_admin_profile(client):
    assert client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'}).status_code == 200
    lineup = create_lineup(client, name='系统阵容').get_json()
    client.post('/api/logout')
    payload = client.get(f'/api/lineups/{lineup["id"]}').get_json()
    assert payload['owner_nickname'] == '系统'
    assert payload['owner_profile_url'] is None
    html = client.get(f'/lineup/{lineup["id"]}').get_data(as_text=True)
    assert '<strong class="ld-author-name">系统</strong>' in html
    assert '/author/adminxlx' not in html
    assert client.get('/author/adminxlx').status_code == 404
    assert client.get('/api/lineups').get_json()[0]['owner_profile_url'] is None


def test_regular_author_link_uses_role_even_when_nickname_is_system(client):
    register_user(client, username='authorlink', email='authorlink@example.com', nickname='系统')
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    payload = client.get(f'/api/lineups/{lineup["id"]}').get_json()
    assert payload['owner_profile_url'] == '/author/authorlink'
    html = client.get(f'/lineup/{lineup["id"]}').get_data(as_text=True)
    assert 'href="/author/authorlink"' in html
    assert client.get(payload['owner_profile_url']).status_code == 200


def test_detail_uses_dynamic_lineup_season_name_and_keeps_complete_code(client):
    manifest_path = Path(client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH'])
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['seasons'].append({
        'id': 's18-preview', 'name': '新赛季 · 示例', 'status': 'active',
        'order': 10, 'data_file': 's18-preview.json',
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    register_user(client, username='detailowner', email='detailowner@example.com')
    code = '#COMPLETE' + '0123456789' * 20
    response = create_lineup(client, name='新赛季阵容', code=code, season_id='s18-preview')
    assert response.status_code == 201
    lineup_id = response.get_json()['id']
    owner_html = client.get(f'/lineup/{lineup_id}').get_data(as_text=True)
    assert f'href="/lineup/{lineup_id}/edit"' in owner_html
    client.post('/api/logout')
    html = client.get(f'/lineup/{lineup_id}').get_data(as_text=True)
    assert '新赛季 · 示例' in html
    assert 's18-preview' not in html
    assert code in html
    assert f'href="/lineup/{lineup_id}/edit"' not in html
