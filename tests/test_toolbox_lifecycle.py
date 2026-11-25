from test_admin import login_admin


def test_toolbox_admin_requires_admin(client):
    assert client.get('/api/admin/toolbox').status_code in (401, 403)
    assert client.patch('/api/admin/toolbox/golden-egg', json={'status': 'disabled'}).status_code in (401, 403)


def test_toolbox_lifecycle_status_guards_and_sitemap(client):
    # Default: golden-egg is visible, S8 special-mechanics is unlisted (direct URL ok, not in menu/sitemap)
    home = client.get('/').get_data(as_text=True)
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
    assert data['counts']['visible'] == 9
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
    order_res = client.post('/api/admin/toolbox/reorder', json={'items': reordered}, headers=headers)
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
