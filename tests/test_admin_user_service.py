from admin_user_service import build_user_list_query, create_user, prepare_user_update_fields
from db import get_db


def test_build_user_list_query_without_search(app):
    base_sql, count_sql, params = build_user_list_query('')

    with app.app_context():
        db = get_db()
        users = db.execute(base_sql, params).fetchall()
        assert [row['username'] for row in users] == ['adminxlx']
        assert db.execute(count_sql, params).fetchone()['c'] == len(users)
    assert params == []


def test_build_user_list_query_with_search(app):
    base_sql, count_sql, params = build_user_list_query('alice')

    with app.app_context():
        db = get_db()
        _, error, _ = create_user(db, 1, {'username': 'alice', 'email': 'alice@example.com', 'password': 'abc123'})
        assert error is None
        users = db.execute(base_sql, params).fetchall()
        assert [row['username'] for row in users] == ['alice']
        assert db.execute(count_sql, params).fetchone()['c'] == 1
    assert params == ['%alice%', '%alice%', '%alice%']


def test_prepare_user_update_fields_collects_supported_fields():
    data = {'nickname': 'Bobby', 'status': 'disabled'}

    fields, params = prepare_user_update_fields(data)

    assert fields == ['nickname = ?', 'status = ?']
    assert params == ['Bobby', 'disabled']


def test_create_user_uses_returning_id_for_insert(app, monkeypatch):
    captured = {}

    def capture_insert_sql(sql, kind):
        captured['insert_kind'] = kind
        return sql

    def capture_last_insert_id(cursor, kind):
        captured['last_insert_kind'] = kind
        return cursor.lastrowid

    monkeypatch.setattr('admin_user_service.db_kind', lambda: 'postgres')
    monkeypatch.setattr('admin_user_service.insert_returning_id_sql', capture_insert_sql)
    monkeypatch.setattr('admin_user_service.last_insert_id', capture_last_insert_id)

    with app.app_context():
        payload, error, status_code = create_user(
            get_db(),
            1,
            {'username': 'pgadminuser', 'email': 'pgadminuser@example.com', 'password': 'abc123'},
        )

    assert error is None
    assert status_code == 201
    assert payload['id']
    assert captured == {'insert_kind': 'postgres', 'last_insert_kind': 'postgres'}


def test_admin_list_returns_persisted_avatar_color(client, app):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE users SET avatar_color = '#123abc' WHERE username = 'adminxlx'")
        db.commit()
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    response = client.get('/api/admin/users?q=adminxlx')
    assert response.status_code == 200
    user = response.get_json()['items'][0]
    assert user['avatar_color'] == '#123abc'
    assert user['avatar_config']['color'] == '#123abc'
    assert user['avatar_config']['preset'] == user['avatar_preset']
    assert user['avatar_config']['expression'] == user['avatar_expression']
    assert user['avatar_config']['version'] == 1
    assert 'password_hash' not in user
