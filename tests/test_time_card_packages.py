"""Time cards use the same immutable candidate/publish/rollback lifecycle as season data."""
import json

import pytest
from PIL import Image

from db import get_db
from orange_deck_service import create_deck
from orange_fortune_service import CATALOG, parse_catalog
from season_package_format import PackageError, dump
from test_season_packages import prepared, manager, package, upload, work

SID = 'orange_s400001'
IDS = ['7230005', '7220015', '7210014']


@pytest.fixture()
def cards_source(prepared):
    index = json.loads((prepared / 'index.json').read_text('utf8'))
    index.update(season_id=SID, display_name='大橘大利')
    dump(prepared / 'index.json', index)
    legacy = parse_catalog(json.loads(CATALOG.read_text('utf8')))
    cards = [c for c in legacy['cards'] if c['id'] in IDS]
    for card in cards:
        card.update(image='assets/icon.png', layout='portrait', name='新版' + card['name'], description='本次 ZIP 中的效果')
    doc = {key: legacy[key] for key in ('season', 'setId', 'time')}
    doc.update(season_id=SID, version=index['game_version'], version_id=index['version_id'], time_cards=cards)
    dump(prepared / 'time_cards.json', doc)
    return prepared


def test_time_cards_preview_publish_remove_and_rollback(cards_source, manager, app):
    admin, headers = manager
    guest = app.test_client()
    with app.test_request_context('/'):
        user = get_db().execute("SELECT * FROM users WHERE username='adminxlx'").fetchone()
        deck = create_deck(user, {'name': '旧卡组', 'action': 'publish', 'portal': 'stable', 'cards': IDS})
    url = f"/api/orange-decks/{deck['id']}"
    old = guest.get(url).get_json()
    first_upload = upload(manager, package(cards_source))
    assert first_upload.status_code == 202, first_upload.json
    rid = first_upload.json['package']['id']
    report = work(app, rid)
    assert report['state'] == 'ready', report
    assert report['report']['counts']['time_cards'] == 3
    assert len(report['time_card_previews']) == 3
    assert any('时间卡片' in w for w in report['report']['warnings'])
    assert len(report['report']['diff']['time_cards']['removed']) == 198
    preview = '?preview_release=' + rid
    assert guest.get('/tools/orange-fortune' + preview).status_code in (401, 403)
    assert guest.get(f'/season-assets/{rid}/assets/icon.png').status_code == 404
    assert guest.get(url).json['cards'] == old['cards']
    for path in ('/tools/orange-fortune', '/tools/orange-fortune-creator', '/lineup/new?type=deck'):
        response = admin.get(path + ('&' if '?' in path else '?') + 'preview_release=' + rid)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert '本次 ZIP 中的效果' in html or json.dumps('本次 ZIP 中的效果')[1:-1] in html
        assert response.headers['Cache-Control'] == 'private, no-store'
    candidate = admin.get('/api/tools/orange-fortune-creator' + preview).json
    assert len(candidate['cards']) == 3
    assert candidate['cards'][0]['image_url'].startswith(f'/season-assets/{rid}/')
    assert admin.post('/api/orange-decks' + preview, headers=headers, json={}).status_code == 400

    def publish(release, revision):
        response = admin.post(f'/api/admin/season-packages/{release}/publish', headers=headers,
                              json={'expected_revision': revision, 'acknowledge_warnings': True})
        assert response.status_code == 200, response.json

    publish(rid, 0)
    live = guest.get(url).json
    assert live['compat']['changed']
    assert all(c['description'] == '本次 ZIP 中的效果' for c in live['cards'])
    assert guest.get(live['cards'][0]['image_url']).status_code == 200
    assert len(guest.get('/api/tools/orange-fortune-creator').json['cards']) == 3
    assert '本次 ZIP 中的效果' in guest.get('/tools/orange-fortune').get_data(as_text=True)
    # Publish another revision of the same patch; a removed card must never silently revive from baseline.
    path = cards_source / 'time_cards.json'
    doc = json.loads(path.read_text('utf8'))
    doc['time_cards'] = [c for c in doc['time_cards'] if c['id'] != IDS[0]]
    doc['time_cards'][0]['description'] = '第二修订效果'
    dump(path, doc)
    rid2 = upload(manager, package(cards_source, 'two', 2)).json['package']['id']
    assert work(app, rid2)['state'] == 'ready'
    publish(rid2, 1)
    live2 = guest.get(url).json
    assert live2['compat']['missing_cards'] == 1
    assert live2['cards'][0]['status'] == 'missing' and live2['cards'][0]['image_url'] is None
    assert live2['cards'][0]['name'] == old['cards'][0]['name']
    assert json.dumps('第二修订效果')[1:-1] in guest.get('/tools/orange-fortune-creator').get_data(as_text=True)
    assert len(guest.get('/api/tools/orange-fortune-creator').json['cards']) == 2
    response = admin.post(f'/api/admin/seasons/{SID}/rollback', headers=headers,
                          json={'expected_revision': 2, 'release_id': rid})
    assert response.status_code == 200, response.json
    assert guest.get(url).json['cards'] == live['cards']
    # Hiding all surfaces must also hide the released time-card descriptions, not just their images.
    with app.app_context():
        from season_visibility import load_policy, save_policy
        policy = load_policy()
        original = json.loads(json.dumps(policy))
        for kind in ('library', 'simulator', 'creator'):
            policy[kind][SID]['status'] = 'hidden'
        save_policy(policy)
    assert guest.get('/api/tools/orange-fortune-creator').json['cards'] == []
    assert guest.get(live['cards'][0]['image_url']).status_code == 404
    with app.app_context():
        save_policy(original)
    response = admin.post(f'/api/admin/seasons/{SID}/rollback', headers=headers,
                          json={'expected_revision': 3, 'release_id': None})
    assert response.status_code == 200, response.json
    assert guest.get(url).json['cards'] == old['cards']


