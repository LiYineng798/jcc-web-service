import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

TARGET_SEASON_ID = 's17-star-god'


def archive_database(database_path, target_season_id=TARGET_SEASON_ID, backup=True):
    db_path = Path(database_path).expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f'Database not found: {db_path}')

    backup_path = None
    if backup:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = db_path.with_name(f'{db_path.stem}.before-s17-archive-{timestamp}{db_path.suffix}')
        shutil.copy2(db_path, backup_path)

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(lineups)').fetchall()}
        if 'season_id' not in columns:
            connection.execute("ALTER TABLE lineups ADD COLUMN season_id TEXT NOT NULL DEFAULT 's17-star-god'")
        before = connection.execute('SELECT COUNT(*) AS total FROM lineups').fetchone()['total']
        connection.execute('UPDATE lineups SET season_id = ?, updated_at = ?', (target_season_id, now))
        connection.execute('CREATE INDEX IF NOT EXISTS idx_lineups_season_status_updated_at ON lineups (season_id, status, updated_at)')
        connection.commit()
        after = connection.execute('SELECT COUNT(*) AS total FROM lineups WHERE season_id = ?', (target_season_id,)).fetchone()['total']

    return {'database': str(db_path), 'backup': str(backup_path) if backup_path else None, 'total_lineups': before, 'archived_lineups': after}


def main():
    parser = argparse.ArgumentParser(description='One-time archive all existing lineups to S17.')
    parser.add_argument('--database', default='instance/lineups.sqlite3', help='SQLite database path')
    parser.add_argument('--season-id', default=TARGET_SEASON_ID, help='Target season id')
    parser.add_argument('--no-backup', action='store_true', help='Do not create a database backup copy')
    args = parser.parse_args()

    result = archive_database(args.database, target_season_id=args.season_id, backup=not args.no_backup)
    print(f"Database: {result['database']}")
    if result['backup']:
        print(f"Backup: {result['backup']}")
    print(f"Archived lineups: {result['archived_lineups']}/{result['total_lineups']} -> {args.season_id}")


if __name__ == '__main__':
    main()
