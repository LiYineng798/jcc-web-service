import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

import orange_deck_service as decks
from db import get_db
from test_admin import login_admin
from test_automation import create_account, login_bot, PREFIX
from test_lineup_permissions import auth_headers
from test_orange_decks import users, create, deck_body, LIGHT, SEASON, formation

CODE = '德玛时光速9流-大橘大利-MjE5OTY4Mzc0NDMyOTI3OTQxNzkzNzU0NzMyMTczNQ=='


def test_plan_code_roundtrip_validation_and_private_html(users):
    owner, other, admin, guest = users
    deck = create(owner, plan_code=' ' + CODE + ' ').get_json()
    assert deck['plan_code'] == CODE and deck['season_id'] == SEASON
    url = f"/api/orange-decks/{deck['id']}"
    assert guest.get('/api/orange-decks').get_json()['items'][0]['plan_code'] == CODE
    html = guest.get(deck['detail_url'])
    assert CODE in html.get_data(as_text=True) and '复制方案码' in html.get_data(as_text=True)
    assert html.headers['Cache-Control'] == 'private, no-store'
    # Old clients omitting the new field must not erase an existing code.
    saved = owner.put(url, json={**deck_body(), 'version': 1}, headers=auth_headers(owner)).get_json()
    assert saved['plan_code'] == CODE
    for value in (123, 'wrong', '名称-大橘大利-???', '名称-大橘大利-', 'a\nb-大橘大利-MQ==', '名' * 513):
        assert create(owner, plan_code=value).status_code == 400
    cleared = owner.put(url, json={**deck_body(plan_code=''), 'version': 2}, headers=auth_headers(owner)).get_json()
    assert cleared['plan_code'] == ''
    assert create(owner, season_id='s18').status_code == 400
    assert create(owner, portal=[]).status_code == 400


def test_missing_cards_do_not_claim_over_budget_and_invalid_traits_return_400(users, monkeypatch):
    owner, _, _, guest = users
    deck = create(owner).get_json()
    changed = dict(decks.card_index())
    changed.pop(LIGHT[0])
    monkeypatch.setattr(decks, 'card_index', lambda: changed)
    html = guest.get(deck['detail_url']).get_data(as_text=True)
    assert '含已失效卡片' in html and '按当前资料计算已超出上限' not in html
    monkeypatch.undo()
    assert create(owner, formation=formation(traits=12)).status_code == 400
    bad = formation()
    bad['payload']['augmentIds'] = ['not-a-real-augment']
    assert create(owner, formation=bad).status_code == 400


def test_admin_racing_update_does_not_log_success(users, monkeypatch):
    owner, _, admin, _ = users
    deck = create(owner).get_json()
    original = decks.deck_row

    def concurrently_edit(deck_id, user=None):
        row = original(deck_id, user)
        get_db().execute('UPDATE orange_decks SET version=version+1 WHERE id=?', (deck_id,))
        get_db().commit()
        return row

    monkeypatch.setattr(decks, 'deck_row', concurrently_edit)
    response = admin.post(f"/api/admin/orange-decks/{deck['id']}/feature", json={'version': 1}, headers=auth_headers(admin))
    assert response.status_code == 409
    with owner.application.app_context():
        assert get_db().execute('SELECT featured FROM orange_decks').fetchone()[0] == 0
        assert get_db().execute("SELECT COUNT(*) FROM audit_logs WHERE action='orange_deck.feature'").fetchone()[0] == 0


def test_parallel_likes_obey_account_daily_quota(users):
    owner, other, _, _ = users
    ids = [create(owner, name=f'卡组{i}').get_json()['id'] for i in range(6)]
    user = other.get('/api/me').get_json()['user']
    barrier = Barrier(6)
    def submit(deck_id):
        with owner.application.app_context():
            barrier.wait(timeout=10)
            try:
                decks.like(user, deck_id)
                return 201
            except decks.DeckError as error:
                get_db().rollback()
                return error.status
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sorted(pool.map(submit, ids)) == [201] * 5 + [429]


