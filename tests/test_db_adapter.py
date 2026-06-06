import pytest

from db_adapter import database_kind, placeholder, qmarks


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

