from test_auth import register_user


def test_browser_style_add_lineup_after_register(client):
    register_user(client)
    me = client.get('/api/me').get_json()
    response = client.post('/api/lineups', json={'name': '测试阵容', 'code': '#TESTCODE'}, headers={'X-CSRF-Token': me['csrf_token']})
    assert response.status_code == 201
    assert response.get_json()['name'] == '测试阵容'


def test_browser_style_add_lineup_after_admin_login(client):
    login = client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    assert login.status_code == 200
    me = client.get('/api/me').get_json()
    response = client.post('/api/lineups', json={'name': '管理员阵容', 'code': '#ADMINCODE'}, headers={'X-CSRF-Token': me['csrf_token']})
    assert response.status_code == 201
    assert response.get_json()['owner_nickname'] == '系统'
