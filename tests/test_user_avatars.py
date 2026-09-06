import sqlite3

import pytest

from avatar_service import AVATAR_COLORS
from db import get_db
from db_migrations import migrate_user_avatars
from test_auth import register_user


def test_registration_assigns_persistent_system_avatar(client):
    response = register_user(client).get_json()
    color = response['user']['avatar_color']
    assert color in AVATAR_COLORS
    assert client.get('/api/me').get_json()['user']['avatar_color'] == color
    client.post('/api/logout')
    assert client.get('/api/me').get_json()['user'] is None
    result = client.post('/api/login', json={'account': 'alice', 'password': 'abc123'}).get_json()
    assert result['user']['avatar_color'] == color


def test_avatar_save_updates_only_self_and_public_lineup_payloads(client):
    data = register_user(client).get_json()
    headers = {'X-CSRF-Token': data['csrf_token']}
    lineup = client.post('/api/lineups', headers=headers, json={'name': '头像测试', 'code': '#AVATARTEST001', 'season_id': 's17-star-god'})
    assert lineup.status_code == 201
    # Warm the public list cache, then verify color mutation invalidates it.
    guest = client.application.test_client()
    guest.get('/api/lineups')
    response = client.put('/api/me/avatar', headers=headers, json={'color': '#AABBCC'})
    assert response.status_code == 200
    assert response.get_json()['user']['avatar_color'] == '#aabbcc'
    author = guest.get('/api/authors/alice').get_json()
    assert author['profile']['avatar_color'] == '#aabbcc'
    assert author['lineups'][0]['owner_avatar_color'] == '#aabbcc'
    result = guest.get('/api/lineups').get_json()
    items = result['items'] if isinstance(result, dict) else result
    assert items[0]['owner_avatar_color'] == '#aabbcc'
    with client.application.app_context():
        admin = get_db().execute("SELECT avatar_color FROM users WHERE role = 'admin'").fetchone()
        assert admin['avatar_color'] != '#aabbcc'


@pytest.mark.parametrize('payload', [{'color': '#fff'}, {'color': 'url(x)'}, {'color': '<svg/>'}, {'color': None}, {'color': 123}, {'color': '#123456', 'user_id': 1}, {'color': '#123456', 'style': 'other'}, [], None])
def test_avatar_rejects_unsupported_input(client, payload):
    data = register_user(client).get_json()
    result = client.put('/api/me/avatar', json=payload, headers={'X-CSRF-Token': data['csrf_token']})
    assert result.status_code == 400
    assert client.get('/api/me').get_json()['user']['avatar_color'] == data['user']['avatar_color']


def test_avatar_requires_session_csrf_and_active_account(client):
    token = client.get('/api/me').get_json()['csrf_token']
    assert client.put('/api/me/avatar', json={'color': '#123456'}, headers={'X-CSRF-Token': token}).status_code == 401
    data = register_user(client).get_json()
    assert client.put('/api/me/avatar', json={'color': '#123456'}).status_code == 403
    with client.application.app_context():
        db = get_db()
        db.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (data['user']['id'],))
        db.commit()
    assert client.put('/api/me/avatar', json={'color': '#123456'}, headers={'X-CSRF-Token': data['csrf_token']}).status_code == 403


def test_legacy_avatar_backfill_is_stable_and_preserves_custom_colors():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY)')
    db.executemany('INSERT INTO users (id) VALUES (?)', [(1,), (2,)])
    migrate_user_avatars(db)
    first = [dict(row) for row in db.execute('SELECT * FROM users')]
    assert all(row['avatar_color'] in AVATAR_COLORS for row in first)
    migrate_user_avatars(db)
    assert first == [dict(row) for row in db.execute('SELECT * FROM users')]
    db.execute("UPDATE users SET avatar_color = '#abcdef' WHERE id = 1")
    migrate_user_avatars(db)
    assert db.execute('SELECT avatar_color FROM users WHERE id = 1').fetchone()[0] == '#abcdef'
