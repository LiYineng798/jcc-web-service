import pytest

from app import create_app
from db import get_db


def test_postgres_database_url_requires_existing_schema(monkeypatch):
    monkeypatch.setattr('db.postgres_schema_ready', lambda: False)

    with pytest.raises(RuntimeError, match='PostgreSQL schema is not initialized'):
        create_app({
            'TESTING': True,
            'DATABASE_URL': 'postgresql://user:pass@database.np5.top:5432/jcc',
        })


def test_postgres_database_url_does_not_create_sqlite_file(tmp_path, monkeypatch):
    sqlite_path = tmp_path / 'lineups.sqlite3'
    monkeypatch.setattr('db.postgres_schema_ready', lambda: False)

    with pytest.raises(RuntimeError):
        create_app({
            'TESTING': True,
            'DATABASE': str(sqlite_path),
            'DATABASE_URL': 'postgresql://user:pass@database.np5.top:5432/jcc',
        })

    assert not sqlite_path.exists()


def test_postgres_get_db_uses_psycopg_connection(monkeypatch):
    created = {}

    class FakeConnection:
        def close(self):
            created['closed'] = True

    def fake_connect(database_url, row_factory=None):
        created['database_url'] = database_url
        created['row_factory'] = row_factory
        return FakeConnection()

    monkeypatch.setattr('db.postgres_schema_ready', lambda: True)
    monkeypatch.setattr('db.psycopg.connect', fake_connect)
    app = create_app({
        'TESTING': True,
        'DATABASE_URL': 'postgresql://user:pass@database.np5.top:5432/jcc',
    })

    with app.app_context():
        assert get_db().__class__ is FakeConnection

    assert created['database_url'] == 'postgresql://user:pass@database.np5.top:5432/jcc'
    assert created['row_factory'] is not None


def test_postgres_schema_ready_checks_schema_migrations(monkeypatch):
    calls = []

    class FakeCursor:
        def execute(self, sql):
            calls.append(sql)

        def fetchone(self):
            return {'exists': True}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('db.psycopg.connect', lambda *args, **kwargs: FakeConnection())
    app = create_app({
        'TESTING': True,
        'DATABASE_URL': 'postgresql://user:pass@database.np5.top:5432/jcc',
    })

    with app.app_context():
        assert app.config['DATABASE_URL'].startswith('postgresql://')

    assert any('schema_migrations' in sql for sql in calls)
