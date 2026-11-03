import json

import pytest

import orange_deck_service
from db import get_db
from test_admin import login_admin
from test_auth import register_user
from test_lineup_permissions import auth_headers

LEGENDS = ['7250010', '7250011', '7250013']  # 5 + 5 + 5 = 15: only the unknown portal
LIGHT = ['7230005', '7220015', '7210014']    # 3 + 2 + 1 = 6: fits every portal
SEASON = 'orange_s400001'


def deck_body(**overrides):
    body = {'action': 'publish', 'name': '轻装稳定门', 'portal': 'stable', 'cards': LIGHT,
            'note': '前期稳血，3-2 开始提速。', 'key_rounds': '2-1 拿装备', 'alternatives': '缺金辉尽绘可换基础锻造'}
    return {**body, **overrides}


def formation(units=(('1400', ['2001'], 2), ('1401', [], 1)), season=SEASON, traits=None):
    board = [None] * 28
    for index, (champion, items, star) in enumerate(units):
        board[21 + index] = {'championId': champion, 'items': items, 'star': star}
    return {'payload': {'version': 2, 'season': season, 'showNames': True, 'board': board, 'augmentIds': []},
            'traits': traits if traits is not None else [{'id': '341', 'count': 1, 'style': '1'}]}


@pytest.fixture()
def users(app):
    owner, other, admin, guest = (app.test_client() for _ in range(4))
    assert register_user(owner).status_code == 201
    assert register_user(other, username='bob', email='bob@example.com', nickname='Bob').status_code == 201
    login_admin(admin)
    return owner, other, admin, guest


def create(client, **overrides):
    return client.post('/api/orange-decks', json=deck_body(**overrides), headers=auth_headers(client))


def moderate(admin, deck, action, **extra):
    return admin.post(f"/api/admin/orange-decks/{deck['id']}/{action}", json={'version': deck['version'], **extra},
                      headers=auth_headers(admin))


def test_publish_requires_login_csrf_and_server_side_card_rules(users):
    owner, other, admin, guest = users
    assert guest.post('/api/orange-decks', json=deck_body()).status_code == 401
    assert owner.post('/api/orange-decks', json=deck_body()).status_code == 403  # missing CSRF token
    for overrides, message in [
        ({'name': ' '}, '请填写卡组名称'),
        ({'cards': LIGHT[:2]}, '请选择三张时间卡片'),
        ({'cards': [LIGHT[0], LIGHT[0], LIGHT[1]]}, '不能重复'),
        ({'cards': [LIGHT[0], '9999999', LIGHT[1]]}, '不存在'),
        ({'portal': 'custom'}, '传送门'),
        ({'cards': LEGENDS, 'portal': 'volatile'}, '超出波动传送门上限 10'),
        ({'name': '名' * 25}, '最多 24 字'),
    ]:
        response = create(owner, **overrides)
        assert response.status_code == 400 and message in response.get_json()['error'], overrides
    published = create(owner, cards=LEGENDS, portal='unknown')
    assert published.status_code == 201
    deck = published.get_json()
    assert deck['status'] == 'published' and deck['energy'] == 15 and deck['energy_limit'] == 15 and deck['fits']
    # Drafts may be incomplete or over the limit; publishing them is still checked.
    draft = create(owner, action='draft', name='', cards=[LEGENDS[0], None, LEGENDS[1]], portal='stable').get_json()
    assert draft['status'] == 'draft' and draft['name'] == '未命名卡组' and draft['energy'] == 10
    blocked = owner.put(f"/api/orange-decks/{draft['id']}", json={**deck_body(cards=LEGENDS), 'version': draft['version']},
                        headers=auth_headers(owner))
    assert blocked.status_code == 400 and '超出稳定传送门上限 8' in blocked.get_json()['error']
    with app_context(owner):
        row = get_db().execute('SELECT energy, card_id_1, card_snapshot_json FROM orange_decks WHERE id = ?', (deck['id'],)).fetchone()
        assert row['energy'] == 15 and row['card_id_1'] == LEGENDS[0]
        assert json.loads(row['card_snapshot_json'])[0]['name'] == '利滚利'


