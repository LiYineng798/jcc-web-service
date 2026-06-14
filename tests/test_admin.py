from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup
from test_live_comps import sample_live_comps_payload, write_live_comps_seed


def login_admin(client):
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    return auth_headers(client)


def test_admin_page_requires_admin_login(client):
    assert client.get('/admin').status_code == 401
    register_user(client)
    assert client.get('/admin').status_code == 403
    client.post('/api/logout')
    login_admin(client)
    assert client.get('/admin').status_code == 200


def test_admin_can_query_users_by_username_or_email(client):
    register_user(client, username='alice', email='alice@example.com')
    client.post('/api/logout')
    headers = login_admin(client)
    data = client.get('/api/admin/users?q=alice', headers=headers).get_json()
    assert data['items'][0]['username'] == 'alice'


def test_admin_can_create_update_disable_delete_users_with_validation(client):
    headers = login_admin(client)
    created = client.post('/api/admin/users', json={'username': 'bob', 'email': 'bob@example.com', 'password': 'abc123', 'nickname': 'Bob'}, headers=headers)
    assert created.status_code == 201
    user_id = created.get_json()['id']
    assert client.put(f'/api/admin/users/{user_id}', json={'nickname': 'Bobby'}, headers=headers).status_code == 200
    assert client.delete(f'/api/admin/users/{user_id}', headers=headers).status_code == 204


def test_admin_can_reset_user_password_and_new_password_takes_effect(client):
    register_user(client, username='alice', email='alice@example.com', password='abc123')
    client.post('/api/logout')

    headers = login_admin(client)
    users = client.get('/api/admin/users?q=alice', headers=headers).get_json()
    user_id = users['items'][0]['id']
    response = client.put(
        f'/api/admin/users/{user_id}',
        json={'password': 'newabc123'},
        headers=headers,
    )
    assert response.status_code == 200

    client.post('/api/logout')
    assert client.post('/api/login', json={'account': 'alice', 'password': 'abc123'}).status_code == 400
    assert client.post('/api/login', json={'account': 'alice', 'password': 'newabc123'}).status_code == 200


def test_admin_can_edit_hide_delete_any_lineup(client):
    register_user(client)
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    headers = login_admin(client)
    assert client.put(f"/api/admin/lineups/{lineup['id']}", json={'name': 'new'}, headers=headers).status_code == 200
    assert client.put(f"/api/admin/lineups/{lineup['id']}", json={'status': 'hidden'}, headers=headers).status_code == 200


def test_admin_lineups_api_includes_hidden_lineup_and_code(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='隐藏阵容', code='#HIDECODE001').get_json()
    client.post('/api/logout')

    headers = login_admin(client)
    assert client.put(f"/api/admin/lineups/{lineup['id']}", json={'status': 'hidden'}, headers=headers).status_code == 200

    payload = client.get('/api/admin/lineups', headers=headers).get_json()
    target = next(item for item in payload['items'] if item['id'] == lineup['id'])
    assert target['status'] == 'hidden'
    assert target['code'] == '#HIDECODE001'


def test_admin_can_list_and_update_live_comps_seasons(client):
    headers = login_admin(client)
    manifest_path = client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH']
    season_dir = client.application.config['LIVE_COMPS_SEASON_DIR']
    Path = __import__('pathlib').Path
    Path(season_dir).mkdir(parents=True, exist_ok=True)
    Path(manifest_path).write_text(__import__('json').dumps({
        'default_season_id': 's17-star-god',
        'seasons': [{'id': 's17-star-god', 'name': 'S17 · 星神', 'status': 'active', 'order': 1, 'description': ''}],
    }, ensure_ascii=False), encoding='utf-8')

    listed = client.get('/api/admin/live-comps/seasons', headers=headers)
    assert listed.status_code == 200
    assert listed.get_json()['default_season_id'] == 's17-star-god'

    updated = client.put(
        '/api/admin/live-comps/seasons/s17-star-god',
        json={'status': 'archived', 'description': '已归档'},
        headers=headers,
    )
    assert updated.status_code == 200
    payload = updated.get_json()
    assert payload['seasons'][0]['status'] == 'archived'
    assert payload['seasons'][0]['description'] == '已归档'


