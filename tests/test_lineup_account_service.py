from lineup_account_service import (
    build_author_profile_payload,
    build_my_dashboard_payload,
    list_my_reports_payload,
)
from scoring import score_map
from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_build_author_profile_payload_returns_public_lineups_only(client):
    register_user(client, username='author3', email='author3@example.com', nickname='作者三号')
    visible = create_lineup(client, name='公开阵容', code='#AUTHOR004').get_json()
    hidden = create_lineup(client, name='隐藏阵容', code='#AUTHOR005', status='hidden').get_json()

    with client.application.app_context():
        payload, error, status_code = build_author_profile_payload(
            username='author3',
            viewer=None,
            scores=score_map(),
        )

    assert error is None
    assert status_code == 200
    lineup_ids = [item['id'] for item in payload['lineups']]
    assert visible['id'] in lineup_ids
    assert hidden['id'] not in lineup_ids
    assert payload['summary']['published_lineups'] == 1


def test_build_my_dashboard_payload_returns_creator_summary(client):
    register_user(client, username='creator', email='creator@example.com')
    lineup = create_lineup(client, name='作者阵容', code='#DASH001').get_json()
    headers = auth_headers(client)

    client.post(f"/api/lineups/{lineup['id']}/favorite", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/like", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/report", json={'reason': '测试举报'}, headers=headers)
    user = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload = build_my_dashboard_payload(user['id'])

    assert payload['published_lineups'] == 1
    assert 'received_likes' in payload
    assert 'received_favorites' in payload
    assert 'received_copies' in payload
    assert 'submitted_reports' in payload


def test_list_my_reports_payload_returns_report_status_rows(client):
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
    user = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload = list_my_reports_payload(user['id'])

    assert payload[0]['status'] == 'resolved'
    assert payload[0]['lineup_status'] == 'hidden'
    assert payload[0]['handled_at'] is not None
