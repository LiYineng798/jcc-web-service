from admin_user_service import build_user_list_query, create_user, prepare_user_update_fields
from db import get_db


def test_build_user_list_query_without_search():
    base_sql, count_sql, params = build_user_list_query('')

    assert base_sql == 'SELECT id, username, email, nickname, role, status, created_at, updated_at, last_login_at, avatar_color FROM users ORDER BY id DESC'
    assert count_sql == 'SELECT COUNT(*) AS c FROM users'
    assert params == []


def test_build_user_list_query_with_search():
    base_sql, count_sql, params = build_user_list_query('alice')

    assert 'WHERE username LIKE ? OR email LIKE ? OR nickname LIKE ?' in base_sql
    assert count_sql.endswith('WHERE username LIKE ? OR email LIKE ? OR nickname LIKE ?')
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
    assert 'password_hash' not in user
