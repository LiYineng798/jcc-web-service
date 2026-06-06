from lineup_write_service import (
    create_lineup_record,
    delete_lineup_record,
    hide_lineup_record,
    update_lineup_record,
)
from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_create_lineup_record_creates_owned_lineup(client):
    register_user(client, nickname='小明')
    user = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload, error, status_code = create_lineup_record(
            user=user,
            data={'name': '阵容A', 'code': '#CODE123', 'status': 'normal', 'season_id': 's17-star-god'},
        )

    assert error is None
    assert status_code == 201
    assert payload['owner_nickname'] == '小明'
    assert payload['can_edit'] is True
    assert payload['can_hide'] is True


def test_update_lineup_record_rejects_stale_version(client):
    register_user(client)
    user = client.get('/api/me').get_json()['user']
    lineup = create_lineup(client).get_json()

    with client.application.app_context():
        payload, error, status_code = update_lineup_record(
            user=user,
            lineup_id=lineup['id'],
            data={'name': lineup['name'], 'code': lineup['code'], 'version': lineup['version'] + 1},
        )

    assert payload is None
    assert status_code == 409
    assert error == '阵容已被更新，请刷新后重试'


def test_delete_lineup_record_rejects_other_user(client):
    register_user(client, username='a', email='a@example.com')
    lineup = create_lineup(client).get_json()
    client.post('/api/logout')
    register_user(client, username='b', email='b@example.com')
    user = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload, error, status_code = delete_lineup_record(user=user, lineup_id=lineup['id'])

    assert payload is None
    assert status_code == 403
    assert error == '无权删除该阵容'


def test_hide_lineup_record_hides_owner_lineup(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='我的可隐藏阵容', code='#HIDEOWN1').get_json()
    user = client.get('/api/me').get_json()['user']

    with client.application.app_context():
        payload, error, status_code = hide_lineup_record(user=user, lineup_id=lineup['id'])

    assert error is None
    assert status_code == 200
    assert payload == {'ok': True}
