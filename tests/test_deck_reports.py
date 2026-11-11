"""Deck figures in hot ranking, the admin overview, copy rank and daily reports, kept apart from lineup codes."""
from datetime import datetime, timedelta

from db import get_db
from orange_deck_service import compute_hot_scores
from test_deck_codes_permissions import CODE
from test_lineup_permissions import auth_headers
from test_orange_decks import LEGENDS, create, moderate, users  # noqa: F401 - fixture

LINEUP = '#DECKREPORT123'


def copy(client, deck, code_type, source):
    return client.post(f"/api/orange-decks/{deck['id']}/copy?code_type={code_type}&source={source}", headers=auth_headers(client))


def seeded(users):
    owner, other, admin, guest = users
    deck = create(owner, name='报告卡组', plan_code=CODE, lineup_code=LINEUP).json
    quiet = create(owner, name='安静卡组', cards=LEGENDS, portal='unknown').json
    assert copy(other, deck, 'plan', 'home').json['counted'] is True
    assert copy(other, deck, 'lineup', 'detail').json['counted'] is False  # same five-minute window
    assert copy(guest, deck, 'lineup', 'detail').json['counted'] is True
    other.post(f"/api/orange-decks/{deck['id']}/like", headers=auth_headers(other))
    other.post(f"/api/orange-decks/{deck['id']}/favorite", headers=auth_headers(other))
    return deck, quiet


def test_overview_and_copy_rank_report_decks_separately(users, app):
    owner, other, admin, guest = users
    deck, quiet = seeded(users)
    assert moderate(admin, quiet, 'hide', reason='报告验收').status_code == 200
    overview = admin.get('/api/admin/overview').json
    stats = overview['stats']
    assert (stats['today_deck_copy_count'], stats['today_deck_plan_copy_count'], stats['today_deck_lineup_copy_count']) == (2, 1, 1)
    assert (stats['today_new_decks'], stats['today_deck_likes'], stats['today_deck_favorites'], stats['published_decks']) == (2, 1, 1, 1)
    # Lineup-code totals are untouched by deck copies.
    assert stats['today_total_copy_count'] == 0
    assert overview['todos']['hidden_decks_count'] == 1
    rank = admin.get('/api/admin/copy-rank').json
    assert rank['items'] == []
    [item] = rank['deck_items']
    assert (item['title'], item['copies'], item['plan_copies'], item['lineup_copies'], item['counted_copies'], item['unique_visitors']) == (
        '报告卡组', 3, 1, 2, 2, 2)
    assert item['plan_code'] == CODE and item['lineup_code'] == LINEUP and len(item['cards']) == 3
    assert [(event['code_type'], event['source_page'], event['counted']) for event in item['details']] == [
        ('lineup', 'detail', True), ('lineup', 'detail', False), ('plan', 'home', True)]
    assert admin.get('/api/admin/stats').json['today_deck_copy_count'] == 2


def test_daily_report_includes_deck_summary_hourly_and_ranking(users, app):
    deck, _ = seeded(users)
    today = datetime.now().strftime('%Y-%m-%d')
    with app.app_context():
        from daily_report_service import ensure_daily_report
        report = ensure_daily_report(today, force=True)
    summary = report['summary']
    assert (summary['deck_copies'], summary['deck_plan_copies'], summary['deck_lineup_copies'], summary['deck_copy_visitors']) == (3, 1, 2, 2)
    assert (summary['new_decks'], summary['deck_like_actions'], summary['deck_favorite_actions']) == (2, 1, 1)
    assert summary['total_copies'] == 0 and report['top_copied'] == [] and report['season_copy_rank'] == []
    assert sum(report['hourly']['deck_copies']) == 3 and sum(report['hourly']['copies']) == 0
    [item] = report['top_copied_decks']
    assert item['deck_id'] == str(deck['id']) and item['copies'] == 3 and 'details' not in item


def test_hot_score_weights_decay_self_interactions_and_author_damping(app):
    now = datetime(2026, 11, 11, 12, 0, 0)
    day = lambda offset: (now - timedelta(days=offset)).strftime('%Y-%m-%d %H:%M:%S')
    with app.app_context():
        db = get_db()
        ids = {}
        for username in ('alice', 'bob', 'carol'):
            db.execute("INSERT INTO users (username, email, nickname, password_hash, role, status, created_at, updated_at) "
                       "VALUES (?, ?, ?, 'x', 'user', 'active', ?, ?)", (username, f'{username}@example.com', username, day(30), day(30)))
            ids[username] = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()['id']

        def deck(name, owner, published):
            db.execute("INSERT INTO orange_decks (user_id, name, portal_id, card_version, status, card_id_1, card_id_2, card_id_3, "
                       "created_at, updated_at, published_at) VALUES (?, ?, 'stable', 'v', 'published', 'a', 'b', 'c', ?, ?, ?)",
                       (ids[owner], name, day(published), day(published), day(published)))
            return db.execute('SELECT id FROM orange_decks WHERE name = ?', (name,)).fetchone()['id']

        recent, stale, selfish, newcomer = deck('近期', 'alice', 20), deck('过气', 'bob', 20), deck('自刷', 'carol', 20), deck('新卡组', 'bob', 0)
        rows = [(recent, f'ip:{n}', day(1)) for n in range(3)]           # 3 copies yesterday
        rows += [(stale, f'ip:{n}', day(28)) for n in range(5)]           # 5 copies four weeks ago
        rows += [(selfish, f"user:{ids['carol']}", day(n)) for n in range(5)]  # the author's own copies
        db.executemany('INSERT INTO orange_deck_copies (deck_id, copy_key, bucket_start, created_at) VALUES (?, ?, ?, ?)',
                       [(*row, row[2]) for row in rows])
        scores = compute_hot_scores(db, now=now)
    assert scores[recent]['score'] > scores[stale]['score'] > scores[selfish]['score']
    assert scores[recent]['recent_interactions'] == 3 and scores[selfish]['recent_interactions'] == 0
    # The brand-new deck gets the full fresh boost; bob's other (lower) deck is damped by 0.8.
    assert scores[newcomer]['score'] == 2.0
    assert scores[stale]['score'] == round((5 * 3 * 0.5 ** 4 + 2 * 0.5 ** (20 / 3)) * 0.8, 3)