def app_context(client):
    return client.application.app_context()


def test_only_the_owner_edits_with_version_checks(users):
    owner, other, admin, guest = users
    deck = create(owner).get_json()
    url = f"/api/orange-decks/{deck['id']}"
    assert other.put(url, json={**deck_body(), 'version': deck['version']}, headers=auth_headers(other)).status_code == 403
    assert admin.put(url, json={**deck_body(), 'version': deck['version']}, headers=auth_headers(admin)).status_code == 403
    assert other.delete(url, headers=auth_headers(other)).status_code == 403
    updated = owner.put(url, json={**deck_body(name='改名了', portal='volatile'), 'version': deck['version']}, headers=auth_headers(owner))
    assert updated.status_code == 200 and updated.get_json()['name'] == '改名了' and updated.get_json()['version'] == 2
    stale = owner.put(url, json={**deck_body(), 'version': deck['version']}, headers=auth_headers(owner))
    assert stale.status_code == 409
    draft = create(owner, action='draft').get_json()
    assert other.get(f"/api/orange-decks/{draft['id']}").status_code == 404
    assert other.put(f"/api/orange-decks/{draft['id']}", json={**deck_body(), 'version': 1}, headers=auth_headers(other)).status_code == 404
    # Withdrawing a published deck makes it private again.
    withdrawn = owner.put(url, json={**deck_body(action='draft'), 'version': 2}, headers=auth_headers(owner)).get_json()
    assert withdrawn['status'] == 'draft' and guest.get(url).status_code == 404


def test_formation_is_stored_structured_restored_and_reedited(users):
    owner, other, admin, guest = users
    deck = create(owner, formation=formation()).get_json()
    assert deck['has_formation']
    detail = owner.get(f"/api/orange-decks/{deck['id']}").get_json()
    edit = detail['formation_edit']
    assert edit['season'] == SEASON and edit['payload']['board'][21] == {'championId': '1400', 'items': ['2001'], 'star': 2}
    assert 'formation_edit' not in guest.get(f"/api/orange-decks/{deck['id']}").get_json()
    view = guest.get(f"/api/orange-decks/{deck['id']}/formation").get_json()['formation']
    assert view['available'] and view['unit_count'] == 2
    assert view['cells'][21]['name'] == '佛耶戈' and view['cells'][21]['star'] == 2 and view['cells'][21]['items'][0]['name'] == '无尽之刃'
    assert view['traits'] == [{'name': '德玛西亚', 'count': 1, 'icon': view['traits'][0]['icon'], 'frame': '/static/tools/lineup-simulator/ui/1.svg'}]
    url = f"/api/orange-decks/{deck['id']}"
    # Omitting the formation keeps it; a new payload replaces it; null removes it.
    kept = owner.put(url, json={**deck_body(name='保留站位'), 'version': 1}, headers=auth_headers(owner)).get_json()
    assert kept['has_formation']
    moved = owner.put(url, json={**deck_body(formation=formation(units=(('1402', [], 3),))), 'version': 2}, headers=auth_headers(owner))
    assert moved.get_json()['formation_edit']['payload']['board'][21]['star'] == 3
    removed = owner.put(url, json={**deck_body(formation=None), 'version': 3}, headers=auth_headers(owner)).get_json()
    assert not removed['has_formation'] and guest.get(f'{url}/formation').get_json()['formation'] is None
    for bad, message in [
        (formation(units=(('99999', [], 1),)), '不存在的弈子'),
        (formation(units=(('1400', ['nope'], 1),)), '不存在的装备'),
        (formation(units=(('1400', [], 5),)), '星级'),
        (formation(season='s16_5'), '赛季'),
        ({'board': []}, '阵容数据无效'),
    ]:
        response = create(owner, formation=bad)
        assert response.status_code == 400 and message in response.get_json()['error'], bad
    # Trait snapshots only keep known IDs; names always come from data.
    spoofed = create(owner, formation=formation(traits=[{'id': '341', 'count': 2, 'style': '2', 'name': '伪造'}, {'id': 'x', 'count': 9, 'style': '4'}])).get_json()
    traits = guest.get(f"/api/orange-decks/{spoofed['id']}/formation").get_json()['formation']['traits']
    assert [(t['name'], t['count']) for t in traits] == [('德玛西亚', 2)]


