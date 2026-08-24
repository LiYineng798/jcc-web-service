import sqlite3

from db_schema import EXTRA_INDEX_STATEMENTS, LINEUP_COLUMN_MIGRATIONS, table_columns, table_names


def migrate_schema(db, admin_id, now_text_func):
    migrate_lineups_table(db, admin_id)
    migrate_legacy_live_comp_stats(db, now_text_func)
    migrate_patch_notes_table(db)
    migrate_site_notices_table(db, now_text_func)
    migrate_daily_admin_reports_table(db, now_text_func)
    migrate_live_comp_upload_jobs_table(db)


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
                jump_season_id TEXT NOT NULL DEFAULT '',
                jump_tab TEXT NOT NULL DEFAULT '',
                marquee_enabled INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
    else:
        columns = table_columns(db, 'site_notices')
        if 'jump_season_id' not in columns:
            db.execute("ALTER TABLE site_notices ADD COLUMN jump_season_id TEXT NOT NULL DEFAULT ''")
        if 'jump_tab' not in columns:
            db.execute("ALTER TABLE site_notices ADD COLUMN jump_tab TEXT NOT NULL DEFAULT ''")
        if 'marquee_enabled' not in columns:
            db.execute("ALTER TABLE site_notices ADD COLUMN marquee_enabled INTEGER NOT NULL DEFAULT 1")

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


def migrate_daily_admin_reports_table(db, now_text_func):
    """Ensure the daily admin report snapshot table exists on older installs.

    Mirrors jcc-db-service migration 0007 so SQLite and PostgreSQL stay
    aligned. The generation worker upserts into this table and never rewrites
    already-generated snapshots unless an admin explicitly regenerates one.
    """
    tables = table_names(db)
    if 'daily_admin_reports' not in tables:
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS daily_admin_reports (
                report_date TEXT PRIMARY KEY,
                unique_visitors INTEGER NOT NULL DEFAULT 0,
                page_visits INTEGER NOT NULL DEFAULT 0,
                successful_copies INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
    db.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_daily_admin_reports_generated_at
        ON daily_admin_reports (generated_at DESC)
        '''
    )


def migrate_live_comp_upload_jobs_table(db):
    """Keep the SQLite job queue aligned with migration 0009."""
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS live_comp_upload_jobs (
            id TEXT PRIMARY KEY,
            season_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'preview',
            stage TEXT NOT NULL DEFAULT 'validated',
            filename TEXT NOT NULL DEFAULT '',
            input_path TEXT NOT NULL,
            total_bytes INTEGER NOT NULL DEFAULT 0,
            uploaded_bytes INTEGER NOT NULL DEFAULT 0,
            item_total INTEGER NOT NULL DEFAULT 0,
            item_done INTEGER NOT NULL DEFAULT 0,
            image_total INTEGER NOT NULL DEFAULT 0,
            image_done INTEGER NOT NULL DEFAULT 0,
            current_item TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            result_json TEXT NOT NULL DEFAULT '{}',
            error_message TEXT NOT NULL DEFAULT '',
            created_by INTEGER,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
        '''
    )
    db.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_live_comp_upload_jobs_status_created_at
        ON live_comp_upload_jobs (status, created_at)
        '''
    )
    db.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_live_comp_upload_jobs_created_by_created_at
        ON live_comp_upload_jobs (created_by, created_at DESC)
        '''
    )


def ensure_indexes(db):
    for statement in EXTRA_INDEX_STATEMENTS:
        try:
            db.execute(statement)
        except sqlite3.OperationalError as exc:
            if 'no such table' not in str(exc):
                raise
