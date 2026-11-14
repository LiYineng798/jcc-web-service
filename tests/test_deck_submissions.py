"""Submission flow: two codes from a user, completion and publication by an admin."""
import json
import uuid

import pytest

import deck_submission_service
from db import get_db
from test_admin import login_admin
from test_auth import register_user
from test_deck_codes_permissions import CODE
from test_lineup_permissions import auth_headers
from test_orange_decks import LIGHT, deck_body

LINEUP = '【阵容码】#投稿阵容#ABC123456789'
OTHER_CODE = '轻装稳定-大橘大利-MTIzNDU2Nzg5MA=='


@pytest.fixture()
def people(app):
    alice, bob, admin, admin2 = (app.test_client() for _ in range(4))
    assert register_user(alice).status_code == 201
    assert register_user(bob, username='bob', email='bob@example.com', nickname='Bob').status_code == 201
    assert register_user(admin2, username='carol', email='carol@example.com', nickname='Carol').status_code == 201
    with app.app_context():
        get_db().execute("UPDATE users SET role = 'admin' WHERE username = 'carol'")
        get_db().commit()
    login_admin(admin)
    return alice, bob, admin, admin2


def submit(client, key=None, **overrides):
    body = {'request_key': key or str(uuid.uuid4()), 'plan_code': CODE, 'lineup_code': LINEUP, **overrides}
    return client.post('/api/deck-submissions', json=body, headers=auth_headers(client))


def act(client, submission, action, **extra):
    return client.post(f"/api/admin/deck-submissions/{submission['id']}/{action}",
                       json={'version': submission['version'], **extra}, headers=auth_headers(client))


def editor_fields(**overrides):
    body = deck_body(name='投稿完善', cards=LIGHT)
    body.pop('action')
    return {**body, **overrides}


def claim(admin, submission):
    response = act(admin, submission, 'claim')
    assert response.status_code == 200, response.json
    return response.json


def user_id(app, username):
    with app.app_context():
        return get_db().execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()['id']


def test_submit_requires_login_csrf_and_both_valid_codes(people, app):
    alice, *_ = people
    guest = app.test_client()
    assert submit(guest).status_code in (401, 403)
    assert alice.post('/api/deck-submissions', json={'request_key': str(uuid.uuid4()), 'plan_code': CODE, 'lineup_code': LINEUP}).status_code == 403
    for overrides, message in [({'plan_code': ''}, '方案码'), ({'lineup_code': ''}, '阵容码'),
                               ({'plan_code': 'not-a-code'}, '方案码格式'), ({'lineup_code': '没有编码'}, '阵容码'),
                               ({'name': '名' * 25}, '最多 24 字'), ({'request_key': 'nope'}, '提交标识')]:
        response = submit(alice, **overrides)
        assert response.status_code == 400 and message in response.json['error'], overrides
    created = submit(alice, name='三传说', note='后期很强')
    assert created.status_code == 201
    data = created.json
    assert data['status'] == 'pending' and data['lineup_code'] == '#ABC123456789' and data['version'] == 1
    assert data['replayed'] is False and created.headers['Cache-Control'] == 'private, no-store'
    # A submission never enters the public library by itself.
    assert alice.get('/api/orange-decks').json['total'] == 0
    with app.app_context():
        events = get_db().execute('SELECT action, from_status, to_status, submission_version FROM orange_deck_submission_events').fetchall()
        assert [tuple(e) for e in events] == [('submit', None, 'pending', 1)]


def test_retries_and_duplicate_codes_get_clear_answers(people, app):
    alice, bob, *_ = people
    key = str(uuid.uuid4())
    first = submit(alice, key=key, name='一号')
    replay = submit(alice, key=key, name='一号')
    assert first.status_code == 201 and replay.status_code == 200
    assert replay.json['id'] == first.json['id'] and replay.json['replayed'] is True
    conflict = submit(alice, key=key, name='另一个')
    assert conflict.status_code == 409 and conflict.json['submission_id'] == first.json['id']
    # Same codes with a different name/plan label are the same codes (the label is not part of the fingerprint).
    again = submit(alice, plan_code='别的名字-大橘大利-' + CODE.rpartition('-大橘大利-')[2])
    assert again.status_code == 409 and again.json['submission_id'] == first.json['id']
    # Another user may submit the same codes; attribution is decided by an admin, never transferred.
    assert submit(bob).status_code == 201
    assert submit(alice, plan_code=OTHER_CODE).status_code == 201


