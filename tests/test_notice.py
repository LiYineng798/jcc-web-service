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
