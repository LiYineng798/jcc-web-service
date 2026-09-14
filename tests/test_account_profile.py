from pathlib import Path

from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_profile_is_private_and_loads_its_built_island_only_on_account(client):
    assert client.get('/me').status_code == 401
    register_user(client)
    html = client.get('/me').get_data(as_text=True)
    assert 'noindex' in html
    for asset in ['account.js', 'account-profile/app.js', 'account-profile/app.css', 'avatar-editor.js']:
        assert f'/static/{asset}?v=' in html
        assert client.get(f'/static/{asset}').status_code == 200
    assert html.index('/static/account.js?v=') < html.index('/static/account-profile/app.js?v=')
    assert 'account-grid' not in html
    assert 'account-profile/app.js' not in client.get('/').get_data(as_text=True)
    assert Path('static/account-profile/THIRD_PARTY_NOTICES.txt').is_file()


def test_profile_pagination_reaches_lineups_after_first_twenty_and_searches(client):
    register_user(client)
    for i in range(23):
        assert create_lineup(client, name=f'个人阵容{i:02}', code=f'#PROFILEPAGE{i:04}').status_code == 201
    pages = [client.get(f'/api/lineups?view=mine&page={page}&page_size=6').get_json() for page in range(1, 5)]
    assert all(page['total'] == 23 for page in pages)
    assert len({item['id'] for page in pages for item in page['items']}) == 23
    match = client.get('/api/lineups?view=mine&page=1&page_size=6&q=个人阵容00').get_json()
    assert match['total'] == 1
    assert match['items'][0]['name'] == '个人阵容00'


def test_preview_login_is_not_registered_in_application(client):
    assert client.get('/__preview/login').status_code == 404
