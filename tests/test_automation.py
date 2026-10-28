import json
import sqlite3

import pytest
from werkzeug.security import check_password_hash
from db import get_db
from test_admin import login_admin
from test_auth import register_user
from test_lineup_permissions import auth_headers
from test_live_comps import sample_live_comps_payload, write_live_comps_seed

PREFIX = '/api/admin/assistant'
PASSWORD = 'AssistantPass1234'


def create_account(client, headers, **overrides):
    response = client.post('/api/admin/automation-accounts', headers=headers, json={
        'username': 'analysis_bot', 'nickname': '分析助手', 'password': PASSWORD, **overrides})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def login_bot(app):
    bot = app.test_client()
    response = bot.post('/api/login', json={'account': 'analysis_bot', 'password': PASSWORD})
    assert response.status_code == 200, response.get_json()
    return bot, auth_headers(bot)


def test_account_creation_login_and_secret_storage(client, app):
    register_user(client)
    assert client.post('/api/admin/automation-accounts', headers=auth_headers(client), json={}).status_code == 403
    admin = login_admin(client)
    account = create_account(client, admin)
    assert 'password' not in account and 'token' not in account
    bot, headers = login_bot(app)
    assert bot.get('/admin').status_code == 200
    html = bot.get('/admin').get_data(as_text=True)
    assert 'assistant.js' in html and 'data-admin-tab="users"' not in html
    assert bot.get(PREFIX + '/me').get_json()['can_import'] is False
    assert bot.get(PREFIX + '/overview').status_code == 200
    with app.app_context():
        row = get_db().execute("SELECT password_hash FROM users WHERE id=?", (account['user_id'],)).fetchone()
        assert check_password_hash(row['password_hash'], PASSWORD)
        assert PASSWORD not in str([dict(row) for row in get_db().execute('SELECT * FROM audit_logs')])
        assert 'token_hash' not in [row[1] for row in get_db().execute('PRAGMA table_info(automation_accounts)')]
        assert not get_db().execute("SELECT name FROM sqlite_master WHERE name='automation_imports'").fetchone()
    assert 'password_hash' not in str(client.get('/api/admin/automation-accounts').get_json())
    assert bot.get('/api/automation/me').status_code == 404
    assert client.get(PREFIX + '/overview').status_code == 403


def test_restricted_session_cannot_escape_workspace(client, app):
    admin = login_admin(client)
    create_account(client, admin)
    bot, headers = login_bot(app)
    for path in ('/api/admin/users', '/api/admin/settings', '/api/admin/overview', '/api/admin/daily-reports',
                 '/api/admin/live-comps/seasons', '/api/admin/automation-accounts'):
        assert bot.get(path).status_code == 403, path
    for method, path in [('post', '/api/lineups'), ('put', '/api/admin/users/1'), ('post', '/api/admin/live-comps/upload'),
                         ('put', '/api/admin/settings'), ('post', '/api/admin/lineups/bulk-import'),
                         ('post', '/api/admin/live-comps/seasons/s17-star-god/touch-updated-at'), ('post', '/api/register')]:
        assert getattr(bot, method)(path, headers=headers, json={}).status_code == 403, path
    assert bot.post(PREFIX + '/lineups/bulk-import', json={}).status_code == 403
    assert bot.post(PREFIX + '/lineups/bulk-import', headers=headers, json={}).status_code == 403
    assert client.post('/api/admin/users', headers=admin, json={'role': 'automation'}).status_code == 400
    outsider = app.test_client()
    assert outsider.get(PREFIX + '/overview').status_code == 401


def test_disable_enable_reset_expire_delete_revoke_sessions(client, app):
    admin = login_admin(client)
    account = create_account(client, admin)
    url = '/api/admin/automation-accounts/' + str(account['user_id'])
    bot, _ = login_bot(app)
    assert client.put(url, headers=admin, json={'status': 'disabled'}).status_code == 200
    # Re-enable before using old cookie: the previous login must still be invalid.
    assert client.put(url, headers=admin, json={'status': 'active'}).status_code == 200
    assert bot.get(PREFIX + '/overview').status_code == 401
    bot, _ = login_bot(app)
    assert client.put(url, headers=admin, json={'password': 'ChangedPassword5678'}).status_code == 200
    assert bot.get(PREFIX + '/overview').status_code == 401
    assert bot.post('/api/login', json={'account': 'analysis_bot', 'password': PASSWORD}).status_code == 400
    assert bot.post('/api/login', json={'account': 'analysis_bot', 'password': 'ChangedPassword5678'}).status_code == 200
    with app.app_context():
        get_db().execute("UPDATE automation_accounts SET expires_at='2000-01-01T00:00:00Z'")
        get_db().commit()
    assert bot.get('/admin').status_code == 401
    assert bot.post('/api/login', json={'account': 'analysis_bot', 'password': 'ChangedPassword5678'}).status_code == 400
    assert client.put(url, headers=admin, json={'expires_in_days': 30}).status_code == 200
    assert bot.post('/api/login', json={'account': 'analysis_bot', 'password': 'ChangedPassword5678'}).status_code == 200
    assert client.delete(url, headers=admin).status_code == 200
    assert bot.get('/admin').status_code in (401, 403)
    assert not client.get('/api/admin/automation-accounts').get_json()['items']
    assert not client.get('/api/admin/users?q=analysis_bot').get_json()['items']


