import json

import pytest

from db import get_db
from test_admin import login_admin
from test_auth import register_user
from test_lineup_permissions import auth_headers


def create_account(client, admin_headers, **overrides):
    response = client.post('/api/admin/automation-accounts', headers=admin_headers, json={
        'username': 'analysis_bot', 'nickname': '分析助手', **overrides,
    })
    assert response.status_code == 201, response.get_json()
    result = response.get_json()
    return result, {'Authorization': f"Bearer {result['token']}"}


def test_only_admin_can_create_and_credentials_are_not_readable(client, app):
    assert client.post('/api/admin/automation-accounts', json={}).status_code in (401, 403)
    register_user(client)
    assert client.post('/api/admin/automation-accounts', headers=auth_headers(client), json={}).status_code == 403
    admin = login_admin(client)
    created, bearer = create_account(client, admin)
    accounts = client.get('/api/admin/automation-accounts').get_json()
    assert 'token' not in accounts['items'][0] and 'token_hash' not in accounts['items'][0]
    with app.app_context():
        row = get_db().execute('SELECT * FROM automation_accounts').fetchone()
        assert row['token_hash'] != created['token'] and len(row['token_hash']) == 64
        audits = str([dict(row) for row in get_db().execute('SELECT * FROM audit_logs').fetchall()])
        assert created['token'] not in audits and row['token_hash'] not in audits
    assert client.get('/api/automation/me', headers=bearer).get_json()['can_import'] is False
    # A valid administrator cookie is deliberately not a machine credential.
    assert client.get('/api/automation/me').status_code == 401
    assert client.post('/api/automation/lineups/bulk-import', json={}).status_code == 401


def test_token_has_no_admin_session_or_ordinary_write_privileges(client, app):
    admin = login_admin(client)
    created, bearer = create_account(client, admin)
    other = app.test_client()
    for path in ('/admin', '/api/admin/users', '/api/admin/overview', '/api/admin/settings',
                 '/api/admin/daily-reports', '/api/admin/automation-accounts'):
        assert other.get(path, headers=bearer).status_code in (401, 403), path
    for method, path in [('post', '/api/lineups'), ('post', '/api/admin/live-comps/upload'),
                         ('put', '/api/admin/settings'), ('delete', '/api/admin/users/1')]:
        assert getattr(other, method)(path, headers=bearer, json={}).status_code in (401, 403, 404, 405)
    # Neither generic role edits nor password edits can convert machine accounts.
    assert client.put(f"/api/admin/users/{created['user_id']}", headers=admin, json={'role': 'admin'}).status_code == 403
    assert client.post('/api/admin/users', headers=admin, json={'role': 'automation'}).status_code == 400
    assert other.post('/api/login', json={'account': 'analysis_bot', 'password': created['token']}).status_code == 400
    assert other.post('/api/automation/lineups/bulk-import', headers=bearer, json={}).status_code == 403


def test_rotation_expiry_disable_and_delete(client, app):
    admin = login_admin(client)
    created, old = create_account(client, admin)
    url = f"/api/admin/automation-accounts/{created['user_id']}"
    rotated = client.post(url + '/rotate-token', headers=admin, json={'expires_in_days': 1}).get_json()
    bearer = {'Authorization': f"Bearer {rotated['token']}"}
    assert client.get('/api/automation/me', headers=old).status_code == 401
    assert client.get('/api/automation/me', headers=bearer).status_code == 200
    assert client.put(url, headers=admin, json={'status': 'disabled'}).status_code == 200
    assert client.get('/api/automation/me', headers=bearer).status_code == 401
    assert client.put(url, headers=admin, json={'status': 'active'}).status_code == 200
    assert client.get('/api/automation/me', headers=bearer).status_code == 401
    rotated = client.post(url + '/rotate-token', headers=admin, json={}).get_json()
    bearer = {'Authorization': f"Bearer {rotated['token']}"}
    with app.app_context():
        get_db().execute("UPDATE automation_accounts SET expires_at='2000-01-01T00:00:00Z'")
        get_db().commit()
    assert client.get('/api/automation/me', headers=bearer).status_code == 401
    assert client.delete(url, headers=admin).status_code == 200
    assert not client.get('/api/admin/automation-accounts').get_json()['items']
    assert not client.get('/api/admin/users?q=analysis_bot').get_json()['items']
    assert client.put(url, headers=admin, json={'status': 'active'}).status_code == 404


