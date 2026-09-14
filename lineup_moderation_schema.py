"""SQLite equivalent of DB-service migration 0016; applied to new and old DBs."""

LINEUP_MODERATION_SCHEMA = '''
CREATE TABLE IF NOT EXISTS lineup_moderation (
    lineup_id INTEGER PRIMARY KEY REFERENCES lineups(id),
    state TEXT NOT NULL CHECK (state IN ('banned', 'pending', 'rejected', 'approved', 'released')),
    reason TEXT NOT NULL,
    prior_status TEXT NOT NULL CHECK (prior_status IN ('normal', 'hidden')),
    proposed_name TEXT,
    proposed_code TEXT,
    proposed_season_id TEXT,
    review_note TEXT NOT NULL DEFAULT '',
    notice_state TEXT NOT NULL DEFAULT 'unread' CHECK (notice_state IN ('unread', 'read')),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitted_at TEXT,
    reviewed_at TEXT,
    CHECK (state != 'pending' OR (proposed_name IS NOT NULL AND proposed_code IS NOT NULL AND proposed_season_id IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS lineup_moderation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lineup_id INTEGER NOT NULL REFERENCES lineups(id),
    actor_user_id INTEGER NOT NULL REFERENCES users(id),
    action TEXT NOT NULL CHECK (action IN ('ban', 'submit', 'approve', 'reject', 'release')),
    reason TEXT NOT NULL DEFAULT '',
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lineup_moderation_state_updated ON lineup_moderation (state, updated_at DESC, lineup_id DESC);
CREATE INDEX IF NOT EXISTS idx_lineup_moderation_events_lineup ON lineup_moderation_events (lineup_id, id DESC);
'''
