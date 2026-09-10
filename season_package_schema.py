"""SQLite schema aligned with DB migration 0015."""

SEASON_PACKAGE_SCHEMA = r'''
CREATE TABLE IF NOT EXISTS season_release_packages (
    id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL UNIQUE,
    season_id TEXT NOT NULL,
    game_version TEXT NOT NULL,
    data_revision INTEGER NOT NULL CHECK (data_revision > 0),
    zip_sha256 TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    total_bytes BIGINT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('queued','validating','ready','rejected','cancelled')),
    manifest_json TEXT NOT NULL,
    report_json TEXT NOT NULL DEFAULT '{}',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    published_at TEXT,
    UNIQUE (season_id, game_version, data_revision)
);
CREATE TABLE IF NOT EXISTS season_import_jobs (
    id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL UNIQUE REFERENCES season_release_packages(id),
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','cancelled')),
    stage TEXT NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    message TEXT NOT NULL DEFAULT '',
    attempt INTEGER NOT NULL DEFAULT 0,
    lease_token TEXT,
    heartbeat_at TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS season_active_releases (
    season_id TEXT PRIMARY KEY,
    release_id TEXT REFERENCES season_release_packages(id),
    previous_release_id TEXT REFERENCES season_release_packages(id),
    revision INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS season_release_events (
    id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL,
    release_id TEXT REFERENCES season_release_packages(id),
    previous_release_id TEXT REFERENCES season_release_packages(id),
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_season_import_jobs_queue ON season_import_jobs(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_season_packages_season_created ON season_release_packages(season_id, created_at);
CREATE INDEX IF NOT EXISTS idx_season_release_events_season_created ON season_release_events(season_id, created_at);

'''
