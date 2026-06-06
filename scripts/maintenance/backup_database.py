from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def backup_sqlite_database(database_path: str | Path, backup_dir: str | Path, timestamp: str | None = None) -> Path | None:
    database = Path(database_path)
    if not database.exists():
        return None

    backup_directory = Path(backup_dir)
    backup_directory.mkdir(parents=True, exist_ok=True)
    backup_timestamp = timestamp or datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = backup_directory / f'{database.stem}.{backup_timestamp}{database.suffix}'
    shutil.copy2(database, backup_path)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Backup the JCC SQLite database before deployment updates.')
    parser.add_argument('--database', default='instance/lineups.sqlite3', help='SQLite database path')
    parser.add_argument('--backup-dir', default='/opt/jcc/backups', help='Directory for database backups')
    args = parser.parse_args()

    backup_path = backup_sqlite_database(args.database, args.backup_dir)
    if backup_path is None:
        print(f'数据库不存在，跳过备份：{args.database}')
    else:
        print(f'数据库已备份：{backup_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
