def get_captcha(client):
    challenge = client.get('/api/captcha').get_json()
    answer = client.application.lookup_captcha_answer_for_tests(challenge['captcha_token'])
    return challenge, answer


def register_user(client, username='alice', email='alice@example.com', password='abc123', nickname='Alice'):
    challenge, answer = get_captcha(client)
    return client.post('/api/register', json={
        'username': username,
        'email': email,
        'password': password,
        'nickname': nickname,
        'captcha_token': challenge['captcha_token'],
        'captcha_answer': answer,
    })


def test_captcha_challenge_does_not_expose_answer(client):
    response = client.get('/api/captcha')
    data = response.get_json()
    assert response.status_code == 200
    assert data['image_url'].startswith('/static/captcha/correct/')
    assert 'answer' not in data
    assert data['captcha_token']


def test_captcha_answer_is_case_insensitive(client):
    challenge = client.get('/api/captcha').get_json()
    answer = client.application.lookup_captcha_answer_for_tests(challenge['captcha_token'])
    response = client.post('/api/captcha/verify', json={
        'captcha_token': challenge['captcha_token'],
        'captcha_answer': answer.swapcase(),
    })
    assert response.status_code == 200
    assert response.get_json()['ok'] is True


def test_register_requires_verified_captcha(client):
    response = client.post('/api/register', json={
        'username': 'alice', 'email': 'alice@example.com', 'password': 'abc123'
    })
    assert response.status_code == 400
    assert response.get_json()['error'] == '请先完成验证码'
    assert register_user(client).status_code == 201


def test_register_hashes_password_and_enforces_unique_username_email(client):
    assert register_user(client).status_code == 201
    with client.application.app_context():
        from db import get_db
        user = get_db().execute('SELECT * FROM users WHERE username = ?', ('alice',)).fetchone()
        assert user['password_hash'] != 'abc123'
    assert register_user(client, email='alice2@example.com').get_json()['error'] == '用户名已存在'
    assert register_user(client, username='alice2').get_json()['error'] == '邮箱已存在'


def test_password_requires_min_length_letter_and_number(client):
    assert register_user(client, password='a1').status_code == 400
    assert register_user(client, password='abcdef').status_code == 400
    assert register_user(client, password='123456').status_code == 400


def test_login_accepts_username_or_email(client):
    register_user(client)
    client.post('/api/logout')
    assert client.post('/api/login', json={'account': 'alice', 'password': 'abc123'}).status_code == 200
    client.post('/api/logout')
    assert client.post('/api/login', json={'account': 'alice@example.com', 'password': 'abc123'}).status_code == 200


def test_logout_clears_session(client):
    register_user(client)
    assert client.post('/api/logout').status_code == 200
    assert client.get('/api/me').get_json()['user'] is None


def test_me_returns_current_user_without_password_hash(client):
    register_user(client)
    data = client.get('/api/me').get_json()
    assert data['user']['username'] == 'alice'
    assert 'password_hash' not in data['user']
    assert data['csrf_token']
