from test_auth import register_user
from test_lineup_permissions import auth_headers


def test_password_reset_request_and_confirm(monkeypatch, client):
    register_user(client, username='resetuser', email='reset@example.com', password='abc123')
    sent = {}

    def fake_send(email, code, request_id):
        sent.update(email=email, code=code, request_id=request_id)
        return ({'id': 'resend-test-id'}, None)

    monkeypatch.setattr('password_reset_service._send_email', fake_send)
    response = client.post('/api/password-reset/request', json={'email': 'reset@example.com'})
    assert response.status_code == 200
    assert '验证码将在几分钟内发送' in response.get_json()['message']
    assert sent['email'] == 'reset@example.com'

    wrong = client.post('/api/password-reset/confirm', json={'email': sent['email'], 'code': '000000', 'password': 'new123'})
    assert wrong.status_code == 400
    success = client.post('/api/password-reset/confirm', json={'email': sent['email'], 'code': sent['code'], 'password': 'new123'})
    assert success.status_code == 200
    assert client.post('/api/login', json={'account': 'resetuser', 'password': 'new123'}).status_code == 200


def test_password_reset_response_does_not_enumerate_users(monkeypatch, client):
    monkeypatch.setattr('password_reset_service._send_email', lambda *args: ({'id': 'x'}, None))
    existing = client.post('/api/password-reset/request', json={'email': 'missing@example.com'})
    assert existing.status_code == 200
    assert existing.get_json() == client.post('/api/password-reset/request', json={'email': 'missing@example.com'}).get_json()


def test_admin_can_view_today_password_reset_emails(monkeypatch, client):
    register_user(client, username='adminreset', email='adminreset@example.com')
    monkeypatch.setattr('password_reset_service._send_email', lambda *args: ({'id': 'x'}, None))
    client.post('/api/password-reset/request', json={'email': 'adminreset@example.com'})
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    response = client.get('/api/admin/password-reset-emails', headers=auth_headers(client))
    assert response.status_code == 200
    assert response.get_json()['items'][0]['email'] == 'adminreset@example.com'
