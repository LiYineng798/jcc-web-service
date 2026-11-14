"""SQLite mirror of DB migrations 0029/0030; data structures only.

The startup upgrader runs before bootstrap writes, on an idle connection. It never
opens a PostgreSQL migration or starts analytics collection.
"""

import sqlite3

from notification_schema import NOTIFICATION_TABLE_SCHEMA


def _columns(db, table):
    return {row[1] for row in db.execute(f'PRAGMA table_info({table})')}


def _statements(db, script):
    for statement in script.split(';'):
        if statement.strip():
            db.execute(statement)


def _rebuild_notifications(db):
    """Rebuild with FKs suspended by the caller, never cascade-delete actors."""
    old_columns = _columns(db, 'user_notifications')
    if not old_columns or 'deck_submission_id' in old_columns:
        return
    objects = db.execute("""SELECT sql FROM sqlite_master
        WHERE tbl_name='user_notifications' AND type IN ('index','trigger') AND sql IS NOT NULL""").fetchall()
    sequence = db.execute("SELECT seq FROM sqlite_sequence WHERE name='user_notifications'").fetchone()
    db.execute(NOTIFICATION_TABLE_SCHEMA.replace('user_notifications (', 'user_notifications_deck_upgrade (', 1))
    if not old_columns.issubset(_columns(db, 'user_notifications_deck_upgrade')):
        raise RuntimeError('Unknown notification columns; refusing a lossy SQLite rebuild')
    names = ', '.join('"' + name.replace('"', '""') + '"' for name in sorted(old_columns))
    db.execute(f'INSERT INTO user_notifications_deck_upgrade ({names}) SELECT {names} FROM user_notifications')
    db.execute('DROP TABLE user_notifications')
    db.execute('ALTER TABLE user_notifications_deck_upgrade RENAME TO user_notifications')
    if sequence:
        # Preserve the high-water mark even when the highest notification was deleted.
        db.execute("DELETE FROM sqlite_sequence WHERE name='user_notifications'")
        db.execute("INSERT INTO sqlite_sequence(name, seq) VALUES ('user_notifications', ?)", (sequence[0],))
    for row in objects:
        db.execute(row[0])


def migrate_deck_data(db):
    """Atomically upgrade SQLite on startup, before any user/bootstrap writes.

    No implicit commit of caller work. PRAGMA foreign_keys cannot change inside
    a transaction, so this startup helper rejects an active caller transaction.
    """
    if getattr(db, 'kind', 'sqlite') != 'sqlite':
        raise ValueError('Use jcc-db-service migrations for PostgreSQL')
    deck_columns = _columns(db, 'orange_decks')
    if not deck_columns:
        return  # Partial legacy test/maintenance database; base schema runs first.
    copy_columns = _columns(db, 'copy_action_events')
    needs_upgrade = (
        not {name for name, _ in DECK_COLUMNS}.issubset(deck_columns)
        or not {name for name, _ in COPY_COLUMNS}.issubset(copy_columns)
        or 'deck_submission_id' not in _columns(db, 'user_notifications')
    )
    raw = getattr(db, 'connection', db)
    if raw.in_transaction:
        raise RuntimeError('Deck schema upgrade requires an idle SQLite connection')
    foreign_keys = db.execute('PRAGMA foreign_keys').fetchone()[0]
    try:
        db.execute('PRAGMA foreign_keys = OFF')
        db.execute('BEGIN IMMEDIATE')
        # Another startup process may have upgraded while BEGIN waited for its lock.
        deck_columns = _columns(db, 'orange_decks')
        copy_columns = _columns(db, 'copy_action_events')
        for table, current, additions in (
            ('orange_decks', deck_columns, DECK_COLUMNS),
            ('copy_action_events', copy_columns, COPY_COLUMNS),
        ):
            for name, definition in additions:
                if name not in current:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
        _statements(db, DECK_DATA_SCHEMA)
        _rebuild_notifications(db)
        _statements(db, DECK_DATA_INDEXES)
        if needs_upgrade and db.execute('PRAGMA foreign_key_check').fetchone():
            raise sqlite3.IntegrityError('Foreign key violations during deck schema upgrade')
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.execute(f'PRAGMA foreign_keys = {int(foreign_keys)}')


