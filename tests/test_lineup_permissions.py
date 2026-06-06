from pathlib import Path

from test_auth import register_user


def csrf(client):
    return client.get('/api/me').get_json()['csrf_token']


def auth_headers(client):
    return {'X-CSRF-Token': csrf(client)}


def create_lineup(client, name='阵容A', code='#CODE123', status='normal', season_id='s17-star-god'):
    return client.post('/api/lineups', json={'name': name, 'code': code, 'status': status, 'season_id': season_id}, headers=auth_headers(client))


def test_create_lineup_accepts_explicit_season_id(client):
    register_user(client)
    response = client.post(
        '/api/lineups',
        json={'name': 'S16 阵容', 'code': '#S16001', 'status': 'normal', 'season_id': 's16-legends'},
        headers=auth_headers(client),
    )
    assert response.status_code == 201
    assert response.get_json()['season_id'] == 's16-legends'


def test_update_lineup_rejects_unavailable_season_id(client):
    register_user(client)
    lineup = create_lineup(client, season_id='s17-star-god').get_json()

    response = client.put(
        f"/api/lineups/{lineup['id']}",
        json={
            'name': lineup['name'],
            'code': lineup['code'],
            'season_id': 'unknown-season',
            'version': lineup['version'],
        },
        headers=auth_headers(client),
    )

    assert response.status_code == 400


def test_lineup_list_filters_by_selected_season(client):
    register_user(client)
    client.post('/api/lineups', json={'name': 'S17 阵容', 'code': '#S17001', 'season_id': 's17-star-god'}, headers=auth_headers(client))
    client.post('/api/lineups', json={'name': 'S16 阵容', 'code': '#S16001', 'season_id': 's16-legends'}, headers=auth_headers(client))
    client.post('/api/lineups', json={'name': '福星 阵容', 'code': '#FUXING01', 'season_id': 'lucky-lantern'}, headers=auth_headers(client))

    payload = client.get('/api/lineups?season=s17-star-god&page=1&page_size=10').get_json()

    assert payload['total'] == 1
    assert payload['items'][0]['name'] == 'S17 阵容'


def test_create_lineup_defaults_to_public_default_season_and_rejects_invalid_season(client):
    register_user(client)
    missing = client.post('/api/lineups', json={'name': '无赛季', 'code': '#NOSEASON'}, headers=auth_headers(client))
    invalid = client.post('/api/lineups', json={'name': '无效赛季', 'code': '#BADSEASON', 'season_id': 'unknown'}, headers=auth_headers(client))

    assert missing.status_code == 201
    assert missing.get_json()['season_id'] == 's17-star-god'
    assert invalid.status_code == 400


def test_lineup_seasons_endpoint_exposes_only_public_choices(client):
    payload = client.get('/api/lineup-seasons').get_json()

    assert payload['default_season_id'] == 's17-star-god'
    assert [season['id'] for season in payload['seasons']] == ['s17-star-god', 's16-legends', 'lucky-lantern', 's8-monsters-attack']
    assert payload['seasons'][0]['name'] == 'S17 · 星神'
    assert payload['seasons'][1]['name'] == 'S16 · 英雄联盟传奇'
    assert payload['seasons'][2]['name'] == '天选福星'
    assert all(season['status'] in {'active'} for season in payload['seasons'])


