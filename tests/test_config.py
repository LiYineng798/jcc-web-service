from app import create_app
from config import apply_config
from flask import Flask


def test_mail_sender_default_is_example_and_can_be_overridden(monkeypatch):
    monkeypatch.delenv('RESEND_FROM_EMAIL', raising=False)
    app = Flask(__name__)
    apply_config(app)
    assert app.config['RESEND_FROM_EMAIL'] == 'Site <no-reply@example.com>'

    monkeypatch.setenv('RESEND_FROM_EMAIL', 'Test Site <sender@example.test>')
    apply_config(app)
    assert app.config['RESEND_FROM_EMAIL'] == 'Test Site <sender@example.test>'


def test_database_url_defaults_to_sqlite_instance_path():
    app = create_app({'TESTING': True})

    assert app.config['DATABASE_URL'].startswith('sqlite:///')
    assert app.config['DATABASE'].endswith('lineups.sqlite3')


def test_database_url_can_be_configured(monkeypatch):
    monkeypatch.setenv('JCC_DATABASE_URL', 'postgresql://user:pass@database.example.com:5432/jcc')
    monkeypatch.setattr('db.postgres_schema_ready', lambda: True)

    app = create_app({'TESTING': True})

    assert app.config['DATABASE_URL'] == 'postgresql://user:pass@database.example.com:5432/jcc'
