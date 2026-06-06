from admin_user_service import build_user_list_query, prepare_user_update_fields


def test_build_user_list_query_without_search():
    base_sql, count_sql, params = build_user_list_query('')

    assert base_sql == 'SELECT id, username, email, nickname, role, status, created_at, updated_at, last_login_at FROM users ORDER BY id DESC'
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
