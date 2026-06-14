import sqlite3

from db_migrations import ensure_indexes, migrate_lineups_table, migrate_schema
from db_schema import table_columns


def test_migrate_lineups_table_adds_expected_columns():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute(
        '''CREATE TABLE lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )'''
    )

    migrate_lineups_table(db, admin_id=7)
    columns = table_columns(db, 'lineups')
    row = db.execute('SELECT user_id, status, season_id FROM lineups LIMIT 1').fetchone()

    assert 'user_id' in columns
    assert 'status' in columns
    assert 'season_id' in columns
    assert row is None


def test_ensure_indexes_creates_lineup_indexes():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute(
        '''CREATE TABLE lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            status TEXT,
            updated_at TEXT,
            season_id TEXT
        )'''
    )

    ensure_indexes(db)
    names = {
        row['name']
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    }

    assert 'idx_lineups_user_status_updated_at' in names
    assert 'idx_lineups_season_status_updated_at' in names


def test_migrate_schema_handles_missing_legacy_live_comp_stats_table():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute(
        '''CREATE TABLE lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )'''
    )

    migrate_schema(db, admin_id=1, now_text_func=lambda: '2026-05-24 00:00:00')

    columns = table_columns(db, 'lineups')
    assert 'season_id' in columns