def test_submitter_edits_and_withdraws_only_while_waiting(people, app):
    alice, bob, admin, _ = people
    sub = submit(alice, name='初稿').json
    url = f"/api/me/deck-submissions/{sub['id']}"
    assert bob.get(url).status_code == 404 and bob.put(url, json={'version': 1}, headers=auth_headers(bob)).status_code == 404
    updated = alice.put(url, json={'version': 1, 'name': '改名', 'note': '补充说明'}, headers=auth_headers(alice))
    assert updated.status_code == 200 and updated.json['version'] == 2 and updated.json['status'] == 'pending'
    assert alice.put(url, json={'version': 1, 'name': '旧页面'}, headers=auth_headers(alice)).status_code == 409
    claimed = claim(admin, {**sub, 'version': 2})
    blocked = alice.put(url, json={'version': claimed['version'], 'name': '覆盖'}, headers=auth_headers(alice))
    assert blocked.status_code == 409 and '管理员正在处理' in blocked.json['error']
    assert alice.post(url + '/withdraw', json={'version': claimed['version']}, headers=auth_headers(alice)).status_code == 409
    asked = act(admin, claimed, 'request_info', note='请补充关键回合')
    assert asked.status_code == 200 and asked.json['status'] == 'needs_info'
    detail = alice.get(url).json
    assert detail['review_note'] == '请补充关键回合' and detail['can_edit']
    assert [e['action'] for e in detail['events']] == ['submit', 'update', 'claim', 'request_info']
    assert all(e['actor'] in ('我', '管理员') for e in detail['events'])  # no admin identities for the user
    resubmitted = alice.put(url, json={'version': detail['version'], 'note': '2-1 拿装备'}, headers=auth_headers(alice)).json
    assert resubmitted['status'] == 'pending'
    withdrawn = alice.post(url + '/withdraw', json={'version': resubmitted['version']}, headers=auth_headers(alice))
    assert withdrawn.status_code == 200 and withdrawn.json['status'] == 'withdrawn' and withdrawn.json['resolved_at']
    page = alice.get(f"/me/deck-submissions/{sub['id']}")
    assert page.status_code == 200 and page.headers['Cache-Control'] == 'private, no-store'
    assert 'noindex' in page.get_data(as_text=True)
    assert bob.get(f"/me/deck-submissions/{sub['id']}").status_code == 404


def test_admin_claim_assign_and_assignee_only_actions(people, app):
    alice, bob, admin, admin2 = people
    sub = submit(alice).json
    assert act(alice, sub, 'claim').status_code == 403
    claimed = claim(admin, sub)
    assert act(admin2, sub, 'claim').status_code == 409  # stale version
    other = act(admin2, claimed, 'reject', note='不是我的')
    assert other.status_code == 409 and '正由' in other.json['error']
    carol = user_id(app, 'carol')
    assigned = act(admin, claimed, 'assign', admin_id=carol)
    assert assigned.status_code == 200 and assigned.json['assignee']['id'] == carol
    assert act(admin, assigned.json, 'release').status_code == 409
    released = act(admin2, assigned.json, 'release')
    assert released.status_code == 200 and released.json['status'] == 'pending' and released.json['assignee'] is None
    queue = admin.get('/api/admin/deck-submissions?status=pending').json
    assert queue['counts']['pending'] == 1 and queue['items'][0]['id'] == sub['id']
    assert alice.get('/api/admin/deck-submissions').status_code == 403


