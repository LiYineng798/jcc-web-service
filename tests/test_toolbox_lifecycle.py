from html import unescape
import re

from db import get_db
from test_admin import login_admin


def test_toolbox_admin_requires_admin(client):
    assert client.get('/api/admin/toolbox').status_code in (401, 403)
    assert client.patch('/api/admin/toolbox/golden-egg', json={'status': 'disabled'}).status_code in (401, 403)


def test_toolbox_lifecycle_status_guards_and_sitemap(client):
    # Default: golden-egg is visible, S8 special-mechanics is unlisted (direct URL ok, not in menu/sitemap)
    home = client.get('/').get_data(as_text=True)
    assert '/tools/s19-smeech' in home
    assert client.get('/tools/s19-smeech').status_code == 200
    assert '/tools/golden-egg' in home
    assert '/tools/special-mechanics' not in home
    assert client.get('/tools/golden-egg').status_code == 200
    s8_resp = client.get('/tools/special-mechanics')
    assert s8_resp.status_code == 200
    assert 'noindex' in s8_resp.get_data(as_text=True)

    sitemap = client.get('/sitemap.xml').get_data(as_text=True)
    assert '/tools/golden-egg' in sitemap
    assert '/tools/special-mechanics' not in sitemap

    headers = login_admin(client)

    # 1. Switch golden-egg to unlisted
    res = client.patch('/api/admin/toolbox/golden-egg', json={'status': 'unlisted'}, headers=headers)
    assert res.status_code == 200
    assert res.get_json()['item']['status'] == 'unlisted'

    assert '/tools/golden-egg' not in client.get('/').get_data(as_text=True)
    assert '/tools/golden-egg' not in client.get('/sitemap.xml').get_data(as_text=True)
    egg_unlisted = client.get('/tools/golden-egg')
    assert egg_unlisted.status_code == 200
    assert 'noindex' in egg_unlisted.get_data(as_text=True)

    # 2. Switch golden-egg to disabled
    res = client.patch('/api/admin/toolbox/golden-egg', json={'status': 'disabled'}, headers=headers)
    assert res.status_code == 200
    # Admin preview works with ?preview=1
    preview = client.get('/tools/golden-egg?preview=1')
    assert preview.status_code == 200
    assert preview.headers.get('X-Robots-Tag') == 'noindex'
    # Without preview, disabled returns 404
    assert client.get('/tools/golden-egg').status_code == 404

    # Logout: anonymous user cannot preview disabled tool
    assert client.post('/api/logout', headers=headers).status_code == 200
    assert client.get('/tools/golden-egg').status_code == 404
    assert client.get('/tools/golden-egg?preview=1').status_code == 404


def test_toolbox_metadata_reorder_and_reset(client):
    headers = login_admin(client)

    listing = client.get('/api/admin/toolbox')
    assert listing.status_code == 200
    data = listing.get_json()
    assert data['counts']['visible'] == 10
    assert data['counts']['unlisted'] == 3

    # Update title, group, description
    res = client.patch(
        '/api/admin/toolbox/golden-egg',
        json={'title': '金蛋掉落表', 'group': '测试分组', 'description': '自定义简介'},
        headers=headers,
    )
    assert res.status_code == 200
    item = res.get_json()['item']
    assert item['title'] == '金蛋掉落表'
    assert item['group'] == '测试分组'
    assert item['customized'] is True

    home = client.get('/').get_data(as_text=True)
    assert '金蛋掉落表' in home
    assert '测试分组' in home

    # Reorder: move golden-egg into a new group and s11-items into the blank group ''
    ids = [row['id'] for row in data['items']]
    reordered = [
        {'id': 'golden-egg', 'group': '新赛季工具'},
        {'id': 's11-items', 'group': ''},
        *[{'id': i} for i in ids if i not in ('golden-egg', 's11-items')],
    ]
    order_url = '/api/admin/toolbox/reorder'
    def order_snapshot(rows):
        return [{'id': row['id'], 'group': row['group']} for row in rows]

    assert client.post(order_url, json={'items': reordered}, headers=headers).status_code == 409
    stale = {'items': reordered, 'expected_order': order_snapshot(data['items'])}
    assert client.post(order_url, json=stale, headers=headers).status_code == 409
    latest = client.get('/api/admin/toolbox').json['items']
    assert next(row['group'] for row in latest if row['id'] == 'golden-egg') == '测试分组'
    order_res = client.post(order_url, json={'items': reordered, 'expected_order': order_snapshot(latest)}, headers=headers)
    assert order_res.status_code == 200
    reordered_items = order_res.get_json()['items']
    assert reordered_items[0]['id'] == 'golden-egg'
    assert reordered_items[0]['group'] == '新赛季工具'
    assert reordered_items[1]['id'] == 's11-items'
    assert reordered_items[1]['group'] == ''

    # Reset golden-egg back to defaults
    reset_res = client.post('/api/admin/toolbox/golden-egg/reset', headers=headers)
    assert reset_res.status_code == 200
    restored = reset_res.get_json()['item']
    assert restored['title'] == '金蛋奖励'
    assert restored['customized'] is False


def test_tool_update_requires_csrf_for_admin(client):
    login_admin(client)
    url = '/api/admin/toolbox/golden-egg'
    assert client.patch(url, json={'status': 'disabled'}).status_code == 403
    assert client.get('/tools/golden-egg').status_code == 200


def test_public_group_links_stay_together_after_metadata_edit(client, app):
    from toolbox_service import list_toolbox_tools

    headers = login_admin(client)
    group = 'S11 · 画之灵'
    result = client.patch('/api/admin/toolbox/golden-egg', json={'group': group}, headers=headers)
    assert result.status_code == 200
    with app.app_context():
        tools = list_toolbox_tools()
    indexes = [i for i, tool in enumerate(tools) if tool['group'] == group]
    assert len(indexes) == 3
    assert indexes == list(range(indexes[0], indexes[0] + 3))


def test_simulator_global_switch_sets_admin_counts_and_preview(client, app):
    login_admin(client)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE app_settings SET setting_value='false' WHERE setting_key='simulator_enabled'")
        db.commit()
    data = client.get('/api/admin/toolbox').json
    sim = next(item for item in data['items'] if item['id'] == 'lineup-simulator')
    assert sim['status'] == 'visible' and sim['effective_status'] == 'disabled'
    assert data['counts']['visible'] == 9 and data['counts']['disabled'] == 1
    assert client.get(sim['url']).status_code == 404
    assert client.get(sim['url'] + '?preview=1').status_code == 200


def test_disabled_tool_preview_links_and_search_forms(client):
    headers = login_admin(client)
    for tool_id in ('s18-witch-rewards', 's11-artifacts', 'orange-fortune', 'orange-fortune-creator'):
        assert client.patch('/api/admin/toolbox/' + tool_id, json={'status': 'disabled'}, headers=headers).status_code == 200
        page = client.get('/tools/' + tool_id + '?preview=1&deck=123')
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        links = [unescape(value) for value in re.findall(r'href="([^"]+)"', html)
                 if value.split('?')[0] == '/tools/' + tool_id]
        assert links and all('preview=1' in url for url in links)
        assert client.get(links[0]).status_code == 200
        if tool_id in ('s11-artifacts', 'orange-fortune'):
            assert 'type="hidden" name="preview" value="1"' in html
