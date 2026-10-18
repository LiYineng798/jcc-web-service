from pathlib import Path

import pytest

from scripts.maintenance.backup_database import backup_sqlite_database, main


def test_backup_cli_requires_explicit_destination(monkeypatch):
    monkeypatch.setattr('sys.argv', ['backup_database.py'])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_backup_sqlite_database_copies_existing_database(tmp_path):
    database = tmp_path / 'lineups.sqlite3'
    database.write_bytes(b'jcc-db')
    backup_dir = tmp_path / 'backups'

    backup_path = backup_sqlite_database(database, backup_dir, timestamp='20260524-130000')

    assert backup_path == backup_dir / 'lineups.20260524-130000.sqlite3'
    assert backup_path.read_bytes() == b'jcc-db'


def test_backup_sqlite_database_returns_none_when_missing(tmp_path):
    backup_path = backup_sqlite_database(tmp_path / 'missing.sqlite3', tmp_path / 'backups', timestamp='20260524-130000')

    assert backup_path is None