def test_formation_respects_the_creator_season_boundary(users, client):
    owner, other, admin, guest = users
    deck = create(owner, formation=formation()).get_json()
    assert admin.put(f'/api/admin/season-display/creator/{SEASON}', json={'status': 'hidden'}, headers=auth_headers(admin)).status_code == 200
    view = guest.get(f"/api/orange-decks/{deck['id']}/formation").get_json()['formation']
    assert view == {'available': False, 'season_id': SEASON, 'message': '阵容所属赛季资料当前未开放，暂时无法显示站位。'}
    response = create(owner, formation=formation())
    assert response.status_code == 400 and '暂未开放' in response.get_json()['error']
    # A deck without a formation still publishes, and the saved formation survives unrelated edits.
    assert create(owner).status_code == 201
    kept = owner.put(f"/api/orange-decks/{deck['id']}", json={**deck_body(name='资料关闭后编辑'), 'version': 1}, headers=auth_headers(owner))
    assert kept.status_code == 200 and kept.get_json()['has_formation']
    exported = owner.get(f"/api/orange-decks/{deck['id']}/export").get_json()
    assert exported['formation'] is None and exported['formation_dropped'] and exported['layout'] == 'cards'


def test_search_filters_tabs_and_favorites(users):
    owner, other, admin, guest = users
    fast = create(owner, name='速攻稳定门').get_json()
    legend = create(owner, name='三传说', cards=LEGENDS, portal='unknown').get_json()
    draft = create(owner, action='draft', name='速攻草稿').get_json()
    names = lambda response: [item['name'] for item in response.get_json()['items']]
    assert names(guest.get('/api/orange-decks')) == ['三传说', '速攻稳定门']
    assert names(guest.get('/api/orange-decks?q=速攻')) == ['速攻稳定门']
    assert names(guest.get('/api/orange-decks?q=利滚')) == ['三传说']  # card name
    assert names(guest.get('/api/orange-decks?portal=stable')) == ['速攻稳定门']
    assert names(guest.get('/api/orange-decks?q=%25')) == []
    assert guest.get('/api/orange-decks?portal=custom').status_code == 400
    assert guest.get('/api/orange-decks?tab=mine').status_code == 401
    assert names(owner.get('/api/orange-decks?tab=mine')) == ['速攻草稿', '三传说', '速攻稳定门']
    page = guest.get('/api/orange-decks?page=2&page_size=1').get_json()
    assert page['total'] == 2 and page['total_pages'] == 2 and names_of(page) == ['速攻稳定门']
    # Hot uses real favorites only, one per account; favoriting is idempotent.
    hot = guest.get('/api/orange-decks?tab=hot').get_json()
    assert hot['items'] == [] and '点赞数' in hot['ranking_rule'] and '收藏账号数' in hot['ranking_rule']
    for client in (other, other, admin):
        assert client.post(f"/api/orange-decks/{fast['id']}/favorite", headers=auth_headers(client)).status_code == 200
    assert other.post(f"/api/orange-decks/{legend['id']}/favorite", headers=auth_headers(other)).get_json() == {'favorited': True, 'favorite_count': 1}
    assert names(guest.get('/api/orange-decks?tab=hot')) == ['速攻稳定门', '三传说']
    assert [i['favorite_count'] for i in guest.get('/api/orange-decks?tab=hot').get_json()['items']] == [2, 1]
    assert names(other.get('/api/orange-decks?tab=favorites')) == ['三传说', '速攻稳定门']
    assert other.get(f"/api/orange-decks/{fast['id']}").get_json()['is_favorited'] is True
    for _ in range(2):
        assert other.delete(f"/api/orange-decks/{fast['id']}/favorite", headers=auth_headers(other)).status_code == 200
    assert names(other.get('/api/orange-decks?tab=favorites')) == ['三传说']
    assert owner.post(f"/api/orange-decks/{draft['id']}/favorite", headers=auth_headers(owner)).status_code == 409
    assert guest.post(f"/api/orange-decks/{fast['id']}/favorite").status_code == 401
    # Featured is set by an administrator only.
    assert other.post(f"/api/admin/orange-decks/{legend['id']}/feature", json={'version': 1}, headers=auth_headers(other)).status_code == 403
    featured = moderate(admin, legend, 'feature').get_json()
    assert featured['featured'] and names(guest.get('/api/orange-decks?tab=featured')) == ['三传说']
    assert moderate(admin, legend, 'feature').status_code == 409  # stale version
    moderate(admin, featured, 'unfeature')
    assert names(guest.get('/api/orange-decks?tab=featured')) == []


