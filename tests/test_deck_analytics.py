"""Deck collection, copy counting rules, hot ranking and report figures."""
import uuid
from datetime import datetime, timedelta

import pytest

import orange_deck_service
from daily_report_service import build_daily_report_payload, ensure_daily_report, get_daily_report
from db import get_db
from test_deck_codes_permissions import CODE
from test_lineup_permissions import auth_headers
from test_orange_decks import LEGENDS, create, moderate, users  # noqa: F401  (fixture)

LINEUP = '#ABC123456789'


def copy(client, deck, code_type='plan', action_id=None):
    return client.post(f"/api/orange-decks/{deck['id']}/copy?code_type={code_type}",
                       json={'action_id': action_id or str(uuid.uuid4())}, headers=auth_headers(client))


def today_bounds():
    start = datetime.now().strftime('%Y-%m-%d')
    return start, (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')


def test_copy_actions_effective_copies_and_retries_are_separate(users, app, monkeypatch):
    owner, other, admin, guest = users
    monkeypatch.setattr('orange_deck_service.bucket_start', lambda: '2026-11-04 12:00:00')
    deck = create(owner, plan_code=CODE, lineup_code=LINEUP).json
    gesture = str(uuid.uuid4())
    first = copy(other, deck, 'plan', gesture)
    assert first.json == {'counted': True, 'copy_count': 1}
    # A network retry of the same gesture is answered from the first write, never counted again.
    assert copy(other, deck, 'plan', gesture).json == {'counted': True, 'copy_count': 1}
    # The other code in the same window is a second action but not a second effective copy.
    assert copy(other, deck, 'lineup').json == {'counted': False, 'copy_count': 1}
    # Reusing an action ID for something else is refused.
    assert copy(other, deck, 'lineup', gesture).status_code == 409
    assert copy(guest, deck, 'plan', gesture).status_code == 409
    assert copy(other, deck, 'plan', 'bad id!').status_code == 400
    # Old clients without an action ID still work.
    assert other.post(f"/api/orange-decks/{deck['id']}/copy", headers=auth_headers(other)).json['counted'] is False
    owner_copy = copy(owner, deck)
    assert owner_copy.json['counted'] is True
    with app.app_context():
        rows = get_db().execute('''SELECT code_type, actor_key, rank_eligible, counted, client_action_id FROM copy_action_events
            WHERE target_type = 'orange_deck' ORDER BY id''').fetchall()
        assert [(r['code_type'], r['rank_eligible'], r['counted']) for r in rows] == [
            ('plan', 1, 1), ('lineup', 1, 0), ('plan', 1, 0), ('plan', 0, 1)]  # the owner's own copy earns no weight
        assert rows[0]['actor_key'].startswith('user:') and rows[0]['client_action_id'] == gesture
        assert get_db().execute("SELECT setting_value FROM app_settings WHERE setting_key = 'deck_analytics_started_at'").fetchone()
        start, end = today_bounds()
        summary = build_daily_report_payload(get_db(), start)['summary']
        assert summary['deck_copy_actions'] == 4 and summary['deck_plan_copy_actions'] == 3 and summary['deck_lineup_copy_actions'] == 1
        assert summary['deck_effective_copies'] == 2 and summary['deck_copiers'] == 2
        # Lineup/live totals keep their meaning; deck copies are reported separately.
        assert summary['total_copies'] == 0


def test_activity_events_follow_real_changes_only(users, app):
    owner, other, admin, guest = users
    deck = create(owner).json
    for _ in range(2):
        other.post(f"/api/orange-decks/{deck['id']}/favorite", headers=auth_headers(other))
    for _ in range(2):
        other.delete(f"/api/orange-decks/{deck['id']}/favorite", headers=auth_headers(other))
    other.post(f"/api/orange-decks/{deck['id']}/like", headers=auth_headers(other))
    hidden = moderate(admin, deck, 'hide', reason='复核隐藏').json
    restored = moderate(admin, hidden, 'restore').json
    reviewed = moderate(admin, restored, 'review')
    assert reviewed.status_code == 200
    edited = owner.put(f"/api/orange-decks/{deck['id']}", json={'name': '改名', 'portal': 'stable', 'cards': [c['id'] for c in deck['cards']],
                                                               'version': reviewed.json['version']}, headers=auth_headers(owner))
    assert edited.status_code == 200
    draft = create(owner, action='draft').json
    owner.delete(f"/api/orange-decks/{draft['id']}", headers=auth_headers(owner))
    owner.delete(f"/api/orange-decks/{deck['id']}", headers=auth_headers(owner))
    with app.app_context():
        actions = [r['action'] for r in get_db().execute('SELECT action FROM orange_deck_activity_events ORDER BY id').fetchall()]
    # Edits and repeated favorite requests are not events; deleting a private draft is not a public deletion.
    assert actions == ['published', 'favorite_add', 'favorite_remove', 'like', 'hidden', 'restored', 'reviewed', 'deleted']


def test_visits_are_daily_distinct_and_skip_admins_bots_and_prefetch(users, app):
    owner, other, admin, guest = users
    deck = create(owner).json
    guest.get('/')  # receives a visitor cookie
    for _ in range(2):
        assert guest.get(f"/orange-decks/{deck['id']}").status_code == 200
        guest.post('/api/orange-decks/visits', json={'surface': 'library'}, headers=auth_headers(guest))
    other.get(f"/orange-decks/{deck['id']}", headers={'Sec-Purpose': 'prefetch'})
    other.get(f"/orange-decks/{deck['id']}", headers={'User-Agent': 'Googlebot'})
    admin.get(f"/orange-decks/{deck['id']}")
    admin.post('/api/orange-decks/visits', json={'surface': 'library'}, headers=auth_headers(admin))
    assert guest.post('/api/orange-decks/visits', json={'surface': 'detail'}, headers=auth_headers(guest)).status_code == 400
    draft = create(owner, action='draft').json
    owner.get(f"/orange-decks/{draft['id']}")
    with app.app_context():
        rows = get_db().execute('SELECT surface, deck_id, visitor_key FROM orange_deck_visit_events ORDER BY id').fetchall()
        assert [(r['surface'], r['deck_id']) for r in rows] == [('detail', deck['id']), ('library', None)]
        summary = build_daily_report_payload(get_db(), today_bounds()[0])['summary']
        assert summary['deck_library_visitors'] == 1 and summary['deck_detail_visitors'] == 1 and summary['deck_detail_visits'] == 1


def test_hot_cold_start_filters_and_consistent_pages(users, app, monkeypatch):
    owner, other, admin, guest = users
    decks = [create(owner, name=f'卡组{i}').json for i in range(5)]
    over = create(owner, name='超限', cards=LEGENDS, portal='unknown').json
    hidden = create(owner, name='隐藏').json
    moderate(admin, hidden, 'hide', reason='测试隐藏')
    create(owner, name='草稿', action='draft')
    with app.app_context():
        # A deck whose portal limit no longer fits under current data, and one from an old card season.
        get_db().execute("UPDATE orange_decks SET portal_id = 'stable' WHERE id = ?", (over['id'],))
        get_db().execute("UPDATE orange_decks SET season_id = 'orange_s1' WHERE id = ?", (decks[0]['id'],))
        get_db().commit()
    first = guest.get('/api/orange-decks?tab=hot&page_size=2').json
    assert first['total'] == 4 and first['total_pages'] == 2
    pages = [guest.get(f'/api/orange-decks?tab=hot&page_size=2&page={n}').json for n in (1, 2)]
    ids = [d['id'] for page in pages for d in page['items']]
    assert len(ids) == 4 and len(set(ids)) == 4
    assert set(ids) == {d['id'] for d in decks[1:]}
    # Featured keeps its own manual meaning.
    assert guest.get('/api/orange-decks?tab=featured').json['total'] == 0
    # Hiding takes effect immediately even with a warm signal cache.
    moderate(admin, guest.get(f"/api/orange-decks/{decks[1]['id']}").json, 'hide', reason='立即生效')
    assert decks[1]['id'] not in [d['id'] for d in guest.get('/api/orange-decks?tab=hot&page_size=10').json['items']]


def test_hot_uses_decayed_daily_signals_and_excludes_self_interest(users, app):
    owner, other, admin, guest = users
    older = create(owner, name='老卡组', plan_code=CODE, lineup_code=LINEUP).json
    newer = create(owner, name='新卡组').json
    third = create(owner, name='第三').json
    # Copying both codes is one daily signal; repeats and the owner's own copies add nothing.
    copy(other, older, 'plan'); copy(other, older, 'lineup'); copy(other, older, 'plan')
    copy(owner, older, 'plan'); copy(admin, older, 'plan')
    with app.app_context():
        long_ago = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
        week_ago = (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S')
        get_db().execute('UPDATE orange_decks SET published_at = ? WHERE id = ?', (week_ago, older['id']))
        get_db().execute('UPDATE orange_decks SET published_at = ? WHERE id = ?', (long_ago, third['id']))
        get_db().commit()
        ranked = orange_deck_service.hot_ranking(get_db(), "FROM orange_decks d WHERE d.status = 'published'", [])
        scores = orange_deck_service._signals(get_db(), datetime.now())
    assert scores == {older['id']: pytest.approx(3.0)}
    assert ranked == [older['id'], newer['id'], third['id']]
    # A signal from outside the 30-day window no longer counts.
    with app.app_context():
        get_db().execute("UPDATE copy_action_events SET created_at = ? WHERE target_type = 'orange_deck'", (long_ago,))
        get_db().commit()
        orange_deck_service._signal_cache.clear()  # a direct backdate is not a new event, so drop the cached aggregate
        assert orange_deck_service._signals(get_db(), datetime.now()) == {}


def test_identical_card_sets_step_back(users, app):
    owner, other, admin, guest = users
    a = create(owner, name='组合A').json
    b = create(owner, name='组合A副本').json
    c = create(owner, name='不同组合', cards=LEGENDS, portal='unknown').json
    with app.app_context():
        get_db().execute("UPDATE orange_decks SET published_at = '2026-01-01 00:00:00'")
        get_db().commit()
        ranked = orange_deck_service.hot_ranking(get_db(), "FROM orange_decks d WHERE d.status = 'published'", [],
                                                 now=datetime(2026, 1, 1, 1))
    # Same score for all three; the repeated combination is damped below the different one.
    assert ranked.index(c['id']) < max(ranked.index(a['id']), ranked.index(b['id']))


def test_report_marks_uncollected_and_partial_days_and_reads_old_snapshots(users, app):
    owner, other, admin, guest = users
    with app.app_context():
        db = get_db()
        # Before collection starts, behaviour figures are unknown rather than zero.
        payload = build_daily_report_payload(db, '2026-01-01')
        assert payload['deck_coverage']['status'] == 'not_collected'
        assert payload['summary']['deck_copy_actions'] is None and payload['summary']['deck_submissions_new'] == 0
        assert payload['payload_version'] == 2
        # An old v1 snapshot is served as stored, without deck keys being invented.
        db.execute('''INSERT INTO daily_admin_reports (report_date, unique_visitors, page_visits, successful_copies, payload_json, generated_at, updated_at)
                      VALUES ('2025-12-31', 1, 1, 0, '{"summary": {"unique_visitors": 1}}', '2026-01-01 00:00:00', '2026-01-01 00:00:00')''')
        db.commit()
        old = get_daily_report('2025-12-31')
        assert 'deck_copy_actions' not in old['summary'] and 'deck_coverage' not in old
    create(owner)  # first collected event
    with app.app_context():
        db = get_db()
        started = db.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'deck_analytics_started_at'").fetchone()[0]
        cover = build_daily_report_payload(db, started[:10])['deck_coverage']
        assert cover['status'] == 'partial' and cover['from'] == started
        report = ensure_daily_report(started[:10], force=True)
        assert report['summary']['deck_published'] == 1 and report['deck_snapshot']['public_decks'] == 1


def test_overview_and_copy_rank_label_deck_targets(users, app):
    owner, other, admin, guest = users
    deck = create(owner, plan_code=CODE).json
    copy(other, deck)
    overview = admin.get('/api/admin/overview').json
    assert overview['deck']['deck_copy_actions'] == 1 and overview['deck']['deck_effective_copies'] == 1
    assert overview['todos']['deck_submissions_pending'] == 0
    rank = admin.get('/api/admin/copy-rank').json
    item = next(i for i in rank['items'] if i['target_type'] == 'orange_deck')
    assert item['title'] == deck['name'] and item['season_name'] == '大橘大利卡组'
    assert item['details'][0]['code'] == CODE and item['details'][0]['code_type'] == 'plan'


def test_legacy_interaction_notifications_still_serialize(users, app):
    owner, other, admin, guest = users
    lineup = owner.post('/api/lineups', json={'name': '阵容A', 'code': '#CODE123', 'status': 'normal', 'season_id': 's17-star-god'},
                        headers=auth_headers(owner)).json
    lineup_id = lineup.get('id') or lineup.get('lineup', {}).get('id')
    other.post(f'/api/lineups/{lineup_id}/favorite', headers=auth_headers(other))
    inbox = owner.get('/api/me/notifications').json
    assert inbox['items'][0]['kind'] == 'favorite' and inbox['items'][0]['category'] == 'interaction'
    assert inbox['items'][0]['url'] == f'/lineup/{lineup_id}' and inbox['items'][0]['deck_submission_id'] is None
    assert owner.get('/api/me/notifications?category=submission').json['total'] == 0
