from test_auth import get_captcha, register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_mutating_requests_require_csrf(client):
    register_user(client)
    response = client.post('/api/lineups', json={'name': '无CSRF', 'code': 'CODE'})
    assert response.status_code == 403


def test_session_cookie_flags_are_securely_configured(client):
    register_user(client)
    cookie = client.get_cookie('session')
    assert cookie is not None
    assert cookie.http_only is True
    assert cookie.same_site == 'Lax'


def test_login_rate_limit_blocks_repeated_failures(client):
    for _ in range(10):
        client.post('/api/login', json={'account': 'missing', 'password': 'bad'})
    response = client.post('/api/login', json={'account': 'missing', 'password': 'bad'})
    assert response.status_code == 429


def test_register_rate_limit_blocks_repeated_same_ip(client):
    for index in range(5):
        register_user(client, username=f'u{index}', email=f'u{index}@example.com')
        client.post('/api/logout')
    challenge, answer = get_captcha(client)
    response = client.post('/api/register', json={
        'username': 'u6', 'email': 'u6@example.com', 'password': 'abc123',
        'captcha_token': challenge['captcha_token'], 'captcha_answer': answer,
    })
    assert response.status_code == 429
