from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from db import get_db, now_text
from test_auth import register_user
from auth_activity import authenticated_active_users
from admin_dashboard_service import build_admin_stats_payload, build_admin_overview_payload
from werkzeug.security import generate_password_hash


def test_registration_and_login_issue_persistent_cookie(client):
    registered = register_user(client)
    assert registered.status_code == 201
    cookie = client.get_cookie('session')
    assert cookie.expires is not None and cookie.http_only and cookie.same_site == 'Lax'
    client.post('/api/logout')
    assert client.get_cookie('session') is None
    login = client.post('/api/login', json={'account': 'alice', 'password': 'abc123'})
    assert login.status_code == 200
    assert client.get_cookie('session').expires is not None
    assert client.application.config['PERMANENT_SESSION_LIFETIME'] == timedelta(days=30)
    # Restore only the cookie in a new browser client (no in-memory session).
    returning = client.application.test_client()
    returning.set_cookie('session', client.get_cookie('session').value)
    assert returning.get('/api/me').get_json()['user']['username'] == 'alice'
    returning.post('/api/logout')
    assert returning.get('/api/me').get_json()['user'] is None


def test_expired_cookie_cannot_authenticate(client):
    import time
    register_user(client)
    with patch('time.time', return_value=time.time() + 31 * 86400):
        assert client.get('/api/me').get_json()['user'] is None


def test_password_change_revokes_all_existing_sessions(client):
    register_user(client)
    other = client.application.test_client()
    other.set_cookie('session', client.get_cookie('session').value)
    with client.application.app_context():
        db = get_db()
        db.execute('UPDATE users SET password_hash = ? WHERE username = ?',
                   (generate_password_hash('new12345'), 'alice'))
        db.commit()
    assert client.get('/api/me').get_json()['user'] is None
    assert other.get('/api/me').get_json()['user'] is None
    assert client.post('/api/login', json={'account': 'alice', 'password': 'new12345'}).status_code == 200


def test_disabled_user_is_not_returned_as_logged_in(client):
    register_user(client)
    with client.application.app_context():
        get_db().execute("UPDATE users SET status = 'disabled' WHERE username = 'alice'")
        get_db().commit()
    assert client.get('/api/me').get_json()['user'] is None
    assert client.get('/api/me/dashboard').status_code == 401


def test_returning_users_count_once_without_fabricated_login_events(client):
    register_user(client)
    client.post('/api/logout')
    client.post('/api/login', json={'account': 'alice', 'password': 'abc123'})
    with client.application.app_context():
        db = get_db()
        db.execute("UPDATE login_events SET created_at = '2020-01-01 12:00:00'")
        db.commit()
    returning = client.application.test_client()
    returning.set_cookie('session', client.get_cookie('session').value)
    returning.get('/')
    returning.get('/patch-notes')
    client.get('/')
    with client.application.app_context():
        db = get_db()
        assert authenticated_active_users(db, now_text()[:10]) == 1
        assert db.execute('SELECT COUNT(*) AS c FROM login_events').fetchone()['c'] == 1
        for stats in (build_admin_stats_payload(db), build_admin_overview_payload(db)['stats']):
            assert stats['today_authenticated_users'] == 1
            assert stats['today_logins'] == 0
    # A same-day password login is unioned with visits, not added again.
    returning.post('/api/login', json={'account': 'alice', 'password': 'abc123'})
    admin = client.application.test_client()
    admin.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    admin.get('/')
    with client.application.app_context():
        assert authenticated_active_users(get_db(), now_text()[:10]) == 1


def test_session_renews_without_changing_csrf(client):
    import time
    register_user(client)
    before = client.get_cookie('session').expires
    csrf = client.get('/api/me').get_json()['csrf_token']
    with patch('time.time', return_value=time.time() + 2 * 86400), patch('flask.sessions.datetime') as clock:
        clock.now.return_value = datetime.now(timezone.utc) + timedelta(days=2)
        assert client.get('/api/me').get_json()['csrf_token'] == csrf
    assert client.get_cookie('session').expires > before
