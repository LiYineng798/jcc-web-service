from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_growth_events_table_exists(app):
    with app.app_context():
        from db import table_names

        assert 'growth_events' in table_names()


def test_record_growth_event_persists_whitelisted_event(app):
    with app.app_context():
        from analytics import record_growth_event
        from db import get_db

        record_growth_event(
            event_name='click_login_entry',
            user_id=None,
            visitor_token='guest-token',
            ip_address='1.2.3.4',
            ref_lineup_id=None,
            page_key='home',
            payload={'source': 'header'},
            created_at='2026-05-12 09:00:00',
        )

        row = get_db().execute('SELECT * FROM growth_events').fetchone()
        assert row['event_name'] == 'click_login_entry'
        assert row['visitor_token'] == 'guest-token'
        assert row['page_key'] == 'home'


def test_register_and_login_success_write_growth_events(client):
    response = register_user(client, username='growth', email='growth@example.com')
    assert response.status_code == 201
    client.post('/api/logout')
    assert client.post('/api/login', json={'account': 'growth', 'password': 'abc123'}).status_code == 200

    with client.application.app_context():
        from db import get_db

        names = [row['event_name'] for row in get_db().execute('SELECT event_name FROM growth_events ORDER BY id').fetchall()]
        assert 'register_success' in names
        assert 'login_success' in names


def test_growth_event_ingest_endpoint_accepts_whitelisted_guest_event(client):
    me = client.get('/api/me').get_json()
    response = client.post(
        '/api/growth-events',
        json={'event_name': 'guest_click_like', 'page_key': 'home', 'ref_lineup_id': None, 'payload': {'source': 'lineup-card'}},
        headers={'X-CSRF-Token': me['csrf_token']},
    )
    assert response.status_code == 201


def test_logged_in_core_actions_write_growth_events(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='核心动作阵容', code='#GROWTH001').get_json()
    headers = auth_headers(client)

    assert client.post(f"/api/lineups/{lineup['id']}/like", headers=headers).status_code == 201
    assert client.post(f"/api/lineups/{lineup['id']}/favorite", headers=headers).status_code == 200
    assert client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers).status_code == 200

    with client.application.app_context():
        from db import get_db

        names = [row['event_name'] for row in get_db().execute('SELECT event_name FROM growth_events ORDER BY id').fetchall()]
        assert 'post_login_create_lineup' in names
        assert 'post_login_like' in names
        assert 'post_login_favorite' in names
        assert 'post_login_copy' in names


def test_growth_summary_uses_calendar_date_and_excludes_admin(app):
    with app.app_context():
        from analytics import growth_summary, record_growth_event
        from db import get_db, now_text

        db = get_db()
        now = now_text()
        user_id = db.execute(
            '''INSERT INTO users (username, email, nickname, password_hash, role, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'user', 'active', ?, ?)''',
            ('growth-user', 'growth-user@example.com', '增长用户', 'hash', now, now),
        ).lastrowid
        db.execute(
            '''INSERT INTO visit_events (visit_date, visitor_key, visitor_kind, user_id, visitor_token, ip_address, page_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            ('2026-05-12', 'guest:guest-a', 'guest_token', None, 'guest-a', '1.1.1.1', 'home', '2026-05-12 08:00:00'),
        )
        db.execute(
            '''INSERT INTO visit_events (visit_date, visitor_key, visitor_kind, user_id, visitor_token, ip_address, page_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            ('2026-05-12', f'user:{user_id}', 'user', user_id, 'guest-user', '2.2.2.2', 'home', '2026-05-12 08:30:00'),
        )
        db.execute(
            '''INSERT INTO visit_events (visit_date, visitor_key, visitor_kind, user_id, visitor_token, ip_address, page_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            ('2026-05-12', 'user:1', 'user', 1, 'guest-admin', '3.3.3.3', 'home', '2026-05-12 09:00:00'),
        )
        db.commit()

        record_growth_event('click_login_entry', visitor_token='guest-a', ip_address='1.1.1.1', page_key='home', payload={'source': 'header'}, created_at='2026-05-12 08:01:00')
        record_growth_event('open_auth_page', visitor_token='guest-a', ip_address='1.1.1.1', page_key='auth', payload={'source': 'redirect'}, created_at='2026-05-12 08:02:00')
        record_growth_event('guest_click_like', visitor_token='guest-a', ip_address='1.1.1.1', page_key='home', payload={'source': 'lineup-card'}, created_at='2026-05-12 08:03:00')
        record_growth_event('guest_click_favorite', visitor_token='guest-a', ip_address='1.1.1.1', page_key='home', payload={'source': 'lineup-card'}, created_at='2026-05-12 08:04:00')
        record_growth_event('register_success', user_id=user_id, visitor_token='guest-user', ip_address='2.2.2.2', page_key='auth', payload={'method': 'register'}, created_at='2026-05-12 08:05:00')
        record_growth_event('post_login_like', user_id=user_id, visitor_token='guest-user', ip_address='2.2.2.2', page_key='home', payload={}, created_at='2026-05-12 08:06:00')
        record_growth_event('post_login_favorite', user_id=user_id, visitor_token='guest-user', ip_address='2.2.2.2', page_key='home', payload={}, created_at='2026-05-12 08:07:00')
        record_growth_event('post_login_create_lineup', user_id=user_id, visitor_token='guest-user', ip_address='2.2.2.2', page_key='home', payload={}, created_at='2026-05-12 08:08:00')
        record_growth_event('login_success', user_id=1, visitor_token='guest-admin', ip_address='3.3.3.3', page_key='auth', payload={'method': 'login'}, created_at='2026-05-12 09:10:00')

        summary = growth_summary(target_date='2026-05-12')

        assert summary['date'] == '2026-05-12'
        assert summary['home_uv'] == 2
        assert summary['login_entry_visitors'] == 1
        assert summary['auth_page_visitors'] == 1
        assert summary['successful_registrations'] == 1
        assert summary['successful_logins'] == 0
        assert summary['guest_like_visitors'] == 1
        assert summary['guest_favorite_visitors'] == 1
        assert summary['post_login_like_users'] == 1
        assert summary['post_login_favorite_users'] == 1
        assert summary['post_login_create_lineup_users'] == 1


def test_admin_actions_do_not_write_growth_events(client):
    assert client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'}).status_code == 200
    headers = auth_headers(client)

    growth_response = client.post(
        '/api/growth-events',
        json={'event_name': 'click_login_entry', 'page_key': 'home', 'payload': {'source': 'header'}},
        headers=headers,
    )
    assert growth_response.status_code == 201

    lineup_response = client.post(
        '/api/lineups',
        json={'name': '管理员阵容', 'code': '#ADMIN001'},
        headers=headers,
    )
    assert lineup_response.status_code == 201

    with client.application.app_context():
        from db import get_db

        rows = get_db().execute('SELECT event_name FROM growth_events WHERE user_id = 1 ORDER BY id').fetchall()
        assert rows == []


def test_admin_login_does_not_leave_guest_funnel_traces_for_same_session(client):
    client.get('/')
    me = client.get('/api/me').get_json()
    response = client.post(
        '/api/growth-events',
        json={'event_name': 'click_login_entry', 'page_key': 'home', 'payload': {'source': 'header'}},
        headers={'X-CSRF-Token': me['csrf_token']},
    )
    assert response.status_code == 201

    assert client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'}).status_code == 200

    with client.application.app_context():
        from datetime import datetime

        from analytics import growth_summary

        today = datetime.now().strftime('%Y-%m-%d')
        summary = growth_summary(target_date=today)
        assert summary['home_uv'] == 0
        assert summary['login_entry_visitors'] == 0