def test_automation_upload_grant_scope_revocation_and_audit(client, app):
    admin = login_admin(client)
    account = create_account(client, admin)
    bot, headers = login_bot(app)
    body = deck_body(season_id=SEASON, plan_code=CODE)
    endpoint = PREFIX + '/decks'
    assert bot.post(endpoint, headers=headers, json=body).status_code == 403
    url = '/api/admin/automation-accounts/' + str(account['user_id'])
    assert client.put(url, headers=admin, json={'can_upload_decks': True, 'deck_seasons': ['s17-star-god']}).status_code == 400
    assert client.put(url, headers=admin, json={'can_upload_decks': True, 'deck_seasons': [SEASON]}).status_code == 200
    assert bot.get(PREFIX + '/me').get_json()['deck_seasons'] == [SEASON]
    assert bot.get('/admin/assistant/decks/new?season_id=' + SEASON).status_code == 200
    assert bot.post(endpoint, json=body).status_code == 403
    assert bot.post('/api/orange-decks', headers=headers, json=body).status_code == 403
    assert bot.post(endpoint, headers=headers, json={**body, 'season_id': 's18'}).status_code == 403
    assert bot.post(endpoint, headers=headers, json={**body, 'user_id': 1}).status_code == 400
    assert bot.post(endpoint, headers=headers, json={**body, 'action': 'draft'}).status_code == 400
    result = bot.post(endpoint, headers=headers, json=body)
    assert result.status_code == 201, result.get_json()
    assert result.get_json()['plan_code'] == CODE and not result.get_json()['can_edit']
    with app.app_context():
        row = get_db().execute('SELECT user_id,season_id,status FROM orange_decks').fetchone()
        assert tuple(row) == (account['user_id'], SEASON, 'published')
        assert get_db().execute("SELECT actor_user_id FROM audit_logs WHERE action='automation_upload_deck'").fetchone()[0] == account['user_id']
    assert client.put(url, headers=admin, json={'can_upload_decks': False}).status_code == 200
    assert bot.post(endpoint, headers=headers, json=body).status_code == 403
    assert bot.get('/admin/assistant/decks/new?season_id=' + SEASON).status_code == 403


def test_automation_upload_atomic_on_audit_failure(client, app, monkeypatch):
    admin = login_admin(client)
    create_account(client, admin, can_upload_decks=True, deck_seasons=[SEASON])
    bot, headers = login_bot(app)
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr('automation_service.write_audit', fail)
    with pytest.raises(RuntimeError):
        bot.post(PREFIX + '/decks', headers=headers, json=deck_body(season_id=SEASON))
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM orange_decks').fetchone()[0] == 0


def test_time_card_catalog_refreshes_without_process_restart(tmp_path, monkeypatch):
    import orange_fortune_service as source
    path = tmp_path / 'cards.json'
    payload = json.loads(source.CATALOG.read_text(encoding='utf-8'))
    path.write_text(json.dumps(payload), encoding='utf-8')
    monkeypatch.setattr(source, 'CATALOG', path)
    before = source.catalog()
    payload['data'][LIGHT[0]]['sDesc'] = '更新后的效果'
    path.write_text(json.dumps(payload), encoding='utf-8')
    after = source.catalog()
    assert next(c for c in before['cards'] if c['id'] == LIGHT[0])['description'] != '更新后的效果'
    assert next(c for c in after['cards'] if c['id'] == LIGHT[0])['description'] == '更新后的效果'


def test_sqlite_upgrade_preserves_old_decks_and_is_repeatable():
    from orange_deck_schema import migrate_deck_codes
    from automation_schema import migrate_automation_sessions
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE orange_decks(id INTEGER, name TEXT)')
    db.execute("INSERT INTO orange_decks VALUES(1,'旧卡组')")
    db.execute('CREATE TABLE automation_accounts(user_id INTEGER)')
    db.execute('INSERT INTO automation_accounts VALUES(7)')
    for _ in range(2):
        migrate_deck_codes(db)
        migrate_automation_sessions(db)
    assert tuple(db.execute('SELECT name,plan_code,season_id FROM orange_decks').fetchone()) == ('旧卡组', '', SEASON)
    assert tuple(db.execute('SELECT can_upload_decks,deck_seasons_json FROM automation_accounts').fetchone()) == (0, '[]')


def test_new_card_season_does_not_reuse_old_card_ids(users, monkeypatch):
    owner, other, _, guest = users
    deck = create(owner).get_json()
    monkeypatch.setattr(decks, 'card_season_id', lambda: 'orange_s400002')
    old = guest.get(f"/api/orange-decks/{deck['id']}").get_json()
    assert old['season_id'] == SEASON and old['compat']['missing_cards'] == 3
    fork = other.post(f"/api/orange-decks/{deck['id']}/fork", headers=auth_headers(other)).get_json()
    draft = other.get(f"/api/orange-decks/{fork['id']}").get_json()
    assert draft['season_id'] == 'orange_s400002' and draft['cards'] == [None, None, None]


def test_hidden_deck_season_blocks_upload_but_not_account_renewal(client, app, monkeypatch):
    admin = login_admin(client)
    account = create_account(client, admin, can_upload_decks=True, deck_seasons=[SEASON])
    bot, headers = login_bot(app)
    monkeypatch.setattr(decks, 'deck_season_choices', lambda: {})
    assert bot.post(PREFIX + '/decks', headers=headers, json=deck_body(season_id=SEASON)).status_code == 403
    url = '/api/admin/automation-accounts/' + str(account['user_id'])
    assert client.put(url, headers=admin, json={'expires_in_days': 60}).status_code == 200
    assert client.put(url, headers=admin, json={'status': 'disabled'}).status_code == 200
