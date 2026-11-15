"""Data-only checks: no collector, admin routes or recommendation implementation."""
import sqlite3

import pytest

from db_schema import SCHEMA
from orange_deck_data_schema import migrate_deck_data


# Minimal pre-0029 database, including cascading actors and a deleted high ID.
LEGACY = '''
CREATE TABLE users(id INTEGER PRIMARY KEY);
INSERT INTO users VALUES(1),(2);
CREATE TABLE lineups(id INTEGER PRIMARY KEY);
INSERT INTO lineups VALUES(1);
CREATE TABLE feedback_threads(id INTEGER PRIMARY KEY);
CREATE TABLE orange_decks(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL, season_id TEXT NOT NULL, status TEXT NOT NULL,
    plan_code TEXT NOT NULL, lineup_code TEXT NOT NULL, published_at TEXT
);
INSERT INTO orange_decks VALUES(7,1,'旧卡组','orange_s400001','published','旧方案','旧阵容','2026-01-01 00:00:00');
CREATE TABLE orange_deck_copies(
    deck_id INTEGER REFERENCES orange_decks(id), copy_key TEXT, bucket_start TEXT, created_at TEXT,
    PRIMARY KEY(deck_id,copy_key,bucket_start)
);
INSERT INTO orange_deck_copies VALUES(7,'user:2','2026-01-01 00:00:00','2026-01-01 00:00:01');
CREATE TABLE copy_action_events(
    id INTEGER PRIMARY KEY AUTOINCREMENT, target_type TEXT NOT NULL, target_id TEXT NOT NULL,
    lineup_id INTEGER REFERENCES lineups(id), live_comp_id TEXT, success INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
INSERT INTO copy_action_events VALUES(3,'lineup','1',1,NULL,1,'2026-01-01 00:00:00');
CREATE TABLE user_notifications(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL CHECK(kind IN ('feedback','like','favorite','copy')),
    group_key TEXT NOT NULL, lineup_id INTEGER REFERENCES lineups(id),
    feedback_id INTEGER REFERENCES feedback_threads(id) ON DELETE CASCADE,
    title TEXT NOT NULL, body TEXT NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 1 CHECK(event_count>0),
    read_count INTEGER NOT NULL DEFAULT 0 CHECK(read_count>=0),
    revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
    notice_state TEXT NOT NULL DEFAULT 'unread' CHECK(notice_state IN ('unread','read')),
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(user_id,group_key)
);
CREATE INDEX idx_user_notifications_inbox ON user_notifications(user_id,notice_state,updated_at DESC,id DESC);
CREATE TABLE notification_actors(
    notification_id INTEGER REFERENCES user_notifications(id) ON DELETE CASCADE,
    actor_user_id INTEGER REFERENCES users(id), updated_at TEXT,
    PRIMARY KEY(notification_id,actor_user_id)
);
INSERT INTO user_notifications VALUES(8,1,'like','like:1',1,NULL,'标题','正文',3,2,4,'unread','old','new');
INSERT INTO user_notifications VALUES(90,1,'copy','copy:1',1,NULL,'删除的通知','',1,0,1,'unread','old','new');
DELETE FROM user_notifications WHERE id=90;
INSERT INTO notification_actors VALUES(8,2,'new');
CREATE TABLE daily_admin_reports(report_date TEXT PRIMARY KEY,payload_json TEXT);
INSERT INTO daily_admin_reports VALUES('2026-01-01','{"successful_copies":1}');
CREATE TABLE app_settings(setting_key TEXT PRIMARY KEY,setting_value TEXT,updated_at TEXT);
'''


def legacy_database():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(LEGACY)
    return db


def submit(db, request='request-1', fingerprint='a' * 64, user=1):
    return db.execute('''INSERT INTO orange_deck_submissions
        (submitter_user_id,season_id,plan_code,lineup_code,code_fingerprint,request_key,created_at,updated_at)
        VALUES (?, 'orange_s400001', '方案-大橘大利-MQ==', '#ABC', ?, ?, 'now', 'now')''',
        (user, fingerprint, request)).lastrowid


def test_fresh_schema_and_restart_keep_foreign_keys_and_do_not_start_collection():
    db = sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SCHEMA)
    migrate_deck_data(db)
    migrate_deck_data(db)
    assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert not db.execute("SELECT 1 FROM app_settings WHERE setting_key='deck_analytics_started_at'").fetchone()


