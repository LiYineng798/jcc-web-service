SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    nickname TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS lineups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    season_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'normal',
    admin_like_adjustment INTEGER NOT NULL DEFAULT 0,
    admin_copy_adjustment INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    lineup_id INTEGER NOT NULL,
    like_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, lineup_id, like_date),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);

CREATE TABLE IF NOT EXISTS copy_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lineup_id INTEGER NOT NULL,
    user_id INTEGER,
    ip_address TEXT,
    copy_key TEXT NOT NULL,
    bucket_start TEXT NOT NULL,
    counted INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(lineup_id, copy_key, bucket_start),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);

CREATE TABLE IF NOT EXISTS copy_action_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    season_id TEXT,
    lineup_id INTEGER,
    live_comp_id TEXT,
    user_id INTEGER,
    visitor_token TEXT,
    ip_address TEXT,
    source_page TEXT NOT NULL DEFAULT '',
    success INTEGER NOT NULL DEFAULT 1,
    counted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);

CREATE TABLE IF NOT EXISTS live_comp_global_stats (
    stats_key TEXT PRIMARY KEY,
    total_copy_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS live_comp_global_daily_stats (
    copy_date TEXT PRIMARY KEY,
    copy_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cache_state (
    cache_key TEXT PRIMARY KEY,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO cache_state (cache_key, revision, created_at, updated_at) VALUES
('home', 0, strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'), strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
('score', 0, strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'), strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'));

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO app_settings (setting_key, setting_value, updated_at) VALUES
('simulator_enabled', 'true', strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
('notice_enabled', 'false', strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
('notice_data', '{}', strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'));

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    lineup_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, lineup_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_user_id INTEGER NOT NULL,
    lineup_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    handled_at TEXT,
    handled_by INTEGER,
    FOREIGN KEY(reporter_user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);

CREATE TABLE IF NOT EXISTS recent_lineup_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    lineup_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, lineup_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);

CREATE TABLE IF NOT EXISTS recent_lineup_copies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    lineup_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, lineup_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);

CREATE TABLE IF NOT EXISTS login_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ip_address TEXT NOT NULL,
    success INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS visit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_date TEXT NOT NULL,
    visitor_key TEXT NOT NULL,
    visitor_kind TEXT NOT NULL,
    user_id INTEGER,
    visitor_token TEXT,
    ip_address TEXT,
    page_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(visit_date, page_key, visitor_key),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    key TEXT NOT NULL,
    window_start TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    UNIQUE(scope, key, window_start)
);

CREATE TABLE IF NOT EXISTS growth_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    user_id INTEGER,
    visitor_token TEXT,
    ip_address TEXT,
    ref_lineup_id INTEGER,
    page_key TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(ref_lineup_id) REFERENCES lineups(id)
);

CREATE INDEX IF NOT EXISTS idx_growth_events_name_created_at
ON growth_events (event_name, created_at);

CREATE INDEX IF NOT EXISTS idx_growth_events_user_created_at
ON growth_events (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_growth_events_visitor_created_at
ON growth_events (visitor_token, created_at);

CREATE INDEX IF NOT EXISTS idx_likes_lineup_created_at
ON likes (lineup_id, created_at);

CREATE INDEX IF NOT EXISTS idx_copy_events_lineup_created_at
ON copy_events (lineup_id, created_at);

CREATE INDEX IF NOT EXISTS idx_copy_action_events_target_created_at
ON copy_action_events (target_type, target_id, created_at);

CREATE INDEX IF NOT EXISTS idx_copy_action_events_user_created_at
ON copy_action_events (user_id, created_at);

CREATE TRIGGER IF NOT EXISTS trg_lineups_cache_state_insert
AFTER INSERT ON lineups
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_lineups_cache_state_update
AFTER UPDATE ON lineups
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_lineups_cache_state_delete
AFTER DELETE ON lineups
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_likes_cache_state_insert
AFTER INSERT ON likes
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_likes_cache_state_update
AFTER UPDATE ON likes
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_likes_cache_state_delete
AFTER DELETE ON likes
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_copy_events_cache_state_insert
AFTER INSERT ON copy_events
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_copy_events_cache_state_update
AFTER UPDATE ON copy_events
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_copy_events_cache_state_delete
AFTER DELETE ON copy_events
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key IN ('home', 'score');
END;

CREATE TRIGGER IF NOT EXISTS trg_favorites_cache_state_insert
AFTER INSERT ON favorites
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key = 'home';
END;

CREATE TRIGGER IF NOT EXISTS trg_favorites_cache_state_update
AFTER UPDATE ON favorites
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key = 'home';
END;

CREATE TRIGGER IF NOT EXISTS trg_favorites_cache_state_delete
AFTER DELETE ON favorites
BEGIN
    UPDATE cache_state
    SET revision = revision + 1,
        updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE cache_key = 'home';
END;

CREATE TABLE IF NOT EXISTS guestbook_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    nickname TEXT NOT NULL,
    content TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

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
);

CREATE INDEX IF NOT EXISTS idx_patch_notes_status_published_at
ON patch_notes (status, published_at DESC, id DESC);
'''


LINEUP_COLUMN_MIGRATIONS = {
    'user_id': 'ALTER TABLE lineups ADD COLUMN user_id INTEGER',
    'status': "ALTER TABLE lineups ADD COLUMN status TEXT NOT NULL DEFAULT 'normal'",
    'admin_like_adjustment': 'ALTER TABLE lineups ADD COLUMN admin_like_adjustment INTEGER NOT NULL DEFAULT 0',
    'admin_copy_adjustment': 'ALTER TABLE lineups ADD COLUMN admin_copy_adjustment INTEGER NOT NULL DEFAULT 0',
    'version': 'ALTER TABLE lineups ADD COLUMN version INTEGER NOT NULL DEFAULT 1',
    'season_id': "ALTER TABLE lineups ADD COLUMN season_id TEXT NOT NULL DEFAULT 's17-star-god'",
}


EXTRA_INDEX_STATEMENTS = (
    'CREATE INDEX IF NOT EXISTS idx_lineups_user_status_updated_at ON lineups (user_id, status, updated_at)',
    'CREATE INDEX IF NOT EXISTS idx_lineups_season_status_updated_at ON lineups (season_id, status, updated_at)',
    'CREATE INDEX IF NOT EXISTS idx_lineups_status_updated_id ON lineups (status, updated_at DESC, id DESC)',
    'CREATE INDEX IF NOT EXISTS idx_likes_created_lineup ON likes (created_at, lineup_id)',
    'CREATE INDEX IF NOT EXISTS idx_copy_events_counted_created_lineup ON copy_events (counted, created_at, lineup_id)',
    'CREATE INDEX IF NOT EXISTS idx_copy_action_events_target_created_at ON copy_action_events (target_type, target_id, created_at)',
    'CREATE INDEX IF NOT EXISTS idx_copy_action_events_user_created_at ON copy_action_events (user_id, created_at)',
)


def table_columns(db, table_name):
    rows = db.execute(f'PRAGMA table_info({table_name})').fetchall()
    return {row['name'] for row in rows}


def table_names(db):
    rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row['name'] for row in rows}
