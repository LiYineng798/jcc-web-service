from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_recent_history_tables_exist(app):
    with app.app_context():
        from db import table_names
        names = table_names()
        assert 'recent_lineup_views' in names
        assert 'recent_lineup_copies' in names


def test_record_recent_view_upserts_latest_timestamp(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='最近浏览阵容', code='#VIEW001').get_json()
    user_id = client.get('/api/me').get_json()['user']['id']

    with client.application.app_context():
        from history import list_recent_views, record_recent_view

        record_recent_view(user_id, lineup['id'], created_at='2026-05-12 10:00:00')
        record_recent_view(user_id, lineup['id'], created_at='2026-05-12 11:00:00')

        rows = list_recent_views(user_id, limit=20)
        assert len(rows) == 1
        assert rows[0]['id'] == lineup['id']
        assert rows[0]['history_at'] == '2026-05-12 11:00:00'


def test_logged_in_view_endpoint_records_recent_view(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='浏览记录阵容', code='#DETAIL002').get_json()
    headers = auth_headers(client)

    response = client.post(f"/api/lineups/{lineup['id']}/view", headers=headers)

    assert response.status_code == 201
    history_payload = client.get('/api/me/recent-views', headers=headers).get_json()
    assert history_payload[0]['id'] == lineup['id']


def test_history_sync_merges_guest_views_and_copies_into_account(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup_a = create_lineup(client, name='浏览阵容', code='#SYNC001').get_json()
    lineup_b = create_lineup(client, name='复制阵容', code='#SYNC002').get_json()
    headers = auth_headers(client)

    payload = {
        'views': [{'lineup_id': lineup_a['id'], 'at': '2026-05-12 09:00:00'}],
        'copies': [{'lineup_id': lineup_b['id'], 'at': '2026-05-12 09:10:00'}],
    }
    response = client.post('/api/me/history/sync', json=payload, headers=headers)

    assert response.status_code == 200
    assert client.get('/api/me/recent-views', headers=headers).get_json()[0]['id'] == lineup_a['id']
    assert client.get('/api/me/recent-copies', headers=headers).get_json()[0]['id'] == lineup_b['id']
