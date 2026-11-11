from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from db import get_db
from orange_deck_service import record_copy
from test_deck_codes_permissions import CODE
from test_lineup_permissions import auth_headers
from test_orange_decks import users, create, moderate


def test_copy_counts_persist_and_share_lineup_dedup_rules(users, app, monkeypatch):
    owner, other, _, guest = users
    monkeypatch.setattr('orange_deck_service.bucket_start', lambda: '2026-11-04 12:00:00')
    deck = create(owner, plan_code=CODE).json
    assert deck['copy_count'] == 0
    url = f"/api/orange-decks/{deck['id']}"
    guest_headers = auth_headers(guest)
    first = guest.post(url + '/copy', headers=guest_headers)
    assert first.status_code == 200 and first.json == {'counted': True, 'copy_count': 1}
    assert first.headers['Cache-Control'] == 'private, no-store'
    for source in ('home', 'detail', 'account'):
        assert guest.post(url + '/copy?source=' + source, headers=guest_headers).json == {'counted': False, 'copy_count': 1}
    second_guest = app.test_client()
    assert second_guest.post(url + '/copy', headers=auth_headers(second_guest)).json['counted'] is False
    assert other.post(url + '/copy', headers=auth_headers(other)).json == {'counted': True, 'copy_count': 2}
    assert owner.post(url + '/copy', headers=auth_headers(owner)).json == {'counted': True, 'copy_count': 3}
    monkeypatch.setattr('orange_deck_service.bucket_start', lambda: '2026-11-04 12:05:00')
    assert guest.post(url + '/copy', headers=guest_headers).json == {'counted': True, 'copy_count': 4}
    assert guest.get(url).json['copy_count'] == 4
    assert guest.get('/api/orange-decks').json['items'][0]['copy_count'] == 4
    assert owner.get('/api/orange-decks?tab=mine').json['items'][0]['copy_count'] == 4
    # Copies feed deck heat but never ordinary-lineup totals; every copy action is logged with its code type.
    hot = guest.get('/api/orange-decks?tab=hot').json
    assert hot['total'] == 1 and hot['items'][0]['hot']['rank'] == 1
    with app.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM copy_events').fetchone()[0] == 0
        actions = db.execute("SELECT code_type, counted, source_page FROM copy_action_events "
                             "WHERE target_type = 'orange_deck' ORDER BY id").fetchall()
        assert [tuple(row) for row in actions][:4] == [('plan', 1, ''), ('plan', 0, 'home'), ('plan', 0, 'detail'), ('plan', 0, 'account')]
        assert sum(row['counted'] for row in actions) == 4
    another = create(owner, plan_code=CODE).json
    assert another['copy_count'] == 0
    assert guest.post(f"/api/orange-decks/{another['id']}/copy", headers=guest_headers).json['copy_count'] == 1


def test_copy_requires_csrf_public_deck_and_plan_code(users, app):
    owner, _, admin, guest = users
    deck = create(owner, plan_code=CODE).json
    url = f"/api/orange-decks/{deck['id']}/copy"
    assert app.test_client().post(url).status_code == 403
    assert owner.post(url).status_code == 403
    headers = auth_headers(guest)
    no_code = create(owner).json
    assert guest.post(f"/api/orange-decks/{no_code['id']}/copy", headers=headers).status_code == 400
    draft = create(owner, action='draft', plan_code=CODE).json
    draft_url = f"/api/orange-decks/{draft['id']}/copy"
    assert guest.post(draft_url, headers=headers).status_code == 404
    assert owner.post(draft_url, headers=auth_headers(owner)).status_code == 409
    assert moderate(admin, deck, 'hide', reason='验收隐藏').status_code == 200
    assert guest.post(url, headers=headers).status_code == 404
    assert owner.post(url, headers=auth_headers(owner)).status_code == 409
    assert owner.delete(f"/api/orange-decks/{deck['id']}", headers=auth_headers(owner)).status_code == 204
    assert owner.post(url, headers=auth_headers(owner)).status_code == 404
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM orange_deck_copies').fetchone()[0] == 0


@pytest.mark.parametrize('code_types', [('plan',) * 4, ('lineup',) * 4, ('plan', 'lineup') * 2])
def test_concurrent_copy_requests_are_deduplicated(users, app, monkeypatch, code_types):
    deck = create(users[0], plan_code=CODE, lineup_code='#CONCURRENT123').json
    monkeypatch.setattr('orange_deck_service.bucket_start', lambda: '2026-11-04 12:00:00')
    barrier = Barrier(4)
    def copy_once(code_type):
        with app.test_request_context('/'):
            barrier.wait(timeout=10)
            return record_copy(None, deck['id'], '192.0.2.1', code_type)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(copy_once, code_types))
    assert sum(r['counted'] for r in results) == 1
    assert all(r['copy_count'] == 1 for r in results)
