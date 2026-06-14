from lineup_bridge_service import (
    ingest_growth_event_payload,
    list_recent_copies_payload,
    list_recent_views_payload,
    record_lineup_view_payload,
    sync_recent_history_payload,
)
from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_record_lineup_view_payload_records_visible_lineup(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='浏览记录阵容', code='#DETAIL002').get_json()
    user = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload, error, status_code = record_lineup_view_payload(user, lineup['id'])
        history = list_recent_views_payload(user, limit=20)

    assert error is None
    assert status_code == 201
    assert payload == {'ok': True}
    assert history[0]['id'] == lineup['id']


def test_sync_recent_history_payload_merges_views_and_copies(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup_a = create_lineup(client, name='浏览阵容', code='#SYNC001').get_json()
    lineup_b = create_lineup(client, name='复制阵容', code='#SYNC002').get_json()
    user = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload, error, status_code = sync_recent_history_payload(
            user,
            {
                'views': [{'lineup_id': lineup_a['id'], 'at': '2026-05-12 09:00:00'}],
                'copies': [{'lineup_id': lineup_b['id'], 'at': '2026-05-12 09:10:00'}],
            },
        )
        views = list_recent_views_payload(user, limit=20)
        copies = list_recent_copies_payload(user, limit=20)

    assert error is None
    assert status_code == 200
    assert payload == {'ok': True}
    assert views[0]['id'] == lineup_a['id']
    assert copies[0]['id'] == lineup_b['id']


def test_ingest_growth_event_payload_accepts_guest_event(client):
    with client.application.test_request_context('/api/growth-events'):
        payload, cookie_meta, error, status_code = ingest_growth_event_payload(
            data={'event_name': 'guest_click_like', 'page_key': 'home', 'ref_lineup_id': None, 'payload': {'source': 'lineup-card'}},
            user=None,
            ip_address='1.2.3.4',
        )

    assert error is None
    assert status_code == 201
    assert payload == {'ok': True}
    assert 'visitor_token' in cookie_meta