def test_draft_is_reused_and_publish_credits_the_submitter(people, app):
    alice, bob, admin, admin2 = people
    sub = claim(admin, submit(alice, name='用户起名', note='用户说明').json)
    draft_url = f"/api/admin/deck-submissions/{sub['id']}/draft"
    first = admin.put(draft_url, json={'version': sub['version'], **editor_fields(cards=[LIGHT[0], None, None])}, headers=auth_headers(admin))
    assert first.status_code == 200, first.json
    deck = first.json['deck_detail']
    assert deck['status'] == 'draft' and deck['plan_code'] == CODE and deck['lineup_code'] == '#ABC123456789'
    stale = admin.put(draft_url, json={'version': sub['version'], **editor_fields()}, headers=auth_headers(admin))
    assert stale.status_code == 409
    second = admin.put(draft_url, json={'version': first.json['version'], 'deck_version': deck['version'], **editor_fields()},
                       headers=auth_headers(admin)).json
    assert second['deck_detail']['id'] == deck['id']
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM orange_decks WHERE origin_type = 'submission'").fetchone()[0] == 1
    # The draft is private: not in public lists, not editable by the submitter, not in the admin's own "mine".
    assert bob.get(f"/api/orange-decks/{deck['id']}").status_code == 404
    assert alice.get(f"/api/orange-decks/{deck['id']}").status_code == 404
    assert admin.get('/api/orange-decks?tab=mine').json['total'] == 0
    locked = admin.put(f"/api/orange-decks/{deck['id']}", json={**editor_fields(), 'action': 'save', 'version': second['deck_detail']['version']},
                       headers=auth_headers(admin))
    assert locked.status_code == 409
    assert admin.get(f"/orange-decks/{deck['id']}/edit").headers['Location'].endswith(f"/admin/deck-submissions/{sub['id']}/edit")
    published = admin.post(f"/api/admin/deck-submissions/{sub['id']}/publish",
                           json={'version': second['version'], 'deck_version': second['deck_detail']['version'], **editor_fields(),
                                 'review_note': '感谢投稿'}, headers=auth_headers(admin))
    assert published.status_code == 200, published.json
    assert published.json['status'] == 'published' and published.json['resolved_at']
    public = bob.get(f"/api/orange-decks/{deck['id']}").json
    assert public['status'] == 'published' and public['author']['nickname'] == 'Alice' and public['author']['credit'] == 'provided'
    assert not public['can_edit'] and not alice.get(f"/api/orange-decks/{deck['id']}").json['can_edit']
    with app.app_context():
        row = get_db().execute('SELECT user_id, provided_by_user_id, published_by_user_id, origin_type, reviewed_at FROM orange_decks WHERE id = ?',
                               (deck['id'],)).fetchone()
        admin_id = get_db().execute("SELECT id FROM users WHERE username = 'adminxlx'").fetchone()['id']
        assert (row['user_id'], row['provided_by_user_id'], row['published_by_user_id'], row['origin_type']) == (
            admin_id, user_id(app, 'alice'), admin_id, 'submission')
        assert row['reviewed_at']
        assert get_db().execute("SELECT COUNT(*) FROM orange_deck_activity_events WHERE action = 'published'").fetchone()[0] == 1
        assert get_db().execute("SELECT COUNT(*) FROM audit_logs WHERE action = 'deck_submission.publish'").fetchone()[0] == 1
    detail = alice.get(f"/api/me/deck-submissions/{sub['id']}").json
    assert detail['deck']['detail_url'] == f"/orange-decks/{deck['id']}" and detail['review_note'] == '感谢投稿'
    assert public['note'] == editor_fields()['note']  # the deck description is not the reviewer's message
    # Contributions show in the submitter's deck list and summary; the submitter still cannot edit or delete.
    mine = alice.get('/api/orange-decks?tab=mine').json
    assert [d['id'] for d in mine['items']] == [deck['id']]
    assert alice.get('/api/me/dashboard').json['decks']['contributed_decks'] == 1
    assert alice.put(f"/api/orange-decks/{deck['id']}", json={**editor_fields(), 'version': public['version']}, headers=auth_headers(alice)).status_code == 403
    assert alice.delete(f"/api/orange-decks/{deck['id']}", headers=auth_headers(alice)).status_code == 403
    # Another admin may maintain the managed public deck through the normal editor, without withdrawing it.
    edited = admin2.put(f"/api/orange-decks/{deck['id']}", json={**editor_fields(name='管理员修订'), 'action': 'save', 'version': public['version']},
                        headers=auth_headers(admin2))
    assert edited.status_code == 200 and edited.json['status'] == 'published'
    assert admin2.put(f"/api/orange-decks/{deck['id']}", json={**editor_fields(), 'action': 'draft', 'version': edited.json['version']},
                      headers=auth_headers(admin2)).status_code == 409