def test_admin_can_adjust_like_and_copy_counts_and_recalculate_score(client):
    register_user(client)
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    headers = login_admin(client)
    data = client.post(f"/api/admin/lineups/{lineup['id']}/adjust-score", json={'admin_like_adjustment': 1, 'admin_copy_adjustment': 2}, headers=headers).get_json()
    assert data['like_count'] == 1
    assert data['copy_count'] == 2
    assert data['score'] == 7


def test_admin_stats_include_total_users_today_users_today_logins_hourly(client):
    register_user(client)
    client.post('/api/logout')
    headers = login_admin(client)
    data = client.get('/api/admin/stats', headers=headers).get_json()
    assert data['total_users'] == 1
    assert data['today_users'] == 1
    assert 'today_logins' in data
    assert 'hourly_registrations' in data
    assert 'today_uv' in data
    assert 'yesterday_uv' in data
    assert 'last_7_days_uv' in data


def test_admin_actions_write_audit_logs(client):
    headers = login_admin(client)
    client.post('/api/admin/users', json={'username': 'eve', 'email': 'eve@example.com', 'password': 'abc123'}, headers=headers)
    logs = client.get('/api/admin/audit-logs', headers=headers).get_json()
    assert logs['items'][0]['action'] == 'create_user'


def test_admin_can_view_report_details_and_resolve_with_hidden_lineup(client):
    register_user(client, username='owner', email='owner@example.com', nickname='作者')
    lineup = create_lineup(client, name='违规阵容', code='#BADCODE').get_json()
    client.post('/api/logout')

    register_user(client, username='reporter', email='reporter@example.com', nickname='举报人')
    report = client.post(
        f"/api/lineups/{lineup['id']}/report",
        json={'reason': '阵容码无效'},
        headers=auth_headers(client),
    )
    assert report.status_code == 201
    report_id = report.get_json()['id']
    client.post('/api/logout')

    headers = login_admin(client)
    reports = client.get('/api/admin/reports', headers=headers).get_json()
    assert reports['items'][0]['id'] == report_id
    assert reports['items'][0]['reason'] == '阵容码无效'
    assert reports['items'][0]['reporter_nickname'] == '举报人'
    assert reports['items'][0]['lineup_name'] == '违规阵容'
    assert reports['items'][0]['lineup_code'] == '#BADCODE'
    assert reports['items'][0]['owner_nickname'] == '作者'

    resolved = client.post(
        f'/api/admin/reports/{report_id}/resolve',
        json={'status': 'resolved', 'hide_lineup': True},
        headers=headers,
    )
    assert resolved.status_code == 200
    assert resolved.get_json()['status'] == 'resolved'

    pending_reports = client.get('/api/admin/reports', headers=headers).get_json()
    assert pending_reports['items'] == []
    updated_report = client.get('/api/admin/reports?status=resolved', headers=headers).get_json()['items'][0]
    assert updated_report['status'] == 'resolved'
    assert updated_report['lineup_status'] == 'hidden'


def test_admin_can_dismiss_report_without_hiding_lineup(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client).get_json()
    report = client.post(
        f"/api/lineups/{lineup['id']}/report",
        json={'reason': '误报'},
        headers=auth_headers(client),
    ).get_json()
    client.post('/api/logout')

    headers = login_admin(client)
    response = client.post(
        f"/api/admin/reports/{report['id']}/resolve",
        json={'status': 'dismissed', 'hide_lineup': False},
        headers=headers,
    )
    assert response.status_code == 200
    pending_reports = client.get('/api/admin/reports', headers=headers).get_json()
    assert pending_reports['items'] == []
    updated_report = client.get('/api/admin/reports?status=dismissed', headers=headers).get_json()['items'][0]
    assert updated_report['status'] == 'dismissed'
    assert updated_report['lineup_status'] == 'normal'


