AUTOMATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS automation_accounts (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    expires_at TEXT NOT NULL,
    can_import INTEGER NOT NULL DEFAULT 0 CHECK (can_import IN (0, 1)),
    allowed_seasons_json TEXT NOT NULL DEFAULT '[]',
    can_touch INTEGER NOT NULL DEFAULT 0 CHECK (can_touch IN (0, 1)),
    touch_seasons_json TEXT NOT NULL DEFAULT '[]',
    session_version INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL REFERENCES users(id),
    last_used_at TEXT,
    deleted_at TEXT
);
"""


def migrate_automation_sessions(db):
    from db_schema import table_columns
    columns = table_columns(db, 'automation_accounts')
    # Keep the upgrade path for installations that used the earlier token design.
    for name, definition in (
        ('can_touch', 'INTEGER NOT NULL DEFAULT 0 CHECK (can_touch IN (0, 1))'),
        ('touch_seasons_json', "TEXT NOT NULL DEFAULT '[]'"),
        ('session_version', 'INTEGER NOT NULL DEFAULT 1'),
    ):
        if name not in columns:
            db.execute(f'ALTER TABLE automation_accounts ADD COLUMN {name} {definition}')
    db.execute('DROP TABLE IF EXISTS automation_imports')
    for name in ('token_hash', 'token_prefix'):
        if name in columns:
            db.execute(f'ALTER TABLE automation_accounts DROP COLUMN {name}')
