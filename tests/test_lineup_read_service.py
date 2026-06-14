from lineup_read_service import build_lineup_detail_payload, build_lineups_list_payload
from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_build_lineups_list_payload_returns_paginated_latest_items(client):
    register_user(client, username='a', email='a@example.com')
    for index in range(3):
        create_lineup(client, name=f'阵容{index}', code=f'#CODE{index}')
    user = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload = build_lineups_list_payload(
            user=user,
            view='all',
            sort='latest',
            query='',
            season_id=None,
            wants_page=True,
            page=1,
            page_size=2,
        )

    assert payload['total'] == 3
    assert payload['page'] == 1
    assert payload['page_size'] == 2
    assert len(payload['items']) == 2
    assert payload['items'][0]['name'] == '阵容2'


def test_build_lineups_list_payload_returns_empty_favorites_for_anonymous(client):
    with client.application.app_context():
        payload = build_lineups_list_payload(
            user=None,
            view='favorites',
            sort='latest',
            query='',
            season_id=None,
            wants_page=True,
            page=1,
            page_size=10,
        )

    assert payload == {'items': [], 'total': 0, 'page': 1, 'page_size': 10, 'total_pages': 1}


def test_build_lineup_detail_payload_rejects_hidden_lineup_for_other_user(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='隐藏阵容', code='#HIDDEN01', status='hidden').get_json()
    client.post('/api/logout')
    register_user(client, username='viewer', email='viewer@example.com')
    viewer = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload, error, status_code = build_lineup_detail_payload(lineup['id'], viewer)

    assert payload is None
    assert status_code == 404
    assert error == '阵容不存在'


def test_build_lineups_list_payload_reuses_cached_home_tab_until_data_changes(client, monkeypatch):
    assert register_user(client, username='cache_owner', email='cache_owner@example.com').status_code == 201
    assert create_lineup(client, name='缓存阵容A', code='#CACHE001').status_code == 201
    user = client.get('/api/me').get_json()['user']

    import lineup_read_service

    original_fetch = lineup_read_service.fetch_lineup_rows
    calls = {'count': 0}

    def counting_fetch(*args, **kwargs):
        calls['count'] += 1
        return original_fetch(*args, **kwargs)

    monkeypatch.setattr(lineup_read_service, 'fetch_lineup_rows', counting_fetch)

    with client.application.app_context():
        first = build_lineups_list_payload(
            user=user,
            view='all',
            sort='latest',
            query='',
            season_id=None,
            wants_page=True,
            page=1,
            page_size=10,
        )
        second = build_lineups_list_payload(
            user=user,
            view='all',
            sort='latest',
            query='',
            season_id=None,
            wants_page=True,
            page=1,
            page_size=10,
        )

    assert first == second
    assert calls['count'] == 1

    assert create_lineup(client, name='缓存阵容B', code='#CACHE002').status_code == 201

    with client.application.app_context():
        refreshed = build_lineups_list_payload(
            user=user,
            view='all',
            sort='latest',
            query='',
            season_id=None,
            wants_page=True,
            page=1,
            page_size=10,
        )

    assert refreshed['total'] == 2
    assert calls['count'] == 2