def test_admin_lineup_search_matches_name_code_and_owner(client):
    register_user(client, username='owner', email='owner@example.com', nickname='阵容作者')
    create_lineup(client, name='法师九五', code='#MAGECODE')
    create_lineup(client, name='斗士阵容', code='#FIGHTERCODE')
    client.post('/api/logout')

    headers = login_admin(client)
    by_name = client.get('/api/admin/lineups?q=法师', headers=headers).get_json()
    by_code = client.get('/api/admin/lineups?q=FIGHTER', headers=headers).get_json()
    by_owner = client.get('/api/admin/lineups?q=阵容作者', headers=headers).get_json()

    assert [item['name'] for item in by_name['items']] == ['法师九五']
    assert [item['name'] for item in by_code['items']] == ['斗士阵容']
    assert {item['name'] for item in by_owner['items']} == {'法师九五', '斗士阵容'}


def test_admin_user_search_matches_username_email_and_nickname(client):
    register_user(client, username='alice', email='alice@example.com', nickname='小爱')
    client.post('/api/logout')

    headers = login_admin(client)
    assert client.get('/api/admin/users?q=alice', headers=headers).get_json()['items'][0]['username'] == 'alice'
    assert client.get('/api/admin/users?q=example.com', headers=headers).get_json()['items'][0]['email'] == 'alice@example.com'
    assert client.get('/api/admin/users?q=小爱', headers=headers).get_json()['items'][0]['nickname'] == '小爱'


def test_admin_growth_stats_returns_funnel_fields(client):
    client.get('/')
    me = client.get('/api/me').get_json()
    client.post(
        '/api/growth-events',
        json={'event_name': 'click_login_entry', 'page_key': 'home', 'payload': {'source': 'header'}},
        headers={'X-CSRF-Token': me['csrf_token']},
    )
    register_user(client, username='growth', email='growth@example.com')
    client.post('/api/logout')

    headers = login_admin(client)
    today = __import__('datetime').datetime.now().strftime('%Y-%m-%d')
    data = client.get(f'/api/admin/growth?date={today}', headers=headers).get_json()

    assert data['date'] == today
    assert 'home_uv' in data
    assert 'login_entry_visitors' in data
    assert 'auth_page_visitors' in data
    assert 'successful_registrations' in data
    assert 'successful_logins' in data
    assert 'guest_like_visitors' in data
    assert 'guest_favorite_visitors' in data
    assert 'post_login_like_users' in data
    assert 'post_login_favorite_users' in data
    assert 'post_login_create_lineup_users' in data
    assert 'conversion_rates' in data
    assert data['successful_logins'] == 0


def test_admin_overview_returns_lightweight_dashboard_payload(client):
    register_user(client, username='alice', email='alice@example.com')
    client.post('/api/logout')
    headers = login_admin(client)

    data = client.get('/api/admin/overview', headers=headers).get_json()

    assert 'stats' in data
    assert 'traffic_7d' in data
    assert 'todos' in data
    assert data['stats']['pending_reports_count'] >= 0
    assert data['stats']['today_uv'] >= 0
    assert len(data['traffic_7d']) == 7


def test_admin_reports_support_pagination(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='举报测试阵容', code='#REPORTPAGE01').get_json()
    client.post('/api/logout')

    for index in range(3):
        register_user(client, username=f'reporter{index}', email=f'reporter{index}@example.com')
        client.post(
            f"/api/lineups/{lineup['id']}/report",
            json={'reason': f'举报 {index}'},
            headers=auth_headers(client),
        )
        client.post('/api/logout')

    headers = login_admin(client)
    page_1 = client.get('/api/admin/reports?status=pending&page=1&page_size=2', headers=headers).get_json()
    page_2 = client.get('/api/admin/reports?status=pending&page=2&page_size=2', headers=headers).get_json()

    assert page_1['total'] == 3
    assert page_1['page'] == 1
    assert page_1['page_size'] == 2
    assert len(page_1['items']) == 2
    assert page_2['page'] == 2
    assert len(page_2['items']) == 1


