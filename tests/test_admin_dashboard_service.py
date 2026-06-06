from admin_dashboard_service import (
    build_admin_growth_payload,
    build_admin_overview_payload,
    build_admin_stats_payload,
)
from db import get_db
from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_build_admin_stats_payload_returns_expected_keys(client):
    register_user(client, username='alice', email='alice@example.com')

    with client.application.app_context():
        payload = build_admin_stats_payload(get_db())

    assert payload['total_users'] == 1
    assert payload['today_users'] == 1
    assert 'today_logins' in payload
    assert 'today_uv' in payload
    assert 'yesterday_uv' in payload
    assert 'last_7_days_uv' in payload
    assert 'hourly_registrations' in payload


def test_build_admin_overview_payload_returns_expected_keys(client):
    register_user(client, username='alice', email='alice@example.com')

    with client.application.app_context():
        payload = build_admin_overview_payload(get_db())

    assert 'stats' in payload
    assert 'traffic_7d' in payload
    assert 'todos' in payload
    assert payload['stats']['pending_reports_count'] >= 0
    assert payload['stats']['today_uv'] >= 0
    assert len(payload['traffic_7d']) == 7


def test_admin_overview_counts_today_total_copy_count(client):
    register_user(client, username='alice', email='alice@example.com')
    lineup = create_lineup(client, name='统计阵容', code='#COPYTOTAL').get_json()
    headers = auth_headers(client)
    client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers)
    with client.application.app_context():
        db = get_db()
        now = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            '''
            INSERT INTO live_comp_global_daily_stats (copy_date, copy_count, created_at, updated_at)
            VALUES (?, 3, ?, ?)
            ''',
            (now[:10], now, now),
        )
        db.commit()
        payload = build_admin_overview_payload(db)

    assert payload['stats']['today_lineup_copy_count'] == 1
    assert payload['stats']['today_live_comp_copy_count'] == 3
    assert payload['stats']['today_total_copy_count'] == 4


def test_build_admin_growth_payload_returns_funnel_fields(client):
    client.get('/')
    me = client.get('/api/me').get_json()
    client.post(
        '/api/growth-events',
        json={'event_name': 'click_login_entry', 'page_key': 'home', 'payload': {'source': 'header'}},
        headers={'X-CSRF-Token': me['csrf_token']},
    )
    register_user(client, username='growth', email='growth@example.com')

    with client.application.app_context():
        payload = build_admin_growth_payload(None)

    assert 'date' in payload
    assert 'home_uv' in payload
    assert 'login_entry_visitors' in payload
    assert 'auth_page_visitors' in payload
    assert 'successful_registrations' in payload
    assert 'successful_logins' in payload
    assert 'guest_like_visitors' in payload
    assert 'guest_favorite_visitors' in payload
    assert 'post_login_like_users' in payload
    assert 'post_login_favorite_users' in payload
    assert 'post_login_create_lineup_users' in payload
    assert 'conversion_rates' in payload