def names_of(payload):
    return [item['name'] for item in payload['items']]


def test_hidden_and_deleted_decks_follow_one_visibility_rule(users):
    owner, other, admin, guest = users
    deck = create(owner, name='违规卡组').get_json()
    other.post(f"/api/orange-decks/{deck['id']}/favorite", headers=auth_headers(other))
    deck = moderate(admin, deck, 'feature').get_json()
    assert moderate(admin, deck, 'hide', reason='x').status_code == 400
    hidden = moderate(admin, deck, 'hide', reason='名称含引流信息').get_json()
    assert hidden['status'] == 'hidden' and not hidden['featured']
    url = f"/api/orange-decks/{deck['id']}"
    for client in (guest, other):
        assert client.get(url).status_code == 404
        assert client.get(f'{url}/formation').status_code == 404
        assert client.get(f'{url}/export').status_code == 404
        assert client.get(f"/orange-decks/{deck['id']}").status_code == 404
        assert names_of(client.get('/api/orange-decks?q=违规').get_json()) == []
    assert names_of(other.get('/api/orange-decks?tab=favorites').get_json()) == []
    assert other.post(f'{url}/fork', headers=auth_headers(other)).status_code == 404
    owner_view = owner.get(url).get_json()
    assert owner_view['hidden_reason'] == '名称含引流信息' and not owner_view['can_share'] and not owner_view['can_fork']
    assert owner.get(f'{url}/export').status_code == 404 and owner.post(f'{url}/fork', headers=auth_headers(owner)).status_code == 404
    page = owner.get(f"/orange-decks/{deck['id']}")
    assert page.status_code == 200 and 'noindex' in page.get_data(as_text=True) and page.headers['Cache-Control'] == 'private, no-store'
    assert admin.get(url).status_code == 200
    # The owner may correct content but cannot republish it.
    republish = owner.put(url, json={**deck_body(), 'version': hidden['version']}, headers=auth_headers(owner))
    assert republish.status_code == 409
    saved = owner.put(url, json={**deck_body(action='save', name='已修正'), 'version': hidden['version']}, headers=auth_headers(owner)).get_json()
    assert saved['status'] == 'hidden'
    restored = moderate(admin, saved, 'restore').get_json()
    assert restored['status'] == 'published' and names_of(guest.get('/api/orange-decks').get_json()) == ['已修正']
    with app_context(admin):
        actions = [row['action'] for row in get_db().execute(
            "SELECT action FROM audit_logs WHERE target_type = 'orange_deck' ORDER BY id").fetchall()]
    assert actions == ['orange_deck.feature', 'orange_deck.hide', 'orange_deck.restore']
    listing = admin.get('/api/admin/orange-decks').get_json()
    assert listing['counts']['published'] == 1 and listing['total'] == 1
    assert owner.get('/api/admin/orange-decks').status_code == 403
    assert admin.post(f'/api/admin/orange-decks/{deck["id"]}/explode', json={'version': restored['version']}, headers=auth_headers(admin)).status_code == 404
    # Deleting removes every entry point, including favorites.
    assert owner.delete(url, headers=auth_headers(owner)).status_code == 204
    for client in (owner, admin, guest):
        assert client.get(url).status_code == 404
    assert names_of(owner.get('/api/orange-decks?tab=mine').get_json()) == []
    assert admin.get('/api/admin/orange-decks').get_json()['total'] == 0


