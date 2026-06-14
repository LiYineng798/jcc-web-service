import pytest

from db_adapter import (
    database_kind,
    insert_ignore_sql,
    insert_returning_id_sql,
    last_insert_id,
    placeholder,
    qmarks,
    to_driver_sql,
    upsert_setting_sql,
)


def test_database_kind_detects_sqlite_urls():
    assert database_kind('sqlite:///instance/lineups.sqlite3') == 'sqlite'


def test_database_kind_detects_postgres_urls():
    assert database_kind('postgresql://u:p@h:5432/db') == 'postgres'
    assert database_kind('postgres://u:p@h:5432/db') == 'postgres'


def test_database_kind_rejects_unknown_urls():
    with pytest.raises(ValueError, match='Unsupported database URL scheme'):
        database_kind('mysql://u:p@h/db')


def test_placeholder_uses_driver_specific_style():
    assert placeholder('sqlite') == '?'
    assert placeholder('postgres') == '%s'


def test_qmarks_returns_repeated_placeholders():
    assert qmarks('sqlite', 3) == '?,?,?'
    assert qmarks('postgres', 3) == '%s,%s,%s'


def test_to_driver_sql_converts_sqlite_placeholders_for_postgres():
    sql = "SELECT * FROM users WHERE username = ? AND note = '?' AND email = ?"

    assert to_driver_sql(sql, 'sqlite') == sql
    assert to_driver_sql(sql, 'postgres') == "SELECT * FROM users WHERE username = %s AND note = '?' AND email = %s"


def test_insert_returning_id_sql_adds_returning_for_postgres_only():
    sql = 'INSERT INTO users (username) VALUES (?)'

    assert insert_returning_id_sql(sql, 'sqlite') == sql
    assert insert_returning_id_sql(sql, 'postgres') == 'INSERT INTO users (username) VALUES (%s) RETURNING id'


def test_last_insert_id_reads_driver_specific_cursor_shape():
    class SqliteCursor:
        lastrowid = 42

    class PostgresCursor:
        def fetchone(self):
            return {'id': 43}

    assert last_insert_id(SqliteCursor(), 'sqlite') == 42
    assert last_insert_id(PostgresCursor(), 'postgres') == 43


def test_insert_ignore_sql_generates_driver_specific_conflict_clause():
    sqlite_sql = insert_ignore_sql('favorites', ['user_id', 'lineup_id', 'created_at'], ['user_id', 'lineup_id'], 'sqlite')
    postgres_sql = insert_ignore_sql('favorites', ['user_id', 'lineup_id', 'created_at'], ['user_id', 'lineup_id'], 'postgres')

    assert sqlite_sql == 'INSERT OR IGNORE INTO favorites (user_id, lineup_id, created_at) VALUES (?, ?, ?)'
    assert postgres_sql == 'INSERT INTO favorites (user_id, lineup_id, created_at) VALUES (%s, %s, %s) ON CONFLICT (user_id, lineup_id) DO NOTHING'


def test_upsert_setting_sql_generates_driver_specific_upsert():
    sqlite_sql = upsert_setting_sql('sqlite')
    postgres_sql = upsert_setting_sql('postgres')

    assert sqlite_sql == 'INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)'
    assert postgres_sql == (
        'INSERT INTO app_settings (setting_key, setting_value, updated_at) VALUES (%s, %s, %s) '
        'ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = EXCLUDED.updated_at'
    )