def test_publish_revalidates_current_rules(people, app):
    alice, bob, admin, _ = people
    sub = claim(admin, submit(alice).json)
    url = f"/api/admin/deck-submissions/{sub['id']}/publish"
    for overrides, message in [({'cards': LIGHT[:2]}, '三张'), ({'name': ''}, '名称'), ({'portal': 'nowhere'}, '传送门'),
                               ({'cards': ['7250010', '7250011', '7250013'], 'portal': 'stable'}, '超出')]:
        response = admin.post(url, json={'version': sub['version'], **editor_fields(**overrides)}, headers=auth_headers(admin))
        assert response.status_code == 400 and message in response.json['error'], overrides
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM orange_decks').fetchone()[0] == 0
        assert get_db().execute('SELECT status FROM orange_deck_submissions').fetchone()[0] == 'processing'


def test_publish_rolls_back_every_write_when_a_late_step_fails(people, app, monkeypatch):
    alice, bob, admin, _ = people
    sub = claim(admin, submit(alice).json)
    with app.app_context():
        before = {table: get_db().execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                  for table in ('orange_decks', 'orange_deck_submission_events', 'user_notifications', 'audit_logs', 'orange_deck_activity_events')}

    def broken(*args, **kwargs):
        raise RuntimeError('audit offline')
    monkeypatch.setattr(deck_submission_service, 'write_audit', broken)
    with pytest.raises(RuntimeError):
        admin.post(f"/api/admin/deck-submissions/{sub['id']}/publish", json={'version': sub['version'], **editor_fields()},
                   headers=auth_headers(admin))
    with app.app_context():
        after = {table: get_db().execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in before}
        assert after == before
        row = get_db().execute('SELECT status, version, deck_id FROM orange_deck_submissions').fetchone()
        assert tuple(row) == ('processing', sub['version'], None)


def test_duplicate_and_reject_are_terminal_and_notify(people, app):
    alice, bob, admin, _ = people
    existing = admin.post('/api/orange-decks', json=deck_body(), headers=auth_headers(admin)).json
    sub = claim(admin, submit(alice).json)
    bad = act(admin, sub, 'duplicate', duplicate_of_deck_id=999999)
    assert bad.status_code == 400
    dup = act(admin, sub, 'duplicate', duplicate_of_deck_id=existing['id'], note='已有相同卡组')
    assert dup.status_code == 200 and dup.json['status'] == 'duplicate'
    assert act(admin, dup.json, 'claim').status_code == 409
    other = claim(admin, submit(alice, plan_code=OTHER_CODE).json)
    assert act(admin, other, 'reject', note='x').status_code == 400  # reason too short
    rejected = act(admin, other, 'reject', note='代码无法导入')
    assert rejected.status_code == 200 and rejected.json['status'] == 'rejected'
    detail = alice.get(f"/api/me/deck-submissions/{sub['id']}").json
    assert detail['duplicate_of']['detail_url'] == f"/orange-decks/{existing['id']}"


def test_notifications_follow_decisions_not_own_saves(people, app):
    alice, bob, admin, _ = people
    sub = submit(alice).json
    url = f"/api/me/deck-submissions/{sub['id']}"
    edited = alice.put(url, json={'version': 1, 'name': '自己改'}, headers=auth_headers(alice)).json
    assert alice.get('/api/me/notifications').json['total'] == 0
    claimed = claim(admin, edited)
    inbox = alice.get('/api/me/notifications?category=submission').json
    item = inbox['items'][0]
    assert inbox['total'] == 1 and item['kind'] == 'deck_submission' and item['category'] == 'submission'
    assert item['url'] == f"/me/deck-submissions/{sub['id']}" and item['state'] == 'processing' and item['notice_state'] == 'unread'
    assert '正在完善' in item['body']
    # Read state uses the shared revision protocol; a later decision makes it unread again.
    assert alice.put(f"/api/me/notifications/{item['id']}", json={'status': 'read', 'revision': item['revision']},
                     headers=auth_headers(alice)).status_code == 200
    act(admin, claimed, 'request_info', note='请补充站位思路')
    again = alice.get('/api/me/notifications').json['items'][0]
    assert again['notice_state'] == 'unread' and again['revision'] == item['revision'] + 1 and again['state'] == 'needs_info'
    assert alice.put(f"/api/me/notifications/{item['id']}", json={'status': 'read', 'revision': item['revision']},
                     headers=auth_headers(alice)).status_code == 409
    detail = alice.get(url).json
    assert detail['notification']['id'] == item['id']
    # Old categories keep working and do not pick up submission notices.
    for category in ('interaction', 'feedback', 'moderation'):
        assert alice.get(f'/api/me/notifications?category={category}').json['total'] == 0
    with app.app_context():
        row = get_db().execute("SELECT group_key, lineup_id, feedback_id, deck_submission_id FROM user_notifications").fetchone()
        assert tuple(row) == (f"deck_submission:{sub['id']}", None, None, sub['id'])


