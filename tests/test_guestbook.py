import pytest


def _register(client, username, email, nickname, password):
    challenge = client.get('/api/captcha').get_json()
    answer = client.application.lookup_captcha_answer_for_tests(challenge['captcha_token'])
    return client.post('/api/register', json={
        'username': username,
        'email': email,
        'nickname': nickname,
        'password': password,
        'captcha_token': challenge['captcha_token'],
        'captcha_answer': answer,
    })


def test_guest_can_post_message(client):
    resp = client.post('/api/guestbook', json={
        'nickname': '热心玩家',
        'content': '希望增加搜索功能',
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['ok'] is True


def test_logged_in_user_post_message(client):
    _register(client, 'testuser1', 'test1@test.com', '测试用户', 'abc123')
    me = client.get('/api/me').get_json()
    resp = client.post('/api/guestbook', json={'content': '登录用户留言'},
                       headers={'X-CSRF-Token': me['csrf_token']})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['ok'] is True


def test_post_message_requires_nickname_for_guest(client):
    resp = client.post('/api/guestbook', json={'content': '无昵称留言'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert '昵称' in data['error']


def test_post_message_requires_content(client):
    resp = client.post('/api/guestbook', json={'nickname': 'test'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert '留言内容' in data['error']


def test_post_message_nickname_too_long(client):
    resp = client.post('/api/guestbook', json={
        'nickname': 'A' * 21,
        'content': 'test content',
    })
    assert resp.status_code == 400


def test_post_message_content_too_long(client):
    resp = client.post('/api/guestbook', json={
        'nickname': 'test',
        'content': 'A' * 501,
    })
    assert resp.status_code == 400


def test_rate_limit_guestbook(client):
    for _ in range(2):
        resp = client.post('/api/guestbook', json={
            'nickname': 'tester',
            'content': 'rate limit test',
        })
    assert resp.status_code == 429
    data = resp.get_json()
    assert '频繁' in data['error']


def test_admin_can_list_messages(client):
    client.post('/api/guestbook', json={'nickname': 'u1', 'content': 'msg1'})
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    resp = client.get('/api/guestbook')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total'] >= 1
    assert 'items' in data


def test_non_admin_cannot_list_messages(client):
    resp = client.get('/api/guestbook')
    assert resp.status_code == 401


def test_admin_can_delete_message(client):
    client.post('/api/guestbook', json={'nickname': 'u1', 'content': 'to be deleted'})
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    me = client.get('/api/me').get_json()
    list_resp = client.get('/api/guestbook')
    msg_id = list_resp.get_json()['items'][0]['id']
    resp = client.delete(f'/api/guestbook/{msg_id}',
                         headers={'X-CSRF-Token': me['csrf_token']})
    assert resp.status_code == 200
    list_resp2 = client.get('/api/guestbook')
    assert all(item['id'] != msg_id for item in list_resp2.get_json()['items'])


def test_csrf_protects_guestbook_post(client):
    _register(client, 'csrfuser', 'csrf@test.com', 'csrf', 'abc123')
    with client.session_transaction() as sess:
        sess['csrf_token'] = ''
    resp = client.post('/api/guestbook', json={'nickname': 'x', 'content': 'test'})
    assert resp.status_code == 403