def test_detail_page_share_text_seo_and_sitemap(users):
    owner, other, admin, guest = users
    deck = create(owner, cards=LEGENDS, portal='unknown', formation=formation()).get_json()
    draft = create(owner, action='draft', name='私人草稿').get_json()
    html = guest.get(f"/orange-decks/{deck['id']}").get_data(as_text=True)
    for text in ['轻装稳定门', '利滚利', '自选神器', '幸运宝箱堆 II', '未知传送门', '2,000 金橘币', '前期稳血', '替代卡建议',
                 'deck-board', '佛耶戈', 'fortune-card-bezel', 'data-portal="unknown"', 'data-action="like"', 'data-action="favorite"']:
        assert text in html, text
    # Copying, forking and poster export are no longer offered on the detail page.
    for text in ['copy-text', 'copy-link', 'data-action="fork"', 'orange-fortune-creator?deck=', '额外羁绊']:
        assert text not in html, text
    assert 'noindex' not in html and '"@type": "BreadcrumbList"' in html.replace('"@type":"BreadcrumbList"', '"@type": "BreadcrumbList"')
    detail = guest.get(f"/api/orange-decks/{deck['id']}").get_json()
    lines = detail['share_text'].split('\n')
    assert lines[0] == '【大橘大利卡组】轻装稳定门'
    assert lines[1] == '卡片：利滚利（传说·5）／自选神器（传说·5）／幸运宝箱堆 II（传说·5）'
    assert lines[2] == '推荐传送门：未知传送门（能量 15 / 15）'
    assert lines[3] == f"详情：http://localhost/orange-decks/{deck['id']}" and detail['share_url'].endswith(f"/orange-decks/{deck['id']}")
    assert '导入' not in detail['share_text']
    assert guest.get(f"/orange-decks/{draft['id']}").status_code == 404
    assert 'share_text' not in owner.get(f"/api/orange-decks/{draft['id']}").get_json()
    sitemap = guest.get('/sitemap.xml').get_data(as_text=True)
    assert f"/orange-decks/{deck['id']}" in sitemap and f"/orange-decks/{draft['id']}" not in sitemap
    assert guest.get('/orange-decks/new').headers['Location'].endswith('/lineup/new?type=deck')
    assert guest.get('/orange-decks/new?from=creator').headers['Location'].endswith('/lineup/new?type=deck&from=creator')
    assert guest.get(f"/orange-decks/{deck['id']}/edit").headers['Location'].endswith('/auth')
    editor = owner.get(f"/orange-decks/{deck['id']}/edit")
    assert editor.status_code == 200 and 'noindex' in editor.get_data(as_text=True)
    assert other.get(f"/orange-decks/{deck['id']}/edit").status_code == 403


def test_fork_creates_a_new_private_draft(users):
    owner, other, admin, guest = users
    source = create(owner, formation=formation()).get_json()
    own_draft = create(other, action='draft', name='Bob 原有草稿', cards=[LEGENDS[0], None, None]).get_json()
    assert guest.post(f"/api/orange-decks/{source['id']}/fork").status_code == 401
    forked = other.post(f"/api/orange-decks/{source['id']}/fork", headers=auth_headers(other))
    assert forked.status_code == 201
    copy = other.get(f"/api/orange-decks/{forked.get_json()['id']}").get_json()
    assert copy['status'] == 'draft' and copy['forked_from_id'] == source['id'] and copy['can_edit']
    assert [c['id'] for c in copy['cards']] == LIGHT and copy['formation_edit']['payload']['board'][21]['star'] == 2
    assert owner.get(f"/api/orange-decks/{source['id']}").get_json()['version'] == source['version']
    untouched = other.get(f"/api/orange-decks/{own_draft['id']}").get_json()
    assert untouched['name'] == 'Bob 原有草稿' and untouched['version'] == own_draft['version']
    assert names_of(guest.get('/api/orange-decks').get_json()) == ['轻装稳定门']
    private = create(owner, action='draft').get_json()
    assert other.post(f"/api/orange-decks/{private['id']}/fork", headers=auth_headers(other)).status_code == 404


