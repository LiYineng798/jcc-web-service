from test_admin import login_admin


def test_site_config_returns_default_enabled(client):
    config = client.get('/api/site-config').get_json()
    assert config['simulator_enabled'] is True


def test_admin_can_get_settings(client):
    headers = login_admin(client)
    data = client.get('/api/admin/settings', headers=headers).get_json()
    assert data['simulator_enabled'] == 'true'


def test_admin_can_toggle_simulator(client):
    headers = login_admin(client)

    resp = client.put('/api/admin/settings', json={'simulator_enabled': 'false'}, headers=headers)
    assert resp.status_code == 200
    data = client.get('/api/admin/settings', headers=headers).get_json()
    assert data['simulator_enabled'] == 'false'

    resp = client.put('/api/admin/settings', json={'simulator_enabled': 'true'}, headers=headers)
    assert resp.status_code == 200
    data = client.get('/api/admin/settings', headers=headers).get_json()
    assert data['simulator_enabled'] == 'true'


def test_save_settings_uses_driver_specific_upsert(client, monkeypatch):
    from db import get_db
    from settings_service import save_settings

    captured = {}

    def capture_upsert(kind):
        captured['kind'] = kind
        return 'INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)'

    monkeypatch.setattr('settings_service.db_kind', lambda: 'postgres')
    monkeypatch.setattr('settings_service.upsert_setting_sql', capture_upsert)

    with client.application.app_context():
        payload, error, status_code = save_settings(get_db(), 1, {'simulator_enabled': 'false'})

    assert error is None
    assert status_code == 200
    assert payload == {'ok': True}
    assert captured == {'kind': 'postgres'}


def test_non_admin_cannot_access_settings(client):
    from test_auth import register_user

    resp = client.get('/api/admin/settings')
    assert resp.status_code == 401

    register_user(client, username='user1', email='user1@example.com')
    resp = client.get('/api/admin/settings')
    assert resp.status_code == 403


def test_simulator_hidden_when_disabled(client):
    headers = login_admin(client)

    resp = client.put('/api/admin/settings', json={'simulator_enabled': 'false'}, headers=headers)
    assert resp.status_code == 200

    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/tools/lineup-simulator"' not in index_html

    assert client.get('/tools/lineup-simulator').status_code == 404

    config = client.get('/api/site-config').get_json()
    assert config['simulator_enabled'] is False

    client.put('/api/admin/settings', json={'simulator_enabled': 'true'}, headers=headers)
