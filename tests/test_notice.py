from test_admin import login_admin


def test_notice_defaults_disabled(client):
    """Default state: no notice, site-config returns None."""
    config = client.get('/api/site-config').get_json()
    assert config['notice'] is None


def test_admin_can_get_notice(client):
    headers = login_admin(client)
    data = client.get('/api/admin/notice', headers=headers).get_json()
    assert data['enabled'] is False
    assert data['title'] == ''
    assert data['message'] == ''


def test_admin_can_save_and_enable_notice(client):
    headers = login_admin(client)

    resp = client.put('/api/admin/notice', json={
        'enabled': True,
        'title': 'S8即将返场',
        'message': '阵容码将在第一时间更新',
        'link_url': '/tools/lineup-simulator',
        'link_text': '查看模拟器',
    }, headers=headers)
    assert resp.status_code == 200

    data = client.get('/api/admin/notice', headers=headers).get_json()
    assert data['enabled'] is True
    assert data['title'] == 'S8即将返场'
    assert data['message'] == '阵容码将在第一时间更新'
    assert data['link_url'] == '/tools/lineup-simulator'
    assert data['link_text'] == '查看模拟器'

    client.put('/api/admin/notice', json={
        'enabled': False,
        'title': '',
        'message': '',
    }, headers=headers)


def test_admin_can_manage_multiple_notices_and_select_one(client):
    headers = login_admin(client)

    first = client.post('/api/admin/notices', json={
        'title': '第一条公告',
        'message': '第一条内容',
        'link_url': '/patch-notes',
        'link_text': '查看公告',
    }, headers=headers)
    assert first.status_code == 201

    second = client.post('/api/admin/notices', json={
        'title': '第二条公告',
        'message': '第二条内容',
    }, headers=headers)
    assert second.status_code == 201

    first_id = first.get_json()['id']
    second_id = second.get_json()['id']

    listing = client.get('/api/admin/notice', headers=headers).get_json()
    assert listing['enabled'] is False
    assert [item['title'] for item in listing['items']] == ['第二条公告', '第一条公告']
    assert all(item['is_active'] is False for item in listing['items'])

    activate = client.post(f'/api/admin/notices/{first_id}/activate', headers=headers)
    assert activate.status_code == 200

    listing = client.get('/api/admin/notice', headers=headers).get_json()
    assert listing['enabled'] is True
    active_items = [item for item in listing['items'] if item['is_active']]
    assert len(active_items) == 1
    assert active_items[0]['id'] == first_id
    assert listing['title'] == '第一条公告'
    assert listing['message'] == '第一条内容'

    activate = client.post(f'/api/admin/notices/{second_id}/activate', headers=headers)
    assert activate.status_code == 200

    listing = client.get('/api/admin/notice', headers=headers).get_json()
    active_items = [item for item in listing['items'] if item['is_active']]
    assert len(active_items) == 1
    assert active_items[0]['id'] == second_id

    config = client.get('/api/site-config').get_json()
    assert config['notice']['title'] == '第二条公告'


def test_admin_can_disable_notice_without_deleting_saved_notices(client):
    headers = login_admin(client)

    created = client.post('/api/admin/notices', json={
        'title': '保留公告',
        'message': '关闭展示后还在列表里',
    }, headers=headers)
    notice_id = created.get_json()['id']
    client.post(f'/api/admin/notices/{notice_id}/activate', headers=headers)

    resp = client.put('/api/admin/notice', json={'enabled': False}, headers=headers)
    assert resp.status_code == 200

    config = client.get('/api/site-config').get_json()
    assert config['notice'] is None

    listing = client.get('/api/admin/notice', headers=headers).get_json()
    assert listing['enabled'] is False
    assert len(listing['items']) == 1
    assert listing['items'][0]['title'] == '保留公告'
    assert listing['items'][0]['is_active'] is True


def test_admin_can_update_and_delete_saved_notice(client):
    headers = login_admin(client)

    created = client.post('/api/admin/notices', json={
        'title': '旧标题',
        'message': '旧内容',
    }, headers=headers)
    notice_id = created.get_json()['id']

    updated = client.put(f'/api/admin/notices/{notice_id}', json={
        'title': '新标题',
        'message': '新内容',
        'link_url': '/tools/lineup-simulator',
        'link_text': '打开工具',
    }, headers=headers)
    assert updated.status_code == 200
    assert updated.get_json()['title'] == '新标题'

    listing = client.get('/api/admin/notice', headers=headers).get_json()
    assert listing['items'][0]['title'] == '新标题'
    assert listing['items'][0]['link_text'] == '打开工具'

    deleted = client.delete(f'/api/admin/notices/{notice_id}', headers=headers)
    assert deleted.status_code == 200
    assert client.get('/api/admin/notice', headers=headers).get_json()['items'] == []


