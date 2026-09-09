import pytest


@pytest.mark.parametrize('path', ['/', '/auth', '/patch-notes'])
def test_shared_notifications_load_before_page_scripts(client, path):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('/static/notifications.js?v=') == 1
    assert html.count('/static/notifications.css?v=') == 1
    assert 'id="toast"' not in html
    if path == '/auth':
        assert html.index('/static/notifications.js?v=') < html.index('/static/auth.js?v=')


def test_admin_and_standalone_simulator_include_notifications(client):
    login = client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'}).get_json()
    client.put('/api/admin/settings', json={'simulator_enabled': 'true'}, headers={'X-CSRF-Token': login['csrf_token']})
    for path in ['/admin', '/tools/lineup-simulator']:
        response = client.get(path)
        assert response.status_code == 200
        assert '/static/notifications.js?v=' in response.get_data(as_text=True)
        assert '/static/notifications.css?v=' in response.get_data(as_text=True)