def test_old_publish_paths_cannot_forge_submission_attribution(people, app):
    alice, bob, admin, _ = people
    forged = alice.post('/api/orange-decks', json={**deck_body(), 'origin_type': 'submission', 'provided_by_user_id': 2,
                                                   'published_by_user_id': 1}, headers=auth_headers(alice)).json
    with app.app_context():
        row = get_db().execute('SELECT origin_type, provided_by_user_id, published_by_user_id FROM orange_decks WHERE id = ?',
                               (forged['id'],)).fetchone()
        assert tuple(row) == ('direct', None, None)
    # Direct decks keep their author line and owner-only editing; admins still cannot edit private drafts.
    assert forged['author']['credit'] == 'author' and forged['can_edit']
    draft = alice.post('/api/orange-decks', json=deck_body(action='draft'), headers=auth_headers(alice)).json
    assert admin.get(f"/api/orange-decks/{draft['id']}").status_code == 404
    assert admin.put(f"/api/orange-decks/{draft['id']}", json={**deck_body(), 'version': 1}, headers=auth_headers(admin)).status_code == 404
    sub = claim(admin, submit(alice).json)
    extra = admin.put(f"/api/admin/deck-submissions/{sub['id']}/draft",
                      json={'version': sub['version'], **editor_fields(), 'user_id': 2, 'status': 'published', 'origin_type': 'direct'},
                      headers=auth_headers(admin)).json
    assert extra['deck_detail']['status'] == 'draft' and extra['deck_detail']['origin'] == 'submission'


def test_concurrent_submissions_and_first_draft_saves_create_one_row(people, app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    alice, bob, admin, _ = people
    key, barrier = str(uuid.uuid4()), Barrier(3)
    clients = [app.test_client() for _ in range(3)]
    with alice.session_transaction() as source:
        state = dict(source)
    for client in clients:
        with client.session_transaction() as target:
            target.update(state)

    def send(client):
        barrier.wait(timeout=10)
        return client.post('/api/deck-submissions', json={'request_key': key, 'plan_code': CODE, 'lineup_code': LINEUP},
                           headers={'X-CSRF-Token': state['csrf_token']})
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(send, clients))
    assert sorted(r.status_code for r in responses) == [200, 200, 201]
    assert len({r.json['id'] for r in responses}) == 1
    sub = claim(admin, responses[0].json)
    with admin.session_transaction() as source:
        admin_state = dict(source)
    admin_clients = [app.test_client() for _ in range(3)]
    for client in admin_clients:
        with client.session_transaction() as target:
            target.update(admin_state)
    barrier = Barrier(3)

    def save(client):
        barrier.wait(timeout=10)
        return client.put(f"/api/admin/deck-submissions/{sub['id']}/draft", json={'version': sub['version'], **editor_fields()},
                          headers={'X-CSRF-Token': admin_state['csrf_token']})
    with ThreadPoolExecutor(max_workers=3) as pool:
        saves = list(pool.map(save, admin_clients))
    assert sorted(r.status_code for r in saves) == [200, 409, 409]
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM orange_decks WHERE origin_type = 'submission'").fetchone()[0] == 1
        assert get_db().execute('SELECT COUNT(*) FROM orange_deck_submissions').fetchone()[0] == 1