def test_legacy_notice_data_is_imported_to_saved_notices(client):
    headers = login_admin(client)

    resp = client.put('/api/admin/notice', json={
        'enabled': True,
        'title': '旧公告',
        'message': '旧内容',
        'link_url': '/patch-notes',
        'link_text': '查看',
    }, headers=headers)
    assert resp.status_code == 200

    listing = client.get('/api/admin/notice', headers=headers).get_json()
    assert len(listing['items']) == 1
    assert listing['items'][0]['title'] == '旧公告'
    assert listing['items'][0]['is_active'] is True


def test_notice_appears_on_index_when_enabled(client):
    headers = login_admin(client)

    client.put('/api/admin/notice', json={
        'enabled': True,
        'title': 'S8即将返场',
        'message': '阵容码将在第一时间更新',
    }, headers=headers)

    html = client.get('/').get_data(as_text=True)
    assert 'site-notice' in html
    assert 'site-notice-title' in html
    assert 'site-notice-marquee' in html
    assert 'site-notice-marquee-track' in html
    assert 'S8即将返场' in html
    assert '阵容码将在第一时间更新' in html
    assert 'siteNoticeClose' in html

    config = client.get('/api/site-config').get_json()
    assert config['notice'] is not None
    assert config['notice']['title'] == 'S8即将返场'

    client.put('/api/admin/notice', json={
        'enabled': False, 'title': '', 'message': '',
    }, headers=headers)


def test_notice_guestbook_link_opens_in_the_current_page():
    with open('templates/index.html', 'r', encoding='utf-8') as file:
        html = file.read()
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        javascript = file.read()

    assert "notice.link_url.startswith('/')" in html
    assert "notice.link_url == '/#guestbook'" in html
    assert "'/#guestbook'" in javascript
    assert 'noticeGuestbookLinkButton' in javascript


def test_guestbook_notice_clears_stale_lineup_jump_and_renders_a_direct_action(client):
    headers = login_admin(client)
    created = client.post('/api/admin/notices', json={
        'title': '反馈入口',
        'message': '欢迎留言',
        'link_url': '/#guestbook',
        'link_text': '去留言',
        'jump_season_id': 's18',
        'jump_tab': 'live',
    }, headers=headers)
    assert created.status_code == 201
    notice = created.get_json()
    assert notice['jump_season_id'] == ''
    assert notice['jump_tab'] == ''

    assert client.post(f"/api/admin/notices/{notice['id']}/activate", headers=headers).status_code == 200
    html = client.get('/').get_data(as_text=True)
    assert 'site-notice-guestbook' in html
    assert 'href="#guestbook"' in html


def test_notice_marquee_styles_bounce_between_visible_edges():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.site-notice-marquee' in css
    assert '.site-notice-marquee-track' in css
    assert 'container-type: inline-size' in css
    assert 'animation: site-notice-marquee-bounce' in css
    assert 'alternate' in css
    assert '@keyframes site-notice-marquee-bounce' in css
    assert 'from { transform: translateX(0); }' in css
    assert 'to { transform: translateX(max(0px, calc(100cqw - 100%))); }' in css


def test_notice_marquee_is_static_and_wrapped_on_small_screens():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    mobile_css = css[css.index('@media (max-width: 640px)'):]
    assert '.site-notice-marquee {' in mobile_css
    assert 'overflow: visible;' in mobile_css
    assert 'white-space: normal;' in mobile_css
    assert '.site-notice-marquee-track {' in mobile_css
    assert 'animation: none;' in mobile_css
    assert 'transform: none;' in mobile_css
    assert 'min-width: 0;' in mobile_css
    assert 'flex-wrap: wrap;' in mobile_css


def test_notice_hidden_when_disabled(client):
    headers = login_admin(client)

    client.put('/api/admin/notice', json={
        'enabled': False, 'title': '', 'message': '',
    }, headers=headers)

    html = client.get('/').get_data(as_text=True)
    assert 'site-notice' not in html

    config = client.get('/api/site-config').get_json()
    assert config['notice'] is None


def test_non_admin_cannot_manage_notice(client):
    from test_auth import register_user

    resp = client.get('/api/admin/notice')
    assert resp.status_code == 401

    register_user(client, username='user2', email='user2@example.com')
    resp = client.get('/api/admin/notice')
    assert resp.status_code == 403

    resp = client.put('/api/admin/notice', json={'enabled': True, 'title': 'x', 'message': 'y'})
    assert resp.status_code == 403