@pytest.mark.parametrize('field,value', [('tier', 6), ('tier', True), ('rounds', ['bad']), ('image', 'https://example.test/x.png'),
                                         ('image', 'assets/absent.png'), ('layout', 'unsafe'), ('description', []), ('id', '')])
def test_reject_invalid_time_cards(cards_source, field, value):
    path = cards_source / 'time_cards.json'
    doc = json.loads(path.read_text('utf8'))
    doc['time_cards'][0][field] = value
    dump(path, doc)
    with pytest.raises(PackageError):
        package(cards_source)


def test_time_cards_required_and_version_bound(cards_source):
    path = cards_source / 'time_cards.json'
    doc = json.loads(path.read_text('utf8'))
    path.unlink()
    with pytest.raises(PackageError, match='time_cards'):
        package(cards_source)
    doc['version'] = 'old-version'
    dump(path, doc)
    with pytest.raises(PackageError, match='版本'):
        package(cards_source)


def test_official_archive_conversion_uses_current_images(tmp_path):
    from scripts.season_library.time_cards import import_time_cards

    source = tmp_path / 'official'
    (source / 'images').mkdir(parents=True)
    Image.new('RGB', (326, 524), 'green').save(source / 'images/card.png')
    legacy = json.loads(CATALOG.read_text('utf8'))
    legacy['data'] = {key: legacy['data'][key] for key in IDS[:2]}
    records = {IDS[0]: {'local_path': 'images/card.png'}, IDS[1]: {'error': 'http_404'}}
    dump(source / 'images/manifest.json', records)
    dest = tmp_path / 'prepared'
    assert import_time_cards(source, legacy, dest, SID, 'v1', legacy['version']) == 2
    doc = json.loads((dest / 'time_cards.json').read_text('utf8'))
    assert doc['time_cards'][0]['layout'] == 'portrait'
    assert doc['time_cards'][1]['image'] is None
    records[IDS[1]] = {'error': 'timeout'}
    dump(source / 'images/manifest.json', records)
    with pytest.raises(PackageError, match='重试'):
        import_time_cards(source, legacy, dest, SID, 'v1', legacy['version'])
