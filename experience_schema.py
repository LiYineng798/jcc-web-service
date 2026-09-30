SEARCH_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    visitor_key TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id),
    query TEXT NOT NULL,
    season_id TEXT NOT NULL,
    sort_key TEXT NOT NULL,
    result_count INTEGER NOT NULL CHECK (result_count >= 0),
    device_type TEXT NOT NULL DEFAULT 'unknown' CHECK (device_type IN ('mobile','tablet','desktop','unknown')),
    created_at TEXT NOT NULL,
    UNIQUE(visitor_key, event_id)
);
CREATE INDEX IF NOT EXISTS idx_search_events_created_at ON search_events(created_at);
"""
