import pytest

from db import get_db
from test_admin import login_admin
from test_automation import create_account, login_bot, PREFIX


def test_reads_and_post_preview_do_not_audit_but_import_does(client, app):
    headers = login_admin(client)
    account = create_account(client, headers, can_import=True, allowed_seasons=['s17-star-god'])
    bot, auth = login_bot(app)
    assert bot.get('/api/admin/notice-targets').status_code == 403
    with app.app_context():
        before = get_db().execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
    for path in ('/me', '/overview', '/lineup-seasons', '/live-seasons', '/lineups?season_id=s17-star-god', '/daily-reports'):
        assert bot.get(PREFIX + path).status_code == 200
    assert bot.head(PREFIX + '/me').status_code == 200
    body = {'season_id': 's17-star-god', 'raw_text': '【阵容码】#测试-审计边界#AUDITBOUNDARY001'}
    assert bot.post(PREFIX + '/lineups/bulk-import/preview', headers=auth, json=body).status_code == 200
    assert bot.post(PREFIX + '/lineups/bulk-import', headers=auth, json={}).status_code == 403
    with app.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0] == before
        assert db.execute('SELECT last_used_at FROM automation_accounts WHERE user_id=?', (account['user_id'],)).fetchone()[0]
    assert bot.post(PREFIX + '/lineups/bulk-import', headers=auth, json=body).status_code == 200
    with app.app_context():
        rows = get_db().execute('SELECT action, actor_user_id FROM audit_logs ORDER BY id').fetchall()
        assert len(rows) == before + 1
        assert rows[-1]['action'] == 'admin_bulk_import_lineups'
        assert rows[-1]['actor_user_id'] == account['user_id']


def test_target_catalog_requires_admin_and_follows_toolbox(client, app, monkeypatch):
    assert client.get('/api/admin/notice-targets').status_code == 401
    headers = login_admin(client)
    response = client.get('/api/admin/notice-targets')
    assert response.headers['Cache-Control'] == 'private, no-store'
    tools = response.get_json()['tools']
    page = client.get('/').get_data(as_text=True)
    assert {'lineup-simulator', 'orange-fortune'} <= {tool['id'] for tool in tools}
    assert all(f'href="{tool["url"]}"' in page for tool in tools)
    assert client.put('/api/admin/settings', headers=headers, json={'simulator_enabled': False}).status_code == 200
    assert 'lineup-simulator' not in [t['id'] for t in client.get('/api/admin/notice-targets').get_json()['tools']]
    import toolbox_service
    monkeypatch.setattr(toolbox_service, 'TOOLBOX_TOOLS', (
        dict(id='future-tool', title='新增工具', description='新功能', group='新赛季'),
        dict(id='hidden-tool', title='隐藏工具', description='', group='', visible=False),
    ))
    assert [t['id'] for t in client.get('/api/admin/notice-targets').get_json()['tools']] == ['future-tool']
    page = client.get('/').get_data(as_text=True)
    assert '/tools/future-tool' in page
    assert '/tools/hidden-tool' not in page


def test_tool_notice_clears_stale_targets_and_hides_unavailable_link(client):
    headers = login_admin(client)
    response = client.post('/api/admin/notices', headers=headers, json={
        'title': '模拟器更新', 'message': '立即体验', 'target_kind': 'tool', 'tool_id': 'lineup-simulator',
        'jump_season_id': 's17-star-god', 'jump_tab': 'live', 'link_url': 'https://example.com',
    })
    assert response.status_code == 201
    notice = response.get_json()
    assert notice['link_url'] == '/tools/lineup-simulator'
    assert notice['link_text'] == '打开阵容模拟器'
    assert notice['jump_season_id'] == notice['jump_tab'] == ''
    assert notice['marquee_enabled'] is True
    url = f'/api/admin/notices/{notice["id"]}'
    assert client.post(url + '/activate', headers=headers).status_code == 200
    assert 'href="/tools/lineup-simulator"' in client.get('/').get_data(as_text=True)
    client.put('/api/admin/settings', headers=headers, json={'simulator_enabled': False})
    public = client.get('/api/site-config').get_json()['notice']
    assert public['title'] == '模拟器更新'
    assert public['link_url'] == public['link_text'] == ''
    assert client.get('/api/admin/notice').get_json()['items'][0]['target']['available'] is False
    assert client.post(url + '/activate', headers=headers).status_code == 400
    assert client.put(url, headers=headers, json={'target_kind': 'tool', 'tool_id': 'lineup-simulator'}).status_code == 400
    client.put('/api/admin/settings', headers=headers, json={'simulator_enabled': True})
    assert client.get('/api/site-config').get_json()['notice']['link_url'] == '/tools/lineup-simulator'
    updated = client.put(url, headers=headers, json={'target_kind': 'none'}).get_json()
    assert updated['link_url'] == updated['link_text'] == updated['jump_tab'] == ''


@pytest.mark.parametrize('url', ['javascript:alert(1)', '//example.com', '/\\example.com', 'data:text/html,hello', 'https://', '/path\nnext'])
def test_unsafe_notice_links_are_rejected(client, url):
    headers = login_admin(client)
    response = client.post('/api/admin/notices', headers=headers, json={
        'title': '通知', 'message': '内容', 'target_kind': 'custom', 'link_url': url,
    })
    assert response.status_code == 400


def test_lineup_target_requires_complete_selection_and_preserves_static_mode(client):
    headers = login_admin(client)
    body = dict(title='榜单', message='更新', target_kind='lineup', jump_season_id='s17-star-god', marquee_enabled=False)
    assert client.post('/api/admin/notices', headers=headers, json=body).status_code == 400
    response = client.post('/api/admin/notices', headers=headers, json={**body, 'jump_tab': 'live', 'link_url': '/tools/golden-egg'})
    assert response.status_code == 201
    notice = response.get_json()
    assert notice['marquee_enabled'] is False
    assert notice['link_url'] == ''
    assert notice['link_text'] == '查看阵容'
    response = client.put(f'/api/admin/notices/{notice["id"]}', headers=headers, json={'message': '再次更新'})
    assert response.get_json()['marquee_enabled'] is False