def test_poster_export_and_creator_import_do_not_touch_drafts(users):
    owner, other, admin, guest = users
    plain = create(owner).get_json()
    staged = create(owner, formation=formation()).get_json()
    exported = guest.get(f"/api/orange-decks/{plain['id']}/export").get_json()
    assert exported == {'id': plain['id'], 'title': '轻装稳定门', 'author': 'Alice', 'portal': 'stable', 'cards': LIGHT,
                        'note': '前期稳血，3-2 开始提速。', 'tempo': '2-1 拿装备', 'layout': 'cards', 'formation': None,
                        'formation_dropped': False}
    with_board = guest.get(f"/api/orange-decks/{staged['id']}/export").get_json()
    assert with_board['layout'] == 'guide' and with_board['formation']['board'][21]['championId'] == '1400'
    page = guest.get(f"/tools/orange-fortune-creator?deck={staged['id']}").get_data(as_text=True)
    assert f'data-deck-id="{staged["id"]}"' in page and 'creator=orange-fortune&amp;deck=1' in page and '原有海报草稿与阵容草稿保持不变' in page
    plain_page = guest.get('/tools/orange-fortune-creator?deck=abc').get_data(as_text=True)
    assert 'creator-import' not in plain_page and 'deck=1' not in plain_page
    assert guest.get('/tools/lineup-simulator?creator=orange-fortune&deck=1').status_code == 200
    creator_js = (orange_deck_service.Path(__file__).resolve().parents[1] / 'static/orange-creator.js').read_text(encoding='utf-8')
    assert "importDeckId ? null : JSON.parse(localStorage.getItem(storageKey)" in creator_js
    assert "if (importDeckId) { $('save-status')" in creator_js
    simulator_js = (orange_deck_service.Path(__file__).resolve().parents[1] / 'static/tools/lineup-simulator/app.js').read_text(encoding='utf-8')
    assert 'function readStoredFormation(seasonId) {\n  if (DECK_MODE) return null;' in simulator_js
    assert 'let storageSaved = !DECK_MODE;\n  if (!DECK_MODE) {' in simulator_js


def test_card_data_changes_are_reported_and_never_replaced(users, monkeypatch):
    owner, other, admin, guest = users
    deck = create(owner, formation=formation()).get_json()
    real = orange_deck_service.card_index()
    changed = {key: dict(value) for key, value in real.items()}
    del changed[LIGHT[1]]
    changed[LIGHT[0]].update(name='金辉尽绘·改', tier=4, tier_name='史诗', energy=4)
    monkeypatch.setattr(orange_deck_service, 'card_index', lambda: changed)
    monkeypatch.setattr(orange_deck_service, 'card_version', lambda: '18.18.2@2026-11-10 10:00:00')
    data = guest.get(f"/api/orange-decks/{deck['id']}").get_json()
    first, second, third = data['cards']
    assert [card['id'] for card in data['cards']] == LIGHT
    assert first['status'] == 'changed' and first['name'] == '金辉尽绘·改' and first['energy'] == 4
    assert first['changes'] == ['卡名由「金辉尽绘」更新为「金辉尽绘·改」', '品阶由王者调整为史诗（能量 3 → 4）']
    assert second['status'] == 'missing' and second['name'] == '假人朋友' and second['image_url'] is None
    assert third['status'] == 'ok'
    assert data['energy'] == 5 and data['compat']['missing_cards'] == 1 and not data['fits']
    assert data['compat']['issues'][0].startswith('卡片资料已从 18.18.1（2026-10-28）更新为 18.18.2（2026-11-10）')
    assert '「假人朋友」在当前资料中已失效' in data['compat']['issues']
    html = guest.get(f"/orange-decks/{deck['id']}").get_data(as_text=True)
    assert '当前资料中不存在' in html and '资料变化' in html
    # Saving with a vanished card is rejected; a fork leaves that slot empty and says so.
    update = owner.put(f"/api/orange-decks/{deck['id']}", json={**deck_body(), 'version': 1}, headers=auth_headers(owner))
    assert update.status_code == 400 and '不存在或已下架' in update.get_json()['error']
    fork = other.post(f"/api/orange-decks/{deck['id']}/fork", headers=auth_headers(other)).get_json()
    assert '失效' in fork['notes'][0]
    assert [c and c['id'] for c in other.get(f"/api/orange-decks/{fork['id']}").get_json()['cards']] == [LIGHT[0], None, LIGHT[2]]
    # A formation saved under older season data is labelled, not silently recomputed.
    bundle = orange_deck_service.season_bundle
    monkeypatch.setattr(orange_deck_service, 'season_bundle', lambda season: {**bundle(season), 'version_id': 'orange_s400001__19'})
    view = guest.get(f"/api/orange-decks/{deck['id']}/formation").get_json()['formation']
    assert any('羁绊为保存时的计算结果' in issue for issue in view['issues'])