def test_scoped_import_preview_duplicates_attribution_and_revocation(client, app):
    admin = login_admin(client)
    account = create_account(client, admin, can_import=True, allowed_seasons=['s17-star-god'])
    bot, headers = login_bot(app)
    body = {'season_id': 's17-star-god', 'raw_text': '【阵容码】#测试-助手阵容#BOTCODE001'}
    url = PREFIX + '/lineups/bulk-import'
    assert bot.post(url + '/preview', headers=headers, json=body).get_json()['importable_count'] == 1
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM lineups').fetchone()[0] == 0
    assert bot.post(url, headers=headers, json=body).get_json()['created_count'] == 1
    assert bot.post(url, headers=headers, json=body).get_json()['created_count'] == 0
    assert bot.post(url, headers=headers, json={**body, 'season_id': 's16-legends'}).status_code == 403
    assert bot.post(url, headers=headers, json={**body, 'user_id': 1}).status_code == 400
    assert bot.post(url, headers=headers, json={**body, 'raw_text': 'x\n' * 51}).status_code == 400
    with app.app_context():
        row = get_db().execute('SELECT user_id,status FROM lineups').fetchone()
        assert row['user_id'] == account['user_id'] and row['status'] == 'normal'
    assert client.put('/api/admin/automation-accounts/' + str(account['user_id']), headers=admin, json={'can_import': False}).status_code == 200
    assert bot.post(url, headers=headers, json=body).status_code == 403


def test_import_failure_is_atomic(client, app, monkeypatch):
    admin = login_admin(client)
    create_account(client, admin, can_import=True, allowed_seasons=['s17-star-god'])
    bot, headers = login_bot(app)
    def fail(*args, **kwargs):
        raise RuntimeError('simulated audit failure')
    monkeypatch.setattr('admin_lineup_service.write_audit', fail)
    with pytest.raises(RuntimeError):
        bot.post(PREFIX + '/lineups/bulk-import', headers=headers,
                 json={'season_id': 's17-star-god', 'raw_text': '【阵容码】#测试-回滚#ROLLBACK001'})
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM lineups').fetchone()[0] == 0


def test_touch_scope_csrf_and_content_unchanged(client, app):
    admin = login_admin(client)
    account = create_account(client, admin, can_touch=True, touch_seasons=['s17-star-god'])
    write_live_comps_seed(client, sample_live_comps_payload())
    from pathlib import Path
    path = Path(app.config['LIVE_COMPS_DATA_PATH'])
    before = path.read_bytes()
    bot, headers = login_bot(app)
    url = PREFIX + '/live-seasons/s17-star-god/touch'
    assert bot.get(PREFIX + '/live-seasons').status_code == 200
    assert bot.post(url, json={}).status_code == 403
    assert bot.post(url, headers=headers, json={'updated_at': 'future'}).status_code == 400
    assert bot.post(PREFIX + '/live-seasons/s16-legends/touch', headers=headers, json={}).status_code == 403
    assert bot.post(url, headers=headers, json={}).status_code == 200
    assert path.read_bytes() == before
    with app.app_context():
        row = get_db().execute("SELECT actor_user_id FROM audit_logs WHERE action='touch_live_comps_season_updated_at'").fetchone()
        assert row['actor_user_id'] == account['user_id']
    client.put('/api/admin/automation-accounts/' + str(account['user_id']), headers=admin, json={'can_touch': False})
    assert bot.post(url, headers=headers, json={}).status_code == 403


def test_responses_exclude_private_data(client, app, monkeypatch):
    admin = login_admin(client); create_account(client, admin); bot, _ = login_bot(app)
    private = {'ip_address': 'private-ip', 'email': 'private-email'}
    monkeypatch.setattr('automation.build_admin_copy_rank_payload', lambda *a, **k: {
        'date': '2026-10-19', 'items': [{'title': '阵容', 'uploader': '作者', 'copies': 3, 'details': [private], **private}]})
    monkeypatch.setattr('automation.get_daily_report', lambda *a: {
        'report_date': '2026-10-19', 'summary': {'total_copies': 3, **private}, 'top_visitor_ips': [private],
        'top_copied': [{'title': '阵容', 'copies': 3, 'details': [private], **private}]})
    for path in ('/copy-rank', '/daily-reports/2026-10-19'):
        response = bot.get(PREFIX + path)
        assert response.status_code == 200
        assert 'private-' not in response.get_data(as_text=True)
        assert response.headers['Cache-Control'] == 'private, no-store'


