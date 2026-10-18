"""SQLite equivalent of PostgreSQL migration 0021."""

NOTIFICATION_SCHEMA = '''
CREATE TABLE IF NOT EXISTS feedback_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    source_type TEXT NOT NULL CHECK (source_type IN ('guestbook','report')),
    source_id INTEGER NOT NULL,
    lineup_id INTEGER REFERENCES lineups(id),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','resolved','dismissed')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_type, source_id)
);
CREATE TABLE IF NOT EXISTS feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL REFERENCES feedback_threads(id) ON DELETE CASCADE,
    actor_user_id INTEGER REFERENCES users(id),
    actor_role TEXT NOT NULL CHECK (actor_role IN ('user','admin','system')),
    status TEXT NOT NULL CHECK (status IN ('pending','in_progress','resolved','dismissed')),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL CHECK (kind IN ('feedback','like','favorite','copy')),
    group_key TEXT NOT NULL,
    lineup_id INTEGER REFERENCES lineups(id),
    feedback_id INTEGER REFERENCES feedback_threads(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 1 CHECK (event_count > 0),
    read_count INTEGER NOT NULL DEFAULT 0 CHECK (read_count >= 0),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    notice_state TEXT NOT NULL DEFAULT 'unread' CHECK (notice_state IN ('unread','read')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, group_key)
);
CREATE TABLE IF NOT EXISTS author_favorite_receipts (
    lineup_id INTEGER NOT NULL REFERENCES lineups(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    PRIMARY KEY (lineup_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_feedback_user_updated ON feedback_threads(user_id, updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_status_updated ON feedback_threads(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_events_thread ON feedback_events(thread_id, id);
CREATE INDEX IF NOT EXISTS idx_user_notifications_inbox ON user_notifications(user_id, notice_state, updated_at DESC, id DESC);
'''

# Preserve old feedback without generating a wave of unread historical messages.
FEEDBACK_BACKFILL = '''
INSERT INTO feedback_threads (user_id, source_type, source_id, lineup_id, title, content, status, created_at, updated_at)
SELECT r.reporter_user_id, 'report', r.id, r.lineup_id, l.name, r.reason, r.status,
       r.created_at, COALESCE(r.handled_at, r.created_at)
FROM reports r JOIN lineups l ON l.id=r.lineup_id WHERE 1=1
ON CONFLICT(source_type, source_id) DO NOTHING;
INSERT INTO feedback_threads (user_id, source_type, source_id, title, content, status, created_at, updated_at)
SELECT user_id, 'guestbook', id, '给站长的留言', content, 'pending', created_at, created_at
FROM guestbook_messages WHERE user_id IS NOT NULL
ON CONFLICT(source_type, source_id) DO NOTHING;
INSERT INTO user_notifications (user_id, kind, group_key, lineup_id, feedback_id, title, body, read_count, notice_state, created_at, updated_at)
SELECT user_id, 'feedback', 'feedback:' || CAST(id AS TEXT), lineup_id, id, title,
       '历史反馈，可在这里查看后续处理进度。', 1, 'read', created_at, updated_at
FROM feedback_threads WHERE user_id IS NOT NULL
ON CONFLICT(user_id, group_key) DO NOTHING;
'''
