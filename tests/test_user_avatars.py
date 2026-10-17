import sqlite3

import pytest

from avatar_service import AVATAR_COLORS, AVATAR_PRESETS, AVATAR_EXPRESSIONS, avatar_config
from db import get_db
from db_migrations import migrate_user_avatars
from test_auth import register_user


def test_registration_assigns_persistent_system_avatar(client):
    response = register_user(client).get_json()
    color = response['user']['avatar_color']
    assert color in AVATAR_COLORS
    config = response['user']['avatar_config']
    assert config == {
        'version': 1, 'preset': config['preset'], 'expression': config['expression'], 'color': color,
    }
    assert config['preset'] in AVATAR_PRESETS
    assert config['expression'] in AVATAR_EXPRESSIONS
    assert client.get('/api/me').get_json()['user']['avatar_config'] == config
    assert client.get('/api/me').get_json()['user']['avatar_color'] == color
    client.post('/api/logout')
    assert client.get('/api/me').get_json()['user'] is None
    result = client.post('/api/login', json={'account': 'alice', 'password': 'abc123'}).get_json()
    assert result['user']['avatar_color'] == color
    assert result['user']['avatar_config'] == config
    with client.application.app_context():
        row = get_db().execute('SELECT * FROM users WHERE id = ?', (result['user']['id'],)).fetchone()
        assert avatar_config(row) == config


def test_avatar_save_updates_only_self_and_public_lineup_payloads(client):
    data = register_user(client).get_json()
    headers = {'X-CSRF-Token': data['csrf_token']}
    lineup = client.post('/api/lineups', headers=headers, json={'name': '头像测试', 'code': '#AVATARTEST001', 'season_id': 's17-star-god'})
    assert lineup.status_code == 201
    # Warm the public list cache, then verify color mutation invalidates it.
    guest = client.application.test_client()
    guest.get('/api/lineups')
    config = {'version': 1, 'color': '#aabbcc', 'preset': 'nova', 'expression': 'sleepy'}
    response = client.put('/api/me/avatar', headers=headers, json={'color': '#AABBCC', 'preset': 'nova', 'expression': 'sleepy'})
    assert response.status_code == 200
    assert response.get_json()['user']['avatar_config'] == config
    assert response.get_json()['user']['avatar_color'] == '#aabbcc'
    author = guest.get('/api/authors/alice').get_json()
    assert author['profile']['avatar_color'] == '#aabbcc'
    assert author['lineups'][0]['owner_avatar_color'] == '#aabbcc'
    result = guest.get('/api/lineups').get_json()
    items = result['items'] if isinstance(result, dict) else result
    assert items[0]['owner_avatar_color'] == '#aabbcc'
    assert items[0]['owner_avatar_config'] == config
    assert author['profile']['avatar_config'] == config
    assert author['lineups'][0]['owner_avatar_config'] == config
    lineup_id = lineup.get_json()['id']
    assert guest.get(f'/api/lineups/{lineup_id}').get_json()['owner_avatar_config'] == config
    with client.application.app_context():
        from history import record_recent_view, record_recent_copy, list_recent_views, list_recent_copies
        user = get_db().execute('SELECT * FROM users WHERE id = ?', (data['user']['id'],)).fetchone()
        record_recent_view(user['id'], lineup_id)
        record_recent_copy(user['id'], lineup_id)
        assert list_recent_views(user['id'], user=user)[0]['owner_avatar_config'] == config
        assert list_recent_copies(user['id'], user=user)[0]['owner_avatar_config'] == config
        admin = get_db().execute("SELECT * FROM users WHERE role = 'admin'").fetchone()
        assert admin['avatar_color'] != '#aabbcc'
        assert admin['avatar_preset'] in AVATAR_PRESETS
        assert admin['avatar_expression'] in AVATAR_EXPRESSIONS
    client.post('/api/logout')
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    admin_items = client.get('/api/admin/lineups').get_json()['items']
    assert next(item for item in admin_items if item['id'] == lineup_id)['owner_avatar_config'] == config


