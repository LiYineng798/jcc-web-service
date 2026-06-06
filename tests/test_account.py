from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_account_dashboard_returns_creator_summary(client):
    register_user(client, username='creator', email='creator@example.com')
    lineup = create_lineup(client, name='作者阵容', code='#DASH001').get_json()
    headers = auth_headers(client)

    client.post(f"/api/lineups/{lineup['id']}/favorite", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/like", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/report", json={'reason': '测试举报'}, headers=headers)

    payload = client.get('/api/me/dashboard', headers=headers).get_json()

    assert payload['published_lineups'] == 1
    assert 'received_likes' in payload
    assert 'received_favorites' in payload
    assert 'received_copies' in payload
    assert 'submitted_reports' in payload


def test_my_reports_api_returns_status_after_admin_resolution(client):
    from test_admin import login_admin

    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='被举报阵容', code='#REPORT001').get_json()
    client.post('/api/logout')

    register_user(client, username='reporter', email='reporter@example.com')
    headers = auth_headers(client)
    report = client.post(
        f"/api/lineups/{lineup['id']}/report",
        json={'reason': '需要处理'},
        headers=headers,
    ).get_json()

    client.post('/api/logout')
    admin_headers = login_admin(client)
    client.post(
        f"/api/admin/reports/{report['id']}/resolve",
        json={'status': 'resolved', 'hide_lineup': True},
        headers=admin_headers,
    )

    client.post('/api/logout')
    client.post('/api/login', json={'account': 'reporter', 'password': 'abc123'})
    my_reports = client.get('/api/me/reports', headers=auth_headers(client)).get_json()

    assert my_reports[0]['status'] == 'resolved'
    assert my_reports[0]['lineup_status'] == 'hidden'
    assert my_reports[0]['handled_at'] is not None


def test_recent_copy_api_returns_latest_first(client):
    register_user(client, username='creator', email='creator@example.com')
    first = create_lineup(client, name='旧复制', code='#COPY001').get_json()
    second = create_lineup(client, name='新复制', code='#COPY002').get_json()
    headers = auth_headers(client)

    client.post('/api/me/history/sync', json={
        'views': [],
        'copies': [
            {'lineup_id': first['id'], 'at': '2026-05-12 09:00:00'},
            {'lineup_id': second['id'], 'at': '2026-05-12 10:00:00'},
        ],
    }, headers=headers)

    payload = client.get('/api/me/recent-copies', headers=headers).get_json()
    assert payload[0]['id'] == second['id']
    assert payload[1]['id'] == first['id']


def test_mine_view_includes_hidden_lineups_for_owner(client):
    from test_admin import login_admin

    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='会被隐藏的阵容', code='#HIDDEN001').get_json()
    client.post('/api/logout')

    admin_headers = login_admin(client)
    client.put(f"/api/admin/lineups/{lineup['id']}", json={'status': 'hidden'}, headers=admin_headers)
    client.post('/api/logout')

    client.post('/api/login', json={'account': 'owner', 'password': 'abc123'})
    mine = client.get('/api/lineups?view=mine&page=1&page_size=20', headers=auth_headers(client)).get_json()

    assert mine['total'] == 1
    assert mine['items'][0]['status'] == 'hidden'
