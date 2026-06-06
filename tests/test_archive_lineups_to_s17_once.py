import sqlite3

from scripts.archive_lineups_to_s17_once import archive_database


def test_archive_lineups_to_s17_once_sets_all_existing_lineups(tmp_path):
    db_path = tmp_path / 'lineups.sqlite3'
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            '''CREATE TABLE lineups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                season_id TEXT NOT NULL DEFAULT 'old-season',
                status TEXT NOT NULL DEFAULT 'normal',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )'''
        )
        connection.execute("INSERT INTO lineups (name, code, season_id, created_at, updated_at) VALUES ('A', '#A', 'old-season', '2026-01-01 00:00:00', '2026-01-01 00:00:00')")
        connection.execute("INSERT INTO lineups (name, code, season_id, created_at, updated_at) VALUES ('B', '#B', 'another-season', '2026-01-01 00:00:00', '2026-01-01 00:00:00')")
        connection.commit()

    result = archive_database(db_path)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute('SELECT season_id FROM lineups ORDER BY id').fetchall()
    assert result['archived_lineups'] == 2
    assert [row[0] for row in rows] == ['s17-star-god', 's17-star-god']
    assert result['backup'] is not None