DECK_COLUMNS = (
    ('provided_by_user_id', """INTEGER REFERENCES users(id)"""),
    ('published_by_user_id', """INTEGER REFERENCES users(id)"""),
    ('origin_type', """TEXT NOT NULL DEFAULT 'direct'
    CONSTRAINT orange_decks_origin CHECK (
        (origin_type='direct' AND provided_by_user_id IS NULL)
        OR (origin_type='submission' AND provided_by_user_id IS NOT NULL)
    )"""),
    ('reviewed_card_version', """TEXT"""),
    ('reviewed_at', """TEXT
    CONSTRAINT orange_decks_review CHECK (
        (reviewed_card_version IS NULL AND reviewed_at IS NULL)
        OR (reviewed_card_version IS NOT NULL AND length(trim(reviewed_card_version))>0
            AND reviewed_at IS NOT NULL AND length(trim(reviewed_at))>0)
    )"""),
)

COPY_COLUMNS = (
    ('deck_id', """INTEGER REFERENCES orange_decks(id)"""),
    ('code_type', """TEXT CHECK (code_type IN ('plan','lineup'))"""),
    ('actor_key', """TEXT"""),
    ('client_action_id', """TEXT
    CHECK (client_action_id IS NULL OR length(trim(client_action_id)) BETWEEN 1 AND 64)"""),
    ('rank_eligible', """INTEGER NOT NULL DEFAULT 0
    CONSTRAINT copy_action_events_deck CHECK (
        rank_eligible IN (0,1) AND (
            (target_type='orange_deck' AND deck_id IS NOT NULL
                AND target_id=CAST(deck_id AS TEXT) AND code_type IS NOT NULL
                AND actor_key IS NOT NULL AND length(trim(actor_key))>0
                AND lineup_id IS NULL AND live_comp_id IS NULL
                AND (rank_eligible=0 OR success=1))
            OR (target_type<>'orange_deck' AND deck_id IS NULL AND code_type IS NULL AND rank_eligible=0)
        )
    )"""),
)

