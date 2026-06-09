import sqlite3

from db_schema import EXTRA_INDEX_STATEMENTS, LINEUP_COLUMN_MIGRATIONS, table_columns, table_names


def migrate_schema(db, admin_id, now_text_func):
    migrate_lineups_table(db, admin_id)
    migrate_legacy_live_comp_stats(db, now_text_func)
    migrate_patch_notes_table(db)
    migrate_site_notices_table(db, now_text_func)


def migrate_legacy_live_comp_stats(db, now_text_func):
    columns = table_columns(db, 'live_comp_stats')
    if not columns:
        return
    if 'total_copy_count' not in columns:
        db.execute('ALTER TABLE live_comp_stats ADD COLUMN total_copy_count INTEGER NOT NULL DEFAULT 0')
        if 'copy_count' in columns:
            db.execute('UPDATE live_comp_stats SET total_copy_count = copy_count WHERE total_copy_count = 0')
    total_row = db.execute('SELECT COALESCE(SUM(total_copy_count), 0) AS total FROM live_comp_stats').fetchone()
    existing_global = db.execute("SELECT total_copy_count FROM live_comp_global_stats WHERE stats_key = 'global'").fetchone()
    if total_row and total_row['total'] and not existing_global:
        now = now_text_func()
        db.execute(
            '''INSERT INTO live_comp_global_stats (stats_key, total_copy_count, created_at, updated_at)
               VALUES ('global', ?, ?, ?)''',
            (int(total_row['total']), now, now),
        )


def migrate_lineups_table(db, admin_id):
    columns = table_columns(db, 'lineups')
    if not columns:
        return

    for column_name, statement in LINEUP_COLUMN_MIGRATIONS.items():
        if column_name not in columns:
            db.execute(statement)

    db.execute('UPDATE lineups SET user_id = ? WHERE user_id IS NULL', (admin_id,))
    db.execute("UPDATE lineups SET season_id = 's17-star-god' WHERE season_id IS NULL OR season_id = ''")
    db.execute("UPDATE lineups SET season_id = 's16-legends' WHERE season_id = 's16-archive'")


def migrate_patch_notes_table(db):
    tables = table_names(db)
    if 'patch_notes' not in tables:
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS patch_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                summary_markdown TEXT NOT NULL,
                original_text TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                published_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
    db.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_patch_notes_status_published_at
        ON patch_notes (status, published_at DESC, id DESC)
        '''
    )


def migrate_site_notices_table(db, now_text_func):
    tables = table_names(db)
    if 'site_notices' not in tables:
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS site_notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                link_url TEXT NOT NULL DEFAULT '',
                link_text TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
    db.execute(
        '''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_site_notices_single_active
        ON site_notices (is_active)
        WHERE is_active = 1
        '''
    )

    existing = db.execute('SELECT id FROM site_notices LIMIT 1').fetchone()
    if existing:
        return
    if 'app_settings' not in tables:
        return

    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'notice_data'"
    ).fetchone()
    if not row:
        return

    import json
    try:
        data = json.loads(row['setting_value'])
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, dict):
        return

    title = str(data.get('title', '')).strip()
    message = str(data.get('message', '')).strip()
    if not title or not message:
        return

    enabled_row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'notice_enabled'"
    ).fetchone()
    now = now_text_func()
    db.execute(
        '''
        INSERT INTO site_notices (title, message, link_url, link_text, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            title,
            message,
            str(data.get('link_url', '')).strip(),
            str(data.get('link_text', '')).strip(),
            1 if enabled_row and enabled_row['setting_value'] == 'true' else 0,
            now,
            now,
        ),
    )


def ensure_indexes(db):
    for statement in EXTRA_INDEX_STATEMENTS:
        try:
            db.execute(statement)
        except sqlite3.OperationalError as exc:
            if 'no such table' not in str(exc):
                raise