@pytest.mark.parametrize('payload', [
    {'color': '#fff'}, {'color': 'url(x)'}, {'color': '<svg/>'}, {'color': None}, {'color': 123},
    {'color': '#123456', 'user_id': 1}, {'color': '#123456', 'style': 'other'}, [], None,
    {'color': '#123456', 'preset': 'nova'}, {'color': '#123456', 'expression': 'happy'},
    {'color': '#123456', 'preset': 'Nova', 'expression': 'happy'},
    {'color': '#123456', 'preset': 'nova', 'expression': 'smile'},
    {'color': '#123456', 'preset': ['nova'], 'expression': 'happy'},
    {'color': '#123456', 'preset': 'nova', 'expression': None},
    {'color': '#123456', 'preset': 'nova', 'expression': 'wink', 'version': 1},
    {'color': '#123456', 'preset': 'nova', 'expression': 'wink', 'svg': '<svg/>'},
    {'color': '#123456', 'preset': 'nova', 'expression': 'wink', 'url': 'https://example.com'},
    {'color': '#123456\n'},
])
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
    assert all(row['avatar_preset'] in AVATAR_PRESETS and row['avatar_expression'] in AVATAR_EXPRESSIONS for row in first)
    db.execute('INSERT INTO users (id) VALUES (3)')
    defaults = db.execute('SELECT * FROM users WHERE id = 3').fetchone()
    assert defaults['avatar_preset'] == 'strobi'
    assert defaults['avatar_expression'] == 'neutral'
    for column in ('avatar_preset', 'avatar_expression'):
        for value in (None, 'invalid'):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(f'UPDATE users SET {column} = ? WHERE id = 1', (value,))


def test_legacy_color_only_save_preserves_persisted_parameters(client):
    data = register_user(client).get_json()
    headers = {'X-CSRF-Token': data['csrf_token']}
    config = {'version': 1, 'preset': 'citrus', 'expression': 'wink', 'color': '#abcdef'}
    assert client.put('/api/me/avatar', headers=headers, json={key: value for key, value in config.items() if key != 'version'}).status_code == 200
    response = client.put('/api/me/avatar', headers=headers, json={'color': '#123ABC'})
    assert response.get_json()['user']['avatar_config'] == {**config, 'color': '#123abc'}


@pytest.mark.parametrize('preset', AVATAR_PRESETS)
@pytest.mark.parametrize('expression', AVATAR_EXPRESSIONS)
def test_avatar_accepts_all_bounded_combinations(client, preset, expression):
    data = register_user(client).get_json()
    response = client.put('/api/me/avatar', headers={'X-CSRF-Token': data['csrf_token']},
                          json={'color': '#012aEF', 'preset': preset, 'expression': expression})
    assert response.status_code == 200
    assert response.get_json()['user']['avatar_config'] == {
        'version': 1, 'color': '#012aef', 'preset': preset, 'expression': expression,
    }


def test_partial_avatar_backfill_only_changes_null_fields():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, avatar_color TEXT, avatar_preset TEXT, avatar_expression TEXT)')
    db.execute("INSERT INTO users VALUES (1, '#ABCDEF', 'nova', NULL)")
    db.execute("INSERT INTO users VALUES (2, '#123456', NULL, 'wink')")
    migrate_user_avatars(db)
    rows = [dict(row) for row in db.execute('SELECT * FROM users ORDER BY id')]
    assert rows[0]['avatar_color'] == '#ABCDEF'
    assert rows[0]['avatar_preset'] == 'nova'
    assert rows[0]['avatar_expression'] in AVATAR_EXPRESSIONS
    assert rows[1]['avatar_color'] == '#123456'
    assert rows[1]['avatar_preset'] in AVATAR_PRESETS
    assert rows[1]['avatar_expression'] == 'wink'
    migrate_user_avatars(db)
    assert rows == [dict(row) for row in db.execute('SELECT * FROM users ORDER BY id')]


def test_invalid_or_missing_storage_fallback_is_stable(monkeypatch):
    def forbid_random(*args):
        raise AssertionError('reading avatars must not randomize')
    monkeypatch.setattr('avatar_service.secrets.choice', forbid_random)
    for user in (None, {'id': 7}, {'id': 3, 'avatar_color': '<svg/>', 'avatar_preset': 'other', 'avatar_expression': None}):
        first = avatar_config(user)
        assert first == avatar_config(user)
        assert first['preset'] in AVATAR_PRESETS
        assert first['expression'] in AVATAR_EXPRESSIONS
        assert first['color'] in AVATAR_COLORS


