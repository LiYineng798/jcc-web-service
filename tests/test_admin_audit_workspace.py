import json

import pytest

from audit import write_audit
from db import get_db
from test_admin import login_admin
from test_auth import register_user


def seed(client):
    with client.application.app_context():
        db = get_db()
        write_audit(1, 'update_user', 'user', 8,
                    before={'nickname': '旧名字', 'password_hash': 'HASH-DO-NOT-EXPOSE'},
                    after={'nickname': '<img src=x onerror=alert(1)>', 'password': 'PLAIN-DO-NOT-EXPOSE',
                           'nested': [{'apiKey': 'KEY-DO-NOT-EXPOSE'}]})
        write_audit(1, 'create_live_comps_season', 'live_comp_season', target_key='s18')
        write_audit(None, 'future_action', 'future_type', target_key='literal_%_id')
        db.execute("UPDATE audit_logs SET created_at = '2026-09-11 23:59:59' WHERE action = 'update_user'")
        db.execute("UPDATE audit_logs SET created_at = '2026-09-12 00:00:00' WHERE action != 'update_user'")
        db.commit()


def test_audit_search_filters_and_full_history_facets(client):
    login_admin(client)
    seed(client)
    payload = client.get('/api/admin/audit-logs?page_size=1').get_json()
    assert payload['total'] == payload['total_all'] == 3
    assert payload['total_pages'] == 3
    assert len(payload['filters']['targets']) == 3
    assert not {'before', 'after', 'before_json', 'after_json'} & payload['items'][0].keys()
    assert payload['items'][0]['actor_label'] == '系统'
    assert payload['items'][0]['action_label'] == 'future_action'
    for query, expected in [('创建', 1), ('adminxlx', 2), ('s18', 1), ('literal_%', 1), ("' OR 1=1 --", 0)]:
        response = client.get('/api/admin/audit-logs', query_string={'q': query}).get_json()
        assert response['total'] == expected
    response = client.get('/api/admin/audit-logs?target_type=user&target_type=live_comp_season&kind=create').get_json()
    assert response['total'] == 1
    assert response['items'][0]['action_label'] == '创建实时阵容赛季'
    assert response['total_all'] == 3
    assert client.get('/api/admin/audit-logs?kind=unknown').get_json()['total'] == 0


def test_audit_date_boundaries_and_page_clamp(client):
    login_admin(client)
    seed(client)
    payload = client.get('/api/admin/audit-logs?start=2026-09-11&end=2026-09-11&page=999').get_json()
    assert payload['total'] == 1
    assert payload['page'] == 1
    assert payload['items'][0]['action'] == 'update_user'
    assert client.get('/api/admin/audit-logs?start=2026-09-12&end=2026-09-12').get_json()['total'] == 2


@pytest.mark.parametrize('query', ['start=invalid', 'start=2026-09-13&end=2026-09-12', 'end=9999-12-31'])
def test_audit_invalid_dates_are_client_errors(client, query):
    login_admin(client)
    assert client.get('/api/admin/audit-logs?' + query).status_code == 400


def test_audit_detail_is_on_demand_redacted_and_not_cached(client):
    login_admin(client)
    seed(client)
    item = client.get('/api/admin/audit-logs?q=更新用户').get_json()['items'][0]
    response = client.get(f"/api/admin/audit-logs/{item['id']}")
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'private, no-store'
    body = response.get_json()
    assert body['before']['password_hash'] == '[已隐藏敏感字段]'
    assert body['after']['password'] == '[已隐藏敏感字段]'
    assert body['after']['nested'][0]['apiKey'] == '[已隐藏敏感字段]'
    assert 'DO-NOT-EXPOSE' not in response.get_data(as_text=True)
    assert body['before']['nickname'] == '旧名字'
    assert '<img' in body['after']['nickname']  # JSON string; React must render it as text.
    assert client.get('/api/admin/audit-logs/99999').status_code == 404


def test_audit_detail_preserves_both_target_identifiers_and_handles_bad_json(client):
    login_admin(client)
    with client.application.app_context():
        db = get_db()
        write_audit(1, 'legacy', 'season', 42, target_key='s18')
        db.execute("UPDATE audit_logs SET before_json = 'broken password=private', after_json = ?", (
            json.dumps({'setting_key': 'RESEND_API_KEY', 'setting_value': 'private'}),))
        db.commit()
    item = client.get('/api/admin/audit-logs').get_json()['items'][0]
    payload = client.get(f"/api/admin/audit-logs/{item['id']}").get_json()
    assert payload['target_id'] == 42 and payload['target_key'] == 's18'
    assert payload['before'] == '[历史记录无法解析]'
    assert payload['after']['setting_value'] == '[已隐藏敏感字段]'


def test_audit_endpoints_require_active_admin(client):
    for url in ['/api/admin/audit-logs', '/api/admin/audit-logs/1']:
        assert client.get(url).status_code == 401
    register_user(client)
    for url in ['/api/admin/audit-logs', '/api/admin/audit-logs/1']:
        assert client.get(url).status_code == 403
    client.post('/api/logout')
    login_admin(client)
    with client.application.app_context():
        db = get_db()
        db.execute("UPDATE users SET status = 'disabled' WHERE username = 'adminxlx'")
        db.commit()
    assert client.get('/api/admin/audit-logs/1').status_code in (401, 403)


def test_admin_loads_scoped_audit_island(client):
    login_admin(client)
    html = client.get('/admin').get_data(as_text=True)
    assert '/static/admin/audit-logs/app.css?v=' in html
    assert '/static/admin/audit-logs/app.js?v=' in html