def test_legacy_upgrade_preserves_data_actors_indexes_and_sequence():
    db = legacy_database()
    tables = ('orange_decks','orange_deck_copies','copy_action_events','user_notifications',
              'notification_actors','daily_admin_reports')
    before = {table: [dict(r) for r in db.execute(f'SELECT * FROM {table}')] for table in tables}
    migrate_deck_data(db)
    migrate_deck_data(db)
    for table, rows in before.items():
        after = [dict(r) for r in db.execute(f'SELECT * FROM {table}')]
        assert len(after) == len(rows)
        for old, new in zip(rows, after):
            assert {key: new[key] for key in old} == old
    assert db.execute("SELECT seq FROM sqlite_sequence WHERE name='user_notifications'").fetchone()[0] == 90
    assert db.execute("SELECT 1 FROM sqlite_master WHERE name='idx_user_notifications_inbox'").fetchone()
    assert db.execute("SELECT origin_type,provided_by_user_id FROM orange_decks").fetchone()[:] == ('direct', None)
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_failed_rebuild_rolls_back_and_restores_foreign_keys():
    db = legacy_database()
    db.execute('ALTER TABLE user_notifications ADD COLUMN unknown_extension TEXT')
    with pytest.raises(RuntimeError, match='lossy'):
        migrate_deck_data(db)
    assert 'origin_type' not in {r[1] for r in db.execute('PRAGMA table_info(orange_decks)')}
    assert db.execute('SELECT COUNT(*) FROM notification_actors').fetchone()[0] == 1
    assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='user_notifications_deck_upgrade'").fetchone()


def test_upgrade_never_commits_caller_transaction():
    db = legacy_database()
    db.execute("UPDATE orange_decks SET name='未提交'")
    with pytest.raises(RuntimeError, match='idle'):
        migrate_deck_data(db)
    assert db.in_transaction
    db.rollback()
    assert db.execute('SELECT name FROM orange_decks').fetchone()[0] == '旧卡组'


def test_submission_idempotency_and_active_fingerprint_are_per_user():
    db = legacy_database()
    migrate_deck_data(db)
    first = submit(db)
    with pytest.raises(sqlite3.IntegrityError):
        submit(db, fingerprint='b' * 64)  # same request, different payload
    with pytest.raises(sqlite3.IntegrityError):
        submit(db, request='new-request')  # same active codes
    submit(db, user=2)  # another user's claim is not silently discarded
    db.execute("UPDATE orange_deck_submissions SET status='withdrawn',resolved_at='now' WHERE id=?", (first,))
    submit(db, request='retry-after-withdrawal')


@pytest.mark.parametrize('update', [
    "status='processing'", "status='published',resolved_at='now'",
    "status='duplicate',resolved_at='now'", "status='rejected'", "version=0",
    "lineup_code=''", "code_fingerprint='short'",
])
def test_submission_constraints_reject_incomplete_states(update):
    db = legacy_database()
    migrate_deck_data(db)
    submit(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f'UPDATE orange_deck_submissions SET {update}')


def test_notification_extension_accepts_submission_only_with_correct_target_shape():
    db = legacy_database()
    migrate_deck_data(db)
    sid = submit(db)
    sql = '''INSERT INTO user_notifications(user_id,kind,group_key,deck_submission_id,title,body,created_at,updated_at)
        VALUES(1,'deck_submission',?,?,'处理进度','已接收','now','now')'''
    notification = db.execute(sql, (f'deck_submission:{sid}', sid)).lastrowid
    assert notification > 90
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, ('invalid', None))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('UPDATE user_notifications SET lineup_id=1 WHERE id=?', (notification,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('UPDATE user_notifications SET deck_submission_id=? WHERE id=8', (sid,))
    assert db.execute('SELECT COUNT(*) FROM notification_actors').fetchone()[0] == 1


def test_distinct_visits_use_separate_nullable_library_index():
    db = legacy_database()
    migrate_deck_data(db)
    sql = '''INSERT INTO orange_deck_visit_events(visit_date,visitor_key,surface,deck_id,created_at)
        VALUES('2026-01-01','visitor:one',?,?,'2026-01-01 00:00:00')'''
    db.execute(sql, ('library', None))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, ('library', None))
    db.execute(sql, ('detail', 7))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, ('detail', 7))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, ('detail', None))
    assert db.execute('SELECT COUNT(*) FROM orange_deck_visit_events').fetchone()[0] == 2


def test_two_copy_types_have_distinct_actions_but_share_effective_bucket():
    db = legacy_database()
    migrate_deck_data(db)
    sql = '''INSERT INTO copy_action_events(target_type,target_id,deck_id,code_type,actor_key,
        client_action_id,rank_eligible,success,created_at)
        VALUES('orange_deck','7',7,?,'user:2',?,1,1,'2026-01-01 00:00:01')'''
    for kind in ('plan', 'lineup'):
        db.execute(sql, (kind, 'gesture-' + kind))
        db.execute("INSERT OR IGNORE INTO orange_deck_copies VALUES(7,'user:2','2026-01-01 00:00:00','now')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, ('plan', 'gesture-plan'))
    assert db.execute("SELECT COUNT(*) FROM copy_action_events WHERE target_type='orange_deck'").fetchone()[0] == 2
    assert db.execute('SELECT COUNT(*) FROM orange_deck_copies').fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE copy_action_events SET target_id='999' WHERE target_type='orange_deck'")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE copy_action_events SET success=0 WHERE target_type='orange_deck'")