def test_lineup_seasons_ignore_live_comps_default_season(client):
    manifest_path = Path(client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH'])
    manifest_path.write_text(
        '{"default_season_id":"default","seasons":[{"id":"default","name":"S17 · 星神","status":"active","order":1,"description":"当前赛季","data_file":"live-comps.json"},{"id":"s16-legends","name":"S16 · 英雄联盟传奇","status":"active","order":2,"description":"经典赛季","data_file":"s16-legends.json"},{"id":"lucky-lantern","name":"天选福星","status":"active","order":3,"description":"返场赛季","data_file":"lucky-lantern.json"}]}',
        encoding='utf-8',
    )

    payload = client.get('/api/lineup-seasons').get_json()

    assert payload['default_season_id'] == 's17-star-god'
    assert [season['id'] for season in payload['seasons']] == ['s17-star-god', 's16-legends', 'lucky-lantern', 's8-monsters-attack']
    assert payload['seasons'][0]['name'] == 'S17 · 星神'


def test_anonymous_can_list_search_and_copy_but_cannot_create_update_delete(client):
    register_user(client)
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    assert client.get('/api/lineups?q=阵容').status_code == 200
    assert client.post(f"/api/lineups/{lineup['id']}/copy").status_code == 200
    assert client.post('/api/lineups', json={'name': 'x', 'code': 'y'}).status_code == 401
    assert client.put(f"/api/lineups/{lineup['id']}", json={'name': 'x', 'code': 'y'}).status_code == 401
    assert client.delete(f"/api/lineups/{lineup['id']}").status_code == 401


def test_logged_in_user_can_create_lineup_with_owner_id(client):
    register_user(client, nickname='小明')
    response = create_lineup(client)
    data = response.get_json()
    assert response.status_code == 201
    assert data['owner_nickname'] == '小明'
    assert data['can_edit'] is True
    assert data['can_hide'] is True


def test_create_lineup_extracts_hash_prefixed_code_from_messy_input(client):
    register_user(client)
    response = create_lineup(client, code='青青#【阵容码】#斗虫伊泽-金铲铲葡葡萄#MTEwMTIzABC987')
    assert response.status_code == 201
    assert response.get_json()['code'] == '#MTEwMTIzABC987'


def test_create_lineup_rejects_unparseable_code(client):
    register_user(client)
    response = create_lineup(client, code='这不是合法阵容码')
    assert response.status_code == 400
    assert '阵容码无法解析' in response.get_json()['error']


def test_create_lineup_supports_hidden_status(client):
    register_user(client)
    response = create_lineup(client, name='隐藏新阵容', code='#HIDDENNEW1', status='hidden')
    assert response.status_code == 201
    data = response.get_json()
    assert data['status'] == 'hidden'
    mine = client.get('/api/lineups?view=mine&page=1&page_size=20', headers=auth_headers(client)).get_json()
    assert mine['items'][0]['status'] == 'hidden'


def test_update_lineup_normalizes_code_before_save(client):
    register_user(client)
    lineup = create_lineup(client, code='#ABC123').get_json()
    response = client.put(
        f"/api/lineups/{lineup['id']}",
        json={'name': lineup['name'], 'code': '分享文本#阵容#XYZ987', 'version': lineup['version']},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    assert response.get_json()['code'] == '#XYZ987'


def test_user_cannot_edit_or_delete_other_users_lineup(client):
    register_user(client, username='a', email='a@example.com')
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    register_user(client, username='b', email='b@example.com')
    assert client.put(f"/api/lineups/{lineup['id']}", json={'name': '改', 'code': '#NEW123'}, headers=auth_headers(client)).status_code == 403
    assert client.delete(f"/api/lineups/{lineup['id']}", headers=auth_headers(client)).status_code == 403


def test_admin_can_edit_delete_hide_any_lineup(client):
    register_user(client, username='a', email='a@example.com')
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    assert client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'}).status_code == 200
    headers = auth_headers(client)
    assert client.put(f"/api/lineups/{lineup['id']}", json={'name': '管理员改', 'code': '#ADMIN123'}, headers=headers).status_code == 200
    assert client.post(f"/api/lineups/{lineup['id']}/hide", headers=headers).status_code == 200


def test_hidden_lineups_are_not_visible_to_public(client):
    register_user(client, username='a', email='a@example.com')
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    client.post(f"/api/lineups/{lineup['id']}/hide", headers=auth_headers(client))
    client.post('/api/logout')
    assert client.get('/api/lineups').get_json() == []


def test_owner_can_hide_own_lineup(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='我的可隐藏阵容', code='#HIDEOWN1').get_json()
    headers = auth_headers(client)

    response = client.post(f"/api/lineups/{lineup['id']}/hide", headers=headers)

    assert response.status_code == 200
    mine = client.get('/api/lineups?view=mine&page=1&page_size=20', headers=headers).get_json()
    assert mine['items'][0]['status'] == 'hidden'


def test_hidden_lineup_only_remains_visible_to_owner_and_admin(client):
    from test_admin import login_admin

    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='被隐藏阵容', code='#HIDDENONLY1').get_json()
    owner_headers = auth_headers(client)
    assert client.post(f"/api/lineups/{lineup['id']}/favorite", headers=owner_headers).status_code == 200
    client.post('/api/logout')

    register_user(client, username='viewer', email='viewer@example.com')
    viewer_headers = auth_headers(client)
    assert client.post(f"/api/lineups/{lineup['id']}/favorite", headers=viewer_headers).status_code == 200
    assert client.post(f"/api/lineups/{lineup['id']}/view", headers=viewer_headers).status_code == 201
    assert client.post(f"/api/lineups/{lineup['id']}/copy", headers=viewer_headers).status_code == 200
    client.post('/api/logout')

    client.post('/api/login', json={'account': 'owner', 'password': 'abc123'})
    owner_headers = auth_headers(client)
    assert client.post(f"/api/lineups/{lineup['id']}/hide", headers=owner_headers).status_code == 200
    owner_favorites = client.get('/api/lineups?view=favorites&page=1&page_size=10', headers=owner_headers).get_json()
    assert owner_favorites['items'][0]['id'] == lineup['id']
    client.post('/api/logout')

    client.post('/api/login', json={'account': 'viewer', 'password': 'abc123'})
    viewer_headers = auth_headers(client)
    public_payload = client.get('/api/lineups?page=1&page_size=10', headers=viewer_headers).get_json()
    favorites_payload = client.get('/api/lineups?view=favorites&page=1&page_size=10', headers=viewer_headers).get_json()
    recent_views = client.get('/api/me/recent-views', headers=viewer_headers).get_json()
    recent_copies = client.get('/api/me/recent-copies', headers=viewer_headers).get_json()

    assert all(item['id'] != lineup['id'] for item in public_payload['items'])
    assert favorites_payload['items'] == []
    assert recent_views == []
    assert recent_copies == []
    assert client.get(f"/api/lineups/{lineup['id']}", headers=viewer_headers).status_code == 404
    assert client.post(f"/api/lineups/{lineup['id']}/view", headers=viewer_headers).status_code == 404
    assert client.post(f"/api/lineups/{lineup['id']}/copy", headers=viewer_headers).status_code == 404
    assert client.post(f"/api/lineups/{lineup['id']}/like", headers=viewer_headers).status_code == 404
    assert client.post(f"/api/lineups/{lineup['id']}/favorite", headers=viewer_headers).status_code == 404
    assert client.post(
        f"/api/lineups/{lineup['id']}/report",
        json={'reason': '隐藏后不该再能举报'},
        headers=viewer_headers,
    ).status_code == 404
    client.post('/api/logout')

    admin_headers = login_admin(client)
    admin_payload = client.get('/api/lineups?page=1&page_size=10', headers=admin_headers).get_json()
    assert any(item['id'] == lineup['id'] for item in admin_payload['items'])


def test_lineups_endpoint_supports_item_fetch_for_editor(client):
    register_user(client, username='a', email='a@example.com', nickname='作者')
    lineup = create_lineup(client, name='可编辑阵容', code='#EDITCODE').get_json()
    data = client.get(f"/api/lineups/{lineup['id']}").get_json()
    assert data['id'] == lineup['id']
    assert data['name'] == '可编辑阵容'
    assert data['owner_nickname'] == '作者'


def test_lineups_endpoint_supports_pagination(client):
    register_user(client, username='a', email='a@example.com')
    for index in range(15):
        create_lineup(client, name=f'阵容{index:02d}', code=f'#CODE{index:02d}')
    page_one = client.get('/api/lineups?page=1&page_size=10').get_json()
    page_two = client.get('/api/lineups?page=2&page_size=10').get_json()
    assert page_one['total'] == 15
    assert page_one['page'] == 1
    assert page_one['page_size'] == 10
    assert page_one['total_pages'] == 2
    assert len(page_one['items']) == 10
    assert len(page_two['items']) == 5
    assert page_one['items'][0]['name'] == '阵容14'


def test_lineups_pagination_applies_after_search_filter(client):
    register_user(client, username='a', email='a@example.com')
    for index in range(12):
        create_lineup(client, name=f'法师阵容{index:02d}', code=f'#MAGE{index:02d}')
    create_lineup(client, name='斗士阵容', code='#FIGHT123')
    page = client.get('/api/lineups?q=法师&page=1&page_size=10').get_json()
    assert page['total'] == 12
    assert page['total_pages'] == 2
    assert len(page['items']) == 10


def test_paginated_logged_in_list_avoids_n_plus_one_queries(client, monkeypatch):
    import db

    register_user(client, username='a', email='a@example.com')
    lineup_ids = []
    for index in range(15):
        lineup_ids.append(create_lineup(client, name=f'阵容{index:02d}', code=f'#CODE{index:02d}').get_json()['id'])

    headers = auth_headers(client)
    for lineup_id in lineup_ids[:3]:
        assert client.post(f'/api/lineups/{lineup_id}/like', headers=headers).status_code == 201
        assert client.post(f'/api/lineups/{lineup_id}/favorite', headers=headers).status_code == 200

    statements = []
    original_connect = db.sqlite3.connect

    def traced_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(db.sqlite3, 'connect', traced_connect)

    response = client.get('/api/lineups?page=1&page_size=10')
    assert response.status_code == 200
    data = response.get_json()
    assert data['total'] == 15
    assert len(data['items']) == 10

    select_statements = [sql for sql in statements if sql.lstrip().upper().startswith('SELECT')]
    assert len(select_statements) <= 6