def test_unchanged_data_reports_version_only(users, monkeypatch):
    owner, *_ = users
    deck = create(owner).get_json()
    assert deck['compat'] == {'saved_version': '18.18.1（2026-10-28）', 'current_version': '18.18.1（2026-10-28）',
                              'changed': False, 'issues': [], 'missing_cards': 0}
    monkeypatch.setattr(orange_deck_service, 'card_version', lambda: '18.18.2@2026-11-10 10:00:00')
    issues = owner.get(f"/api/orange-decks/{deck['id']}").get_json()['compat']['issues']
    assert issues == ['卡片资料已从 18.18.1（2026-10-28）更新为 18.18.2（2026-11-10），本卡组的卡片没有变化。']


def test_decks_stay_out_of_lineup_counts_and_rankings(users):
    owner, other, admin, guest = users
    before = guest.get('/api/home-stats').get_json()
    create(owner)
    create(owner, cards=LEGENDS, portal='unknown')
    assert guest.get('/api/home-stats').get_json() == before
    assert guest.get('/api/lineups').get_json() == []
    assert admin.get('/api/admin/lineups').get_json()['total'] == 0


def test_home_library_switch_renders_requested_library(client):
    decks = client.get('/?library=decks').get_data(as_text=True)
    assert 'data-home-library="decks"' in decks
    assert 'id="lineupLibrary" aria-labelledby="listTitle" hidden' in decks
    assert 'id="deckLibrary" data-deck-root aria-labelledby="deckLibraryTitle">' in decks
    assert '<a href="/?library=decks" data-home-library="decks" aria-current="page">' in decks
    lineups = client.get('/').get_data(as_text=True)
    assert 'id="lineupLibrary" aria-labelledby="listTitle">' in lineups
    assert 'aria-labelledby="deckLibraryTitle" hidden' in lineups
    for tab in ('latest', 'hot', 'featured', 'favorites', 'mine'):
        assert f'data-deck-tab="{tab}"' in lineups
    assert '/tools/orange-fortune-creator' in lineups and '/tools/orange-fortune"' in lineups
    # <body> carries data-home-library too; the switch handler must bind to the two links only.
    script = (orange_deck_service.Path(__file__).resolve().parents[1] / 'static/orange-deck-library.js').read_text(encoding='utf-8')
    assert "querySelectorAll('[data-home-library]')" not in script and script.count("querySelectorAll('a[data-home-library]')") == 2


def test_creation_is_rate_limited(users, monkeypatch):
    owner, *_ = users
    monkeypatch.setattr(orange_deck_service, 'hit_limit', lambda *args: True)
    response = create(owner)
    assert response.status_code == 429


