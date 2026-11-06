import pytest

from db import get_db
from test_deck_codes_permissions import CODE
from test_lineup_permissions import auth_headers
from test_orange_decks import users, create, deck_body, moderate, SEASON
from test_admin import login_admin
from test_automation import create_account, login_bot, PREFIX

RAW = '分享文案【阵容码】#测试阵容#ABC123456789，复制到游戏'
NORMALIZED = '#ABC123456789'


@pytest.mark.parametrize('plan,lineup', [('', ''), (CODE, ''), ('', RAW), (CODE, RAW)])
def test_independent_optional_codes_roundtrip(users, plan, lineup):
    owner, other, _, guest = users
    response = create(owner, plan_code=plan, lineup_code=lineup)
    assert response.status_code == 201
    deck = response.json
    expected = NORMALIZED if lineup else ''
    assert (deck['plan_code'], deck['lineup_code']) == (plan, expected)
    assert guest.get('/api/orange-decks').json['items'][0]['lineup_code'] == expected
    html = guest.get(deck['detail_url']).get_data(as_text=True)
    assert ('复制阵容码' if lineup else '作者暂未提供阵容码') in html
    assert ('复制方案码' if plan else '作者暂未提供方案码') in html
    url = f"/api/orange-decks/{deck['id']}"
    # Legacy clients omit both fields: existing values survive.
    saved = owner.put(url, json={**deck_body(), 'version': 1}, headers=auth_headers(owner))
    assert saved.status_code == 200
    assert (saved.json['plan_code'], saved.json['lineup_code']) == (plan, expected)
    assert other.put(url, json={**deck_body(lineup_code='#OTHER'), 'version': 2}, headers=auth_headers(other)).status_code == 403
    assert owner.put(url, json={**deck_body(lineup_code='#STALE'), 'version': 1}, headers=auth_headers(owner)).status_code == 409
    cleared = owner.put(url, json={**deck_body(lineup_code=''), 'version': 2}, headers=auth_headers(owner))
    assert cleared.json['lineup_code'] == '' and cleared.json['plan_code'] == plan
    fork = other.post(url + '/fork', headers=auth_headers(other)).json
    draft = other.get(f"/api/orange-decks/{fork['id']}").json
    assert draft['lineup_code'] == draft['plan_code'] == ''


@pytest.mark.parametrize('raw,expected', [
    (RAW, NORMALIZED), (' ＃AbC123 ', '#AbC123'), ('【阵容码】##XYZ987', '#XYZ987'),
    ('#short 文案 #LONGEST1234', '#LONGEST1234'), ('  ', ''), (None, ''),
])
def test_uses_existing_lineup_extractor(users, raw, expected):
    assert create(users[0], lineup_code=raw).json['lineup_code'] == expected


@pytest.mark.parametrize('raw', [123, [], {}, '无效阵容码', '#', 'a' * 20001])
def test_rejects_invalid_lineup_code_without_saving(users, app, raw):
    assert create(users[0], lineup_code=raw).status_code == 400
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM orange_decks').fetchone()[0] == 0


def test_copy_types_validation_and_shared_deduplication(users, monkeypatch):
    owner, _, admin, guest = users
    monkeypatch.setattr('orange_deck_service.bucket_start', lambda: '2026-11-06 12:00:00')
    deck = create(owner, plan_code=CODE, lineup_code=RAW).json
    url = f"/api/orange-decks/{deck['id']}/copy"
    headers = auth_headers(guest)
    assert guest.post(url + '?code_type=lineup', headers=headers).json == {'counted': True, 'copy_count': 1}
    assert guest.post(url, headers=headers).json == {'counted': False, 'copy_count': 1}
    assert guest.post(url + '?code_type=invalid', headers=headers).status_code == 400
    single = create(owner, lineup_code=RAW).json
    single_url = f"/api/orange-decks/{single['id']}/copy"
    assert guest.post(single_url, headers=headers).status_code == 400
    assert guest.post(single_url + '?code_type=lineup', headers=headers).status_code == 200
    plan = create(owner, plan_code=CODE).json
    assert guest.post(f"/api/orange-decks/{plan['id']}/copy?code_type=lineup", headers=headers).status_code == 400
    assert moderate(admin, deck, 'hide', reason='测试隐藏').status_code == 200
    assert guest.post(url + '?code_type=lineup', headers=headers).status_code == 404
    assert owner.post(url + '?code_type=lineup', headers=auth_headers(owner)).status_code == 409


def test_ai_upload_uses_shared_normalization_and_validation(client, app):
    admin = login_admin(client)
    create_account(client, admin, can_upload_decks=True, deck_seasons=[SEASON])
    bot, headers = login_bot(app)
    body = deck_body(season_id=SEASON, lineup_code=RAW, plan_code=CODE)
    result = bot.post(PREFIX + '/decks', headers=headers, json=body)
    assert result.status_code == 201
    assert result.json['lineup_code'] == NORMALIZED and result.json['plan_code'] == CODE
    assert bot.post(PREFIX + '/decks', headers=headers, json={**body, 'lineup_code': '无效'}).status_code == 400
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM orange_decks').fetchone()[0] == 1
        assert get_db().execute("SELECT COUNT(*) FROM audit_logs WHERE action='automation_upload_deck'").fetchone()[0] == 1
