import pytest

from app import create_app


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