def test_invalid_creation_and_read_rate_limit(client, app):
    admin = login_admin(client)
    for data in ({'password': 'short'}, {'expires_in_days': 91}, {'can_import': 'true'}, {'can_touch': True, 'touch_seasons': ['hidden']}, {'role': 'admin'}):
        assert client.post('/api/admin/automation-accounts', headers=admin, json={'username': 'bad', 'password': PASSWORD, **data}).status_code == 400
    create_account(client, admin); bot, _ = login_bot(app)
    for _ in range(60):
        assert bot.get(PREFIX + '/me').status_code == 200
    assert bot.get(PREFIX + '/me').status_code == 429


def test_upgrade_old_sqlite_schema_preserves_identity_and_drops_tokens():
    from automation_schema import migrate_automation_sessions
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE automation_accounts(user_id INTEGER PRIMARY KEY,token_hash TEXT,token_prefix TEXT,expires_at TEXT)')
    db.execute("INSERT INTO automation_accounts VALUES(7,'oldsecret','prefix','future')")
    db.execute('CREATE TABLE automation_imports(user_id INTEGER)')
    migrate_automation_sessions(db)
    migrate_automation_sessions(db)
    assert tuple(db.execute('SELECT user_id,can_touch,session_version FROM automation_accounts').fetchone()) == (7, 0, 1)
    assert 'token_hash' not in [row[1] for row in db.execute('PRAGMA table_info(automation_accounts)')]


def test_avatar_is_own_account_only_and_audited(client, app):
    admin = login_admin(client)
    account = create_account(client, admin)
    bot, headers = login_bot(app)
    assert bot.get(PREFIX + '/me').get_json()['can_avatar'] is True
    body = {'color': '#7E96AD', 'preset': 'nova', 'expression': 'happy'}
    assert bot.put(PREFIX + '/avatar', json=body).status_code == 403
    assert bot.put('/api/me/avatar', headers=headers, json=body).status_code == 403
    assert bot.put(PREFIX + '/avatar', headers=headers, json={**body, 'user_id': 1}).status_code == 400
    assert bot.put(PREFIX + '/avatar', headers=headers, json={**body, 'preset': 'unknown'}).status_code == 400
    response = bot.put(PREFIX + '/avatar', headers=headers, json=body)
    assert response.status_code == 200
    assert response.get_json()['user']['avatar_config'] == {'version': 1, 'preset': 'nova', 'expression': 'happy', 'color': '#7e96ad'}
    with app.app_context():
        rows = get_db().execute('SELECT id, avatar_preset FROM users ORDER BY id').fetchall()
        assert {row['id']: row['avatar_preset'] for row in rows}[account['user_id']] == 'nova'
        assert all(row['avatar_preset'] != 'nova' for row in rows if row['id'] != account['user_id'])
        assert get_db().execute("SELECT actor_user_id FROM audit_logs WHERE action='automation_update_avatar'").fetchone()[0] == account['user_id']


def test_import_reports_target_and_format_only_scope(client, app):
    admin = login_admin(client)
    create_account(client, admin, can_import=True, allowed_seasons=['s17-star-god'])
    bot, headers = login_bot(app)
    body = {'season_id': 's17-star-god', 'raw_text': '【阵容码】#S17-助手阵容#BOTCODE002\n#坏行'}
    preview = bot.post(PREFIX + '/lineups/bulk-import/preview', headers=headers, json=body).get_json()
    assert preview['target'] == {'season_id': 's17-star-god', 'season_name': 'S17 · 星神', 'uploader': '分析助手 (@analysis_bot)',
                                 'publish_status': 'normal', 'publish_status_label': '公开：导入后立即出现在前台普通阵容列表'}
    assert preview['validation']['content_parsed'] is False and '未解析阵容内容' in preview['validation']['summary']
    assert [item['status'] for item in preview['items']] == ['importable', 'invalid']
    assert preview['items'][0]['name'] == '助手阵容'
    result = bot.post(PREFIX + '/lineups/bulk-import', headers=headers, json=body).get_json()
    created = [item for item in result['items'] if item['status'] == 'created']
    assert result['target']['season_id'] == 's17-star-god' and len(created) == 1 and created[0]['id']
    listed = bot.get(PREFIX + '/lineups?season_id=s17-star-god').get_json()['items']
    assert listed[0]['id'] == created[0]['id']


def test_touch_reports_previous_and_zoned_times(client, app):
    admin = login_admin(client)
    create_account(client, admin, can_touch=True, touch_seasons=['s17-star-god'])
    write_live_comps_seed(client, sample_live_comps_payload())
    bot, headers = login_bot(app)
    season = bot.get(PREFIX + '/live-seasons').get_json()['seasons'][0]
    assert season['updated_at'][-6] in '+-'
    result = bot.post(PREFIX + '/live-seasons/s17-star-god/touch', headers=headers, json={}).get_json()
    assert result['season_name'] == 'S17 · 星神'
    assert result['previous_updated_at'] == season['updated_at']
    assert result['updated_at'][-6] in '+-' and result['updated_at'] >= result['previous_updated_at']