def test_all_user_creation_paths_randomize_complete_avatar_once(client, app, monkeypatch):
    from admin_user_service import create_user
    from db import bootstrap_admin
    calls = []
    expected = {'version': 1, 'preset': 'freddy', 'expression': 'wink', 'color': '#059669'}
    def generate():
        calls.append(True)
        return expected.copy()
    monkeypatch.setattr('auth.random_avatar_config', generate)
    assert register_user(client).get_json()['user']['avatar_config'] == expected
    assert len(calls) == 1
    monkeypatch.setattr('admin_user_service.random_avatar_config', generate)
    with app.app_context():
        db = get_db()
        payload, error, status = create_user(db, 1, {'username': 'created', 'email': 'created@example.com', 'password': 'abc123'})
        assert error is None and status == 201
        assert avatar_config(db.execute('SELECT * FROM users WHERE id = ?', (payload['id'],)).fetchone()) == expected
        assert len(calls) == 2
        monkeypatch.setattr('avatar_service.random_avatar_config', generate)
        app.config['ADMIN_USERNAME'] = 'newbootstrap'
        admin_id = bootstrap_admin(db)
        assert avatar_config(db.execute('SELECT * FROM users WHERE id = ?', (admin_id,)).fetchone()) == expected
        assert len(calls) == 3
        assert bootstrap_admin(db) == admin_id
        assert len(calls) == 3


def test_author_and_history_lists_do_not_query_per_avatar(client, app):
    from history import record_recent_view, list_recent_views
    from lineup_account_service import build_author_profile_payload
    data = register_user(client).get_json()
    headers = {'X-CSRF-Token': data['csrf_token']}
    lineup_ids = []
    for index in range(3):
        response = client.post('/api/lineups', headers=headers, json={
            'name': f'avatar {index}', 'code': f'#AVATAR{index}001', 'season_id': 's17-star-god',
        })
        assert response.status_code == 201
        lineup_ids.append(response.get_json()['id'])
    with app.app_context():
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id = ?', (data['user']['id'],)).fetchone()
        for lineup_id in lineup_ids:
            record_recent_view(user['id'], lineup_id)
        queries = []
        db.connection.set_trace_callback(queries.append)
        try:
            profile, error, _ = build_author_profile_payload('alice', user, {})
            assert error is None and len(profile['lineups']) == 3
            # One author lookup and one joined lineup query, no per-row SELECTs.
            assert len([sql for sql in queries if sql.lstrip().upper().startswith('SELECT')]) == 2
            queries.clear()
            rows = list_recent_views(user['id'], user=user)
            assert len(rows) == 3
            assert not any('FROM users WHERE id =' in sql for sql in queries)
            assert not any('SELECT id FROM likes' in sql or 'SELECT id FROM favorites' in sql for sql in queries)
            assert all(row['owner_avatar_config'] == data['user']['avatar_config'] for row in rows)
        finally:
            db.connection.set_trace_callback(None)


def test_sqlite_init_upgrades_legacy_users_before_bootstrap(tmp_path):
    from flask import Flask
    from db import init_db, close_db
    from db_schema import SCHEMA

    path = tmp_path / 'legacy.sqlite3'
    legacy_schema = '\n'.join(line for line in SCHEMA.splitlines() if 'avatar_' not in line)
    with sqlite3.connect(path) as connection:
        connection.executescript(legacy_schema)
        connection.execute("""INSERT INTO users
            (username, email, nickname, password_hash, role, status, created_at, updated_at)
            VALUES ('old', 'old@example.com', 'Old', 'unused', 'user', 'active', '2026-01-01', '2026-01-01')""")
    app = Flask(__name__)
    app.config.update(DATABASE=str(path), DATABASE_URL='sqlite:///' + str(path),
                      ADMIN_USERNAME='newadmin', ADMIN_PASSWORD='Test1234')
    with app.app_context():
        try:
            init_db()
            db = get_db()
            rows = [dict(row) for row in db.execute('SELECT * FROM users ORDER BY id')]
            assert len(rows) == 2
            assert rows[1]['username'] == 'newadmin'
            for row in rows:
                assert row['avatar_color'] in AVATAR_COLORS
                assert row['avatar_preset'] in AVATAR_PRESETS
                assert row['avatar_expression'] in AVATAR_EXPRESSIONS
            init_db()
            assert rows == [dict(row) for row in db.execute('SELECT * FROM users ORDER BY id')]
        finally:
            close_db()


