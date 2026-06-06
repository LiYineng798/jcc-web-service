from app import create_app


def test_database_url_defaults_to_sqlite_instance_path():
    app = create_app({'TESTING': True})

    assert app.config['DATABASE_URL'].startswith('sqlite:///')
    assert app.config['DATABASE'].endswith('lineups.sqlite3')


def test_database_url_can_be_configured(monkeypatch):
    monkeypatch.setenv('JCC_DATABASE_URL', 'postgresql://user:pass@database.np5.top:5432/jcc')

    app = create_app({'TESTING': True})

    assert app.config['DATABASE_URL'] == 'postgresql://user:pass@database.np5.top:5432/jcc'