def test_admin_lineups_and_users_support_paginated_results(client):
    register_user(client, username='owner', email='owner@example.com', nickname='作者')
    create_lineup(client, name='法师九五', code='#ADMINPAGE01')
    create_lineup(client, name='斗士九五', code='#ADMINPAGE02')
    client.post('/api/logout')

    headers = login_admin(client)
    lineups = client.get('/api/admin/lineups?q=九五&page=1&page_size=1', headers=headers).get_json()
    users = client.get('/api/admin/users?q=作者&page=1&page_size=10', headers=headers).get_json()

    assert lineups['total'] == 2
    assert len(lineups['items']) == 1
    assert users['total'] == 1
    assert users['items'][0]['nickname'] == '作者'


def test_admin_audit_logs_support_pagination_without_filters(client):
    headers = login_admin(client)
    client.post('/api/admin/users', json={'username': 'eve2', 'email': 'eve2@example.com', 'password': 'abc123'}, headers=headers)

    payload = client.get('/api/admin/audit-logs?page=1&page_size=10', headers=headers).get_json()

    assert payload['page'] == 1
    assert payload['page_size'] == 10
    assert payload['total'] >= 1
    assert payload['items'][0]['action'] == 'create_user'


def test_admin_can_view_global_live_comp_copy_counts(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    csrf = client.get('/api/me').get_json()['csrf_token']
    client.post('/api/live-comps/a-02/copy', headers={'X-CSRF-Token': csrf})
    client.post('/api/live-comps/a-02/copy', headers={'X-CSRF-Token': csrf})
    client.post('/api/live-comps/s-01/copy', headers={'X-CSRF-Token': csrf})

    headers = login_admin(client)
    payload = client.get('/api/admin/live-comps', headers=headers).get_json()

    assert payload['today_copy_count'] == 3
    assert payload['total_copy_count'] == 3
    assert payload['items'] == []
    assert payload['total'] == 0
    assert payload['season']['id'] == 's17-star-god'


def test_admin_live_comps_returns_selected_season_items_with_code_source(client):
    headers = login_admin(client)
    Path = __import__('pathlib').Path
    json_module = __import__('json')
    season_dir = Path(client.application.config['LIVE_COMPS_SEASON_DIR'])
    season_dir.mkdir(parents=True, exist_ok=True)
    payload = sample_live_comps_payload()
    payload['tiers']['S'][0]['jccCode'] = ''
    (season_dir / 's16-legends.json').write_text(json_module.dumps(payload, ensure_ascii=False), encoding='utf-8')

    response = client.get('/api/admin/live-comps?season=s16-legends&page=1&page_size=10', headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data['season']['id'] == 's16-legends'
    assert data['total'] == 1
    assert [item['id'] for item in data['items']] == ['s-01']
    assert data['items'][0]['codeSource'] == 'none'


def test_admin_can_add_manual_code_for_missing_live_comp(client):
    headers = login_admin(client)
    Path = __import__('pathlib').Path
    json_module = __import__('json')
    season_dir = Path(client.application.config['LIVE_COMPS_SEASON_DIR'])
    season_dir.mkdir(parents=True, exist_ok=True)
    payload = sample_live_comps_payload()
    payload['tiers']['S'][0]['jccCode'] = ''
    (season_dir / 's16-legends.json').write_text(json_module.dumps(payload, ensure_ascii=False), encoding='utf-8')

    created = client.post(
        '/api/admin/live-comps/s16-legends/s-01/manual-code',
        json={'code': '【阵容码】##ADMIN001'},
        headers=headers,
    )
    listed = client.get('/api/admin/live-comps?season=s16-legends&page=1&page_size=10', headers=headers)

    assert created.status_code == 200
    assert created.get_json()['resolvedJccCode'] == '#ADMIN001'
    listed_payload = listed.get_json()
    assert listed_payload['items'] == []
    assert listed_payload['total'] == 0


def test_admin_rejects_manual_code_for_live_comp_that_already_has_original_code(client):
    headers = login_admin(client)
    write_live_comps_seed(client, sample_live_comps_payload())

    response = client.post(
        '/api/admin/live-comps/s17-star-god/s-01/manual-code',
        json={'code': '【阵容码】##SHOULDFAIL'},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == '当前条目已有原始阵容码，无需补码'