def test_likes_mirror_lineup_rules_and_feed_hot_ranking(users, monkeypatch):
    owner, other, admin, guest = users
    first = create(owner, name='甲').get_json()
    second = create(owner, name='乙', cards=LEGENDS, portal='unknown').get_json()
    draft = create(owner, action='draft').get_json()
    url = f"/api/orange-decks/{first['id']}/like"
    assert guest.post(url).status_code == 401
    assert other.post(url).status_code == 403  # CSRF
    assert other.post(url, headers=auth_headers(other)).get_json() == {'liked_today': True, 'like_count': 1}
    again = other.post(url, headers=auth_headers(other))
    assert again.status_code == 409 and '今天已经点赞' in again.get_json()['error']
    assert owner.post(f"/api/orange-decks/{draft['id']}/like", headers=auth_headers(owner)).status_code == 409
    assert admin.post(url, headers=auth_headers(admin)).status_code == 201
    view = other.get(f"/api/orange-decks/{first['id']}").get_json()
    assert view['like_count'] == 2 and view['is_liked_today'] is True
    assert guest.get(f"/api/orange-decks/{first['id']}").get_json()['is_liked_today'] is False
    # A new day allows another like; the daily cap is per account.
    monkeypatch.setattr(orange_deck_service, 'today', lambda: '2099-01-01')
    assert other.post(url, headers=auth_headers(other)).status_code == 201
    monkeypatch.setattr(orange_deck_service, 'DAILY_LIKE_LIMIT', 1)
    capped = other.post(f"/api/orange-decks/{second['id']}/like", headers=auth_headers(other))
    assert capped.status_code == 429
    # Hot = likes + favorites; the favorite-only deck ranks below the liked one.
    monkeypatch.setattr(orange_deck_service, 'DAILY_LIKE_LIMIT', 5)
    other.post(f"/api/orange-decks/{second['id']}/favorite", headers=auth_headers(other))
    hot = guest.get('/api/orange-decks?tab=hot').get_json()['items']
    assert [(d['name'], d['like_count'], d['favorite_count']) for d in hot] == [('甲', 3, 0), ('乙', 0, 1)]
    assert guest.get('/api/home-stats').get_json()['total_public_lineups'] == 0


def test_dashboard_reports_deck_figures_separately(users):
    owner, other, admin, guest = users
    deck = create(owner).get_json()
    create(owner, action='draft')
    other.post(f"/api/orange-decks/{deck['id']}/like", headers=auth_headers(other))
    other.post(f"/api/orange-decks/{deck['id']}/favorite", headers=auth_headers(other))
    data = owner.get('/api/me/dashboard').get_json()
    assert data['received_likes'] == 0 and data['received_favorites'] == 0 and data['published_lineups'] == 0
    assert data['decks'] == {'decks': 2, 'published_decks': 1, 'draft_decks': 1, 'hidden_decks': 0,
                             'received_likes': 1, 'received_favorites': 1}


def test_publish_page_offers_lineups_and_decks(users):
    owner, other, admin, guest = users
    html = owner.get('/lineup/new').get_data(as_text=True)
    assert 'id="editorForm"' in html and 'id="deckForm"' in html and 'id="publishTabDeck"' in html
    assert 'id="publishDeck" role="tabpanel" aria-labelledby="publishTabDeck" hidden' in html
    deck_tab = owner.get('/lineup/new?type=deck').get_data(as_text=True)
    assert 'id="publishLineup" role="tabpanel" aria-labelledby="publishTabLineup" hidden' in deck_tab
    assert 'id="deckEditorConfig"' in deck_tab and 'bezel-5' in deck_tab
    # Editing stays specific to the content type.
    lineup_edit = owner.get('/lineup/1/edit').get_data(as_text=True)
    assert 'id="editorForm"' in lineup_edit and 'id="deckForm"' not in lineup_edit and 'publishTabDeck' not in lineup_edit
    deck = create(owner, action='draft').get_json()
    deck_edit = owner.get(f"/orange-decks/{deck['id']}/edit").get_data(as_text=True)
    assert 'id="deckForm"' in deck_edit and 'id="editorForm"' not in deck_edit
    assert 'href="/lineup/new?type=deck&amp;from=creator"' in owner.get('/tools/orange-fortune-creator').get_data(as_text=True)