def test_four_hundred_existing_avatars_keep_colors_and_stable_assignments():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, avatar_color TEXT NOT NULL)')
    originals = [(index, f'#{index:06x}') for index in range(1, 401)]
    db.executemany('INSERT INTO users VALUES (?, ?)', originals)
    migrate_user_avatars(db)
    first = [dict(row) for row in db.execute('SELECT * FROM users ORDER BY id')]
    assert [(row['id'], row['avatar_color']) for row in first] == originals
    assert all(row['avatar_preset'] in AVATAR_PRESETS and row['avatar_expression'] in AVATAR_EXPRESSIONS for row in first)
    migrate_user_avatars(db)
    assert first == [dict(row) for row in db.execute('SELECT * FROM users ORDER BY id')]
    db.close()


def test_existing_four_preset_schema_expands_without_changing_users_or_relations():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript("""CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT,
        avatar_color TEXT NOT NULL,
        avatar_preset TEXT NOT NULL DEFAULT 'strobi' CHECK (avatar_preset IN ('strobi','freddy','citrus','nova')),
        avatar_expression TEXT NOT NULL DEFAULT 'neutral' CHECK (avatar_expression IN ('neutral','happy','wink','sleepy'))
    );
    CREATE TABLE children (user_id INTEGER REFERENCES users(id) ON DELETE CASCADE);
    CREATE INDEX users_name_lookup ON users(username);
    INSERT INTO users VALUES (42, 'existing', 'unchanged-hash', '#0021ed', 'freddy', 'wink');
    INSERT INTO children VALUES (42);
    """)
    original = dict(db.execute('SELECT * FROM users').fetchone())
    migrate_user_avatars(db)
    assert dict(db.execute('SELECT * FROM users').fetchone()) == original
    assert db.execute('SELECT user_id FROM children').fetchone()[0] == 42
    assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    assert db.execute("SELECT name FROM sqlite_master WHERE name='users_name_lookup'").fetchone()
    for preset in AVATAR_PRESETS:
        db.execute('UPDATE users SET avatar_preset=?', (preset,))
    for expression in AVATAR_EXPRESSIONS:
        db.execute('UPDATE users SET avatar_expression=?', (expression,))
    db.execute("UPDATE users SET avatar_preset='sunee', avatar_expression='curious'")
    schema = db.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
    migrate_user_avatars(db)
    assert db.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0] == schema
    assert db.execute('SELECT avatar_preset FROM users').fetchone()[0] == 'sunee'
    assert db.execute('SELECT avatar_expression FROM users').fetchone()[0] == 'curious'
    for invalid in ('unknown', None):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('UPDATE users SET avatar_expression=?', (invalid,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE users SET avatar_preset='unknown'")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('UPDATE users SET avatar_preset=NULL')
    db.execute("INSERT INTO users (username,avatar_color) VALUES ('new','#7e927d')")
    assert db.execute("SELECT id FROM users WHERE username='new'").fetchone()[0] == 43
    db.close()


@pytest.mark.parametrize('column,choices', [
    ('avatar_preset', AVATAR_PRESETS), ('avatar_expression', AVATAR_EXPRESSIONS),
])
def test_avatar_constraint_expansion_rolls_back_on_failure(column, choices):
    from db_migrations import expand_avatar_constraint
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    allowed = ','.join(f"'{value}'" for value in choices[:4])
    db.execute(f'CREATE TABLE users (id INTEGER PRIMARY KEY, {column} TEXT CHECK ({column} IN ({allowed})))')
    db.execute(f'INSERT INTO users VALUES (1, ?)', (choices[3],))
    before = db.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]

    class InterruptedConnection:
        def execute(self, sql, *args):
            if sql == f'ALTER TABLE users DROP COLUMN {column}':
                raise sqlite3.OperationalError('simulated interruption')
            return db.execute(sql, *args)

    with pytest.raises(sqlite3.OperationalError, match='simulated interruption'):
        expand_avatar_constraint(InterruptedConnection(), column, choices)
    assert db.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0] == before
    assert dict(db.execute('SELECT * FROM users').fetchone()) == {'id': 1, column: choices[3]}
    db.close()
