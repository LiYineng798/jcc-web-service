import sqlite3
from pathlib import Path

from app import create_app
from test_lineup_permissions import auth_headers


def test_legacy_single_user_lineups_schema_is_migrated():
    db_path = Path(__file__).resolve().parents[1] / 'test-legacy.sqlite3'
    if db_path.exists():
        db_path.unlink()

    legacy_db = sqlite3.connect(db_path)
    legacy_db.execute(
        '''CREATE TABLE lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )'''
    )
    legacy_db.execute(
        '''INSERT INTO lineups (name, code, created_at, updated_at)
           VALUES ('旧阵容', 'OLD-CODE', '2026-05-01 10:00:00', '2026-05-01 10:00:00')'''
    )
    legacy_db.commit()
    legacy_db.close()

    try:
        app = create_app({
            'TESTING': True,
            'DATABASE': str(db_path),
            'SECRET_KEY': 'test-secret',
            'ADMIN_USERNAME': 'adminxlx',
            'ADMIN_PASSWORD': 'Admin1234',
        })
        client = app.test_client()

        assert client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'}).status_code == 200
        response = client.post(
            '/api/lineups',
            json={'name': '新阵容', 'code': '#NEWCODE'},
            headers=auth_headers(client),
        )

        assert response.status_code == 201
        names = [item['name'] for item in client.get('/api/lineups').get_json()]
        assert '旧阵容' in names
        assert '新阵容' in names
    finally:
        if db_path.exists():
            db_path.unlink()
