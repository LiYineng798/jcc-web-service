from test_admin import login_admin


def test_admin_controls_library_order_and_direct_access(client):
    headers = login_admin(client)
    listing = client.get('/api/admin/season-display/library', headers=headers).get_json()['items']
    target = listing[-1]

    response = client.put(
        f"/api/admin/season-display/library/{target['season_id']}",
        json={'order': 1, 'status': 'hidden'},
        headers=headers,
    )
    assert response.status_code == 200

    public = client.get('/api/season-catalog?surface=library').get_json()['seasons']
    assert all(item['season_id'] != target['season_id'] for item in public)
    assert client.get(f"/tools/seasons/{target['season_id']}").status_code == 404


def test_simulator_visibility_is_independent_and_admin_only(client):
    assert client.get('/api/admin/season-display/simulator').status_code == 401
    headers = login_admin(client)
    items = client.get('/api/admin/season-display/simulator', headers=headers).get_json()['items']
    target = items[0]
    assert client.put(
        f"/api/admin/season-display/simulator/{target['season_id']}",
        json={'status': 'disabled'},
        headers=headers,
    ).status_code == 200
    public = client.get('/api/season-catalog?surface=simulator').get_json()['seasons']
    assert all(item['season_id'] != target['season_id'] for item in public)


def test_admin_sets_simulator_default_and_hidden_default_falls_back(client):
    headers = login_admin(client)
    payload = client.get('/api/admin/season-display/simulator', headers=headers).get_json()
    first, target = payload['items'][:2]

    response = client.put(
        f"/api/admin/season-display/simulator/{target['season_id']}",
        json={'is_default': True},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()['default_season_id'] == target['season_id']
    assert client.get('/api/season-catalog?surface=simulator').get_json()['default_season_id'] == target['season_id']

    response = client.put(
        f"/api/admin/season-display/simulator/{target['season_id']}",
        json={'status': 'hidden'},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()['default_season_id'] == first['season_id']


def test_simulator_default_must_be_public(client):
    headers = login_admin(client)
    target = client.get('/api/admin/season-display/simulator', headers=headers).get_json()['items'][0]
    assert client.put(
        f"/api/admin/season-display/simulator/{target['season_id']}",
        json={'status': 'disabled'},
        headers=headers,
    ).status_code == 200
    response = client.put(
        f"/api/admin/season-display/simulator/{target['season_id']}",
        json={'is_default': True},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.get_json()['error'] == '默认赛季必须处于展示或归档状态'


def test_custom_404_page_is_rendered(client):
    response = client.get('/does-not-exist')
    assert response.status_code == 404
    assert '页面不存在' in response.get_data(as_text=True)
