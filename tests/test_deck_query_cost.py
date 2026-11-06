"""Bound SQL work with SQLite VM steps instead of machine-dependent timing."""
import sqlite3

import pytest

import orange_deck_service as decks
from orange_deck_schema import ORANGE_DECK_SCHEMA


@pytest.fixture()
def populated_db(monkeypatch):
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, nickname TEXT, role TEXT,
                           avatar_color TEXT, avatar_preset TEXT, avatar_expression TEXT);
        INSERT INTO users VALUES(1,'demo','demo','user',NULL,NULL,NULL);
    """ + ORANGE_DECK_SCHEMA)
    db.executemany("""
        INSERT INTO orange_decks(id,user_id,name,portal_id,card_version,status,card_id_1,card_id_2,card_id_3,
                                 created_at,updated_at,published_at,lineup_code)
        VALUES(?,1,'demo','stable','v','published','1','2','3','now','now','now','#ABC123')
    """, ((i,) for i in range(1, 501)))
    db.executemany("INSERT INTO orange_deck_copies VALUES(?,?,?,?)",
                   ((i, f'guest:{j}', 'old bucket', 'now') for i in range(1, 501) for j in range(100)))
    db.execute("INSERT INTO orange_deck_favorites VALUES(1,1,'now')")
    db.execute("INSERT INTO orange_deck_likes(user_id,deck_id,like_date,created_at) VALUES(1,2,?,'now')", (decks.today(),))
    db.commit()
    monkeypatch.setattr(decks, 'get_db', lambda: db)
    # These tests isolate query work; full serialization is exercised by API tests.
    monkeypatch.setattr(decks, 'serialize', lambda row, *args, **kwargs: dict(row))
    yield db
    db.close()


def bounded(db, call):
    steps = 0

    def progress():
        nonlocal steps
        steps += 1000
        return steps > 50000

    db.set_progress_handler(progress, 1000)
    try:
        return call()
    finally:
        db.set_progress_handler(None, 0)


def test_detail_does_not_scan_unrelated_copy_history(populated_db):
    row = bounded(populated_db, lambda: decks.deck_row(1, {'id': 1}))
    assert row['copy_count'] == 100 and row['favorite_count'] == 1 and row['is_favorited'] == 1


def test_latest_count_and_page_only_count_displayed_decks(populated_db):
    result = bounded(populated_db, lambda: decks.list_decks(None, page_size=10))
    assert result['total'] == 500
    assert [row['id'] for row in result['items']] == list(range(500, 490, -1))
    assert all(row['copy_count'] == 100 for row in result['items'])


def test_copy_endpoint_does_not_read_unrelated_copy_history(populated_db):
    result = bounded(populated_db, lambda: decks.record_copy(None, 1, '192.0.2.1', 'lineup'))
    assert result == {'counted': True, 'copy_count': 101}
    assert bounded(populated_db, lambda: decks.record_copy(None, 1, '192.0.2.1', 'lineup')) == {
        'counted': False, 'copy_count': 101}


def test_hot_ranking_ignores_copy_volume_and_preserves_viewer_counts(populated_db):
    result = bounded(populated_db, lambda: decks.list_decks({'id': 1}, tab='hot'))
    assert result['total'] == 2
    assert [row['id'] for row in result['items']] == [2, 1]
    assert result['items'][0]['is_liked_today'] == 1
    assert result['items'][1]['is_favorited'] == 1