DECK_DATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS orange_deck_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submitter_user_id INTEGER NOT NULL REFERENCES users(id),
    season_id TEXT NOT NULL CHECK (length(trim(season_id))>0),
    name TEXT NOT NULL DEFAULT '' CHECK (length(name)<=24),
    plan_code TEXT NOT NULL CHECK (length(trim(plan_code)) BETWEEN 1 AND 512),
    lineup_code TEXT NOT NULL CHECK (length(trim(lineup_code)) BETWEEN 1 AND 20000),
    note TEXT NOT NULL DEFAULT '' CHECK (length(note)<=300),
    code_fingerprint TEXT NOT NULL CHECK (length(code_fingerprint)=64),
    request_key TEXT NOT NULL CHECK (length(trim(request_key)) BETWEEN 1 AND 64),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','needs_info','published','rejected','duplicate','withdrawn')),
    assigned_admin_id INTEGER REFERENCES users(id),
    deck_id INTEGER UNIQUE REFERENCES orange_decks(id),
    duplicate_of_deck_id INTEGER REFERENCES orange_decks(id),
    review_note TEXT NOT NULL DEFAULT '' CHECK (length(review_note)<=1000),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version>=1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    UNIQUE(submitter_user_id, request_key),
    CONSTRAINT orange_deck_submissions_claim CHECK (status<>'processing' OR assigned_admin_id IS NOT NULL),
    CONSTRAINT orange_deck_submissions_published CHECK (status<>'published' OR deck_id IS NOT NULL),
    CONSTRAINT orange_deck_submissions_duplicate CHECK (
        (status='duplicate' AND duplicate_of_deck_id IS NOT NULL
            AND (deck_id IS NULL OR duplicate_of_deck_id<>deck_id))
        OR (status<>'duplicate' AND duplicate_of_deck_id IS NULL)
    ),
    CONSTRAINT orange_deck_submissions_resolved CHECK (
        (status IN ('published','rejected','duplicate','withdrawn') AND resolved_at IS NOT NULL)
        OR (status IN ('pending','processing','needs_info') AND resolved_at IS NULL)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_deck_submissions_active_codes
    ON orange_deck_submissions(submitter_user_id, season_id, code_fingerprint)
    WHERE status IN ('pending','processing','needs_info');
CREATE INDEX IF NOT EXISTS idx_deck_submissions_queue ON orange_deck_submissions(status, created_at, id);
CREATE INDEX IF NOT EXISTS idx_deck_submissions_user ON orange_deck_submissions(submitter_user_id, updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_deck_submissions_assignee ON orange_deck_submissions(assigned_admin_id, status, updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_deck_submissions_codes ON orange_deck_submissions(season_id, code_fingerprint);

CREATE TABLE IF NOT EXISTS orange_deck_submission_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES orange_deck_submissions(id),
    actor_user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL CHECK (action IN ('submit','update','claim','release','assign','save_draft','request_info','resubmit','publish','reject','mark_duplicate','withdraw')),
    from_status TEXT CHECK (from_status IN ('pending','processing','needs_info','published','rejected','duplicate','withdrawn')),
    to_status TEXT NOT NULL CHECK (to_status IN ('pending','processing','needs_info','published','rejected','duplicate','withdrawn')),
    submission_version INTEGER NOT NULL CHECK (submission_version>=1),
    note TEXT NOT NULL DEFAULT '' CHECK (length(note)<=1000),
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(submission_id, submission_version)
);
CREATE INDEX IF NOT EXISTS idx_deck_submission_events_history ON orange_deck_submission_events(submission_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_deck_submission_events_action ON orange_deck_submission_events(action, created_at, submission_id);

CREATE TABLE IF NOT EXISTS orange_deck_activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL REFERENCES orange_decks(id),
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL CHECK (action IN ('published','hidden','restored','deleted','reviewed','like','favorite_add','favorite_remove')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deck_activity_action ON orange_deck_activity_events(action, created_at, deck_id);
CREATE INDEX IF NOT EXISTS idx_deck_activity_history ON orange_deck_activity_events(deck_id, created_at, id);

CREATE TABLE IF NOT EXISTS orange_deck_visit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_date TEXT NOT NULL,
    visitor_key TEXT NOT NULL CHECK (length(trim(visitor_key))>0),
    user_id INTEGER REFERENCES users(id),
    surface TEXT NOT NULL CHECK (surface IN ('library','detail')),
    deck_id INTEGER REFERENCES orange_decks(id),
    device_type TEXT NOT NULL DEFAULT 'unknown' CHECK (device_type IN ('mobile','tablet','desktop','unknown')),
    created_at TEXT NOT NULL,
    CONSTRAINT orange_deck_visit_surface CHECK (
        (surface='library' AND deck_id IS NULL) OR (surface='detail' AND deck_id IS NOT NULL)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_deck_visits_library ON orange_deck_visit_events(visit_date, visitor_key) WHERE surface='library';
CREATE UNIQUE INDEX IF NOT EXISTS idx_deck_visits_detail ON orange_deck_visit_events(visit_date, visitor_key, deck_id) WHERE surface='detail';
CREATE INDEX IF NOT EXISTS idx_deck_visits_surface ON orange_deck_visit_events(surface, created_at, deck_id);

"""

DECK_DATA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_orange_decks_provider_published
    ON orange_decks(provided_by_user_id, status, published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_user_notifications_deck_submission ON user_notifications(deck_submission_id)
    WHERE deck_submission_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_copy_action_client_action ON copy_action_events(client_action_id)
    WHERE client_action_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_copy_action_deck_created ON copy_action_events(target_type, created_at, deck_id);
CREATE INDEX IF NOT EXISTS idx_copy_action_deck_actor ON copy_action_events(deck_id, created_at, actor_key);
"""