def test_import_scope_preview_retry_attribution_and_limits(client, app):
    admin = login_admin(client)
    created, bearer = create_account(client, admin, can_import=True, allowed_seasons=['s17-star-god'])
    body = {'season_id': 's17-star-god', 'raw_text': '【阵容码】#测试-助手阵容#BOTCODE001'}
    url = '/api/automation/lineups/bulk-import'
    preview = client.post(url + '/preview', headers=bearer, json=body)
    assert preview.status_code == 200 and preview.get_json()['importable_count'] == 1
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM lineups').fetchone()[0] == 0
    assert client.post(url, headers=bearer, json=body).status_code == 400
    headers = {**bearer, 'Idempotency-Key': 'batch-20261020-001'}
    result = client.post(url, headers=headers, json=body)
    assert result.status_code == 200, result.get_json()
    assert result.get_json()['created_count'] == 1
    assert client.post(url, headers=headers, json=body).get_json() == result.get_json()
    assert client.post(url, headers=headers, json={**body, 'raw_text': body['raw_text'] + '\ninvalid'}).status_code == 409
    assert client.post(url, headers=headers, json={**body, 'season_id': 's16-legends'}).status_code == 403
    assert client.post(url, headers=headers, json={**body, 'user_id': 1}).status_code == 400
    assert client.post(url, headers=headers, json={**body, 'raw_text': 'x\n' * 51}).status_code == 400
    with app.app_context():
        row = get_db().execute('SELECT user_id, status FROM lineups').fetchone()
        assert row['user_id'] == created['user_id'] and row['status'] == 'normal'
        assert get_db().execute('SELECT COUNT(*) FROM automation_imports').fetchone()[0] == 1


def test_import_failure_rolls_back_lineup_and_receipt(client, app, monkeypatch):
    admin = login_admin(client)
    _, bearer = create_account(client, admin, can_import=True, allowed_seasons=['s17-star-god'])
    import admin_lineup_service
    def fail(*args, **kwargs):
        raise RuntimeError('simulated audit failure')
    monkeypatch.setattr(admin_lineup_service, 'write_audit', fail)
    with pytest.raises(RuntimeError):
        client.post('/api/automation/lineups/bulk-import',
                    headers={**bearer, 'Idempotency-Key': 'rollback-case'},
                    json={'season_id': 's17-star-god', 'raw_text': '【阵容码】#测试-回滚#ROLLBACK001'})
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM lineups').fetchone()[0] == 0
        assert get_db().execute('SELECT COUNT(*) FROM automation_imports').fetchone()[0] == 0


def test_machine_responses_never_include_private_details(client, monkeypatch):
    admin = login_admin(client)
    _, bearer = create_account(client, admin)
    import automation
    private = {'ip_address': 'private-ip', 'email': 'private-email', 'token_hash': 'private-hash'}
    monkeypatch.setattr(automation, 'build_admin_copy_rank_payload', lambda *a, **k: {
        'date': '2026-10-19', 'items': [{'title': '阵容', 'uploader': '作者', 'copies': 3, 'details': [private], **private}],
    })
    monkeypatch.setattr(automation, 'get_daily_report', lambda *a: {
        'report_date': '2026-10-19', 'summary': {'successful_copies': 3, **private},
        'top_visitor_ips': [private], 'top_copied': [{'title': '阵容', **private}],
        'top_pages': [{'page_key': 'home', 'visits': 2, **private}], **private,
    })
    for path in ('/api/automation/copy-rank', '/api/automation/daily-reports/2026-10-19'):
        response = client.get(path, headers=bearer)
        assert response.status_code == 200
        assert 'private-' not in response.get_data(as_text=True)
        assert response.headers['Cache-Control'] == 'private, no-store'
    assert client.get('/api/automation/daily-reports/not-a-date', headers=bearer).status_code == 400


def test_rate_limit_and_invalid_configuration(client):
    admin = login_admin(client)
    for payload in ({'expires_in_days': 0}, {'expires_in_days': 91},
                    {'can_import': 'true'}, {'can_import': True, 'allowed_seasons': []},
                    {'can_import': True, 'allowed_seasons': ['hidden-season']}, {'role': 'admin'}):
        assert client.post('/api/admin/automation-accounts', headers=admin,
                           json={'username': 'analysis_bot', **payload}).status_code == 400
    _, bearer = create_account(client, admin)
    for _ in range(60):
        assert client.get('/api/automation/me', headers=bearer).status_code == 200
    assert client.get('/api/automation/me', headers=bearer).status_code == 429


def test_machine_accounts_do_not_inflate_registration_metrics(client, app):
    from admin_dashboard_service import build_admin_stats_payload
    from daily_report_service import build_daily_report_payload
    from db import now_text
    admin = login_admin(client)
    with app.app_context():
        before = build_admin_stats_payload(get_db())
    create_account(client, admin)
    with app.app_context():
        after = build_admin_stats_payload(get_db())
        assert after['total_users'] == before['total_users']
        assert after['today_users'] == before['today_users']
        report = build_daily_report_payload(get_db(), now_text()[:10])
        assert report['summary']['new_registrations'] == 0
