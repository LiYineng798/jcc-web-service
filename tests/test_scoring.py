from datetime import datetime, timedelta

from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_score_weights_like_as_five_and_copy_as_one(client):
    register_user(client)
    lineup = create_lineup(client).get_json()
    headers = auth_headers(client)
    client.post(f"/api/lineups/{lineup['id']}/like", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers)
    client.post('/api/logout')
    client.post(f"/api/lineups/{lineup['id']}/copy", headers={'X-Forwarded-For': '9.9.9.9'})
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    admin_lineup = client.get('/api/admin/lineups', headers=auth_headers(client)).get_json()['items'][0]
    assert admin_lineup['score'] == 7


def test_admin_adjustments_are_included(client):
    register_user(client)
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    response = client.post(f"/api/admin/lineups/{lineup['id']}/adjust-score", json={'admin_like_adjustment': 2, 'admin_copy_adjustment': 3}, headers=auth_headers(client))
    assert response.get_json()['score'] == 13


def test_public_api_hides_score_but_admin_api_returns_score(client):
    register_user(client)
    create_lineup(client)
    public = client.get('/api/lineups').get_json()[0]
    assert 'score' not in public
    client.post('/api/logout')
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    admin = client.get('/api/admin/lineups', headers=auth_headers(client)).get_json()['items'][0]
    assert 'score' in admin


def test_percentage_levels_assign_ss_s_a_b(client):
    register_user(client)
    ids = [create_lineup(client, name=f'L{i}', code=f'#C{i}').get_json()['id'] for i in range(10)]
    client.post('/api/logout')
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    headers = auth_headers(client)
    for index, lineup_id in enumerate(ids):
        client.post(f'/api/admin/lineups/{lineup_id}/adjust-score', json={'admin_copy_adjustment': 100 - index * 10}, headers=headers)
    levels = [item['rank_level'] for item in client.get('/api/admin/lineups', headers=headers).get_json()['items']]
    assert 'SS' in levels
    assert 'S' in levels
    assert 'A' in levels
    assert 'B' in levels


def test_score_uses_recent_seven_days_only(client):
    register_user(client)
    lineup = create_lineup(client).get_json()
    with client.application.app_context():
        from db import get_db
        old = (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S')
        get_db().execute("UPDATE copy_events SET created_at = ?", (old,))
        get_db().commit()
    client.post('/api/logout')
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    admin = client.get('/api/admin/lineups', headers=auth_headers(client)).get_json()['items'][0]
    assert admin['score'] == 0


def test_score_map_cache_refreshes_after_copy_event(client):
    register_user(client)
    lineup = create_lineup(client).get_json()
    with client.application.app_context():
        from scoring import score_map

        assert score_map()[lineup['id']]['score'] == 0

    client.post('/api/logout')
    response = client.post(f"/api/lineups/{lineup['id']}/copy", headers={'X-Forwarded-For': '8.8.8.8'})
    assert response.status_code == 200
    assert response.get_json()['counted'] is True

    with client.application.app_context():
        from scoring import score_map

        assert score_map()[lineup['id']]['score'] == 1
