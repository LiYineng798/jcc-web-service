from test_admin import login_admin

PAGE = '/tools/orange-fortune-creator'
API = '/api/tools/orange-fortune-creator'


def test_creator_static_catalog_and_public_page(client):
    response = client.get(API)
    data = response.get_json()
    assert data['schema_version'] == 2
    assert data['simulator_available'] is True
    assert data['card_slots'] == 3
    assert data['export'] == {'width': 1200, 'height': 1600}
    assert len(data['cards']) == 201
    assert len(data['backgrounds']) == 6
    folio = next(b for b in data['backgrounds'] if b['id'] == 'folio')
    assert 'material-folio.svg?' in folio['image_url']
    assert client.get(folio['image_url']).status_code == 200
    # Energy equals rarity: Basic 1 … Legendary 5.
    assert data['tiers'] == {'1': '基础', '2': '勇士', '3': '王者', '4': '史诗', '5': '传说'}
    assert all(card['energy'] == card['tier'] and card['tier_name'] == data['tiers'][str(card['tier'])] for card in data['cards'])
    assert len({card['id'] for card in data['cards']}) == 201
    assert [(p['id'], p['name'], p['energy_limit'], p['entry_fee'], p['loss_cards']) for p in data['portals']] == [
        ('stable', '稳定传送门', 8, 0, 0), ('volatile', '波动传送门', 10, 400, 2), ('unknown', '未知传送门', 15, 2000, 3)]
    assert [(l['id'], l['formation']) for l in data['layouts']] == [('guide', True), ('showcase', True), ('cards', False)]
    assert response.headers['Cache-Control'] == 'no-store'
    html = client.get(PAGE).get_data(as_text=True)
    assert '大橘大利创作者工具' in html
    assert html.count('name="deck-portal"') == 3 and '卡组推荐版' in html
    assert '其他传送门' not in html and 'deck-energy' not in html
    assert '先遣服' not in html and '测试服' not in html
    assert f'href="{PAGE}"' in client.get('/').get_data(as_text=True)
    assert PAGE in client.get('/sitemap.xml').get_data(as_text=True)
    assert client.get('/tools/lineup-simulator?creator=orange-fortune').status_code == 200


def test_creator_uses_its_own_season_surface(client):
    headers = login_admin(client)
    data = client.get(API).get_json()
    assert data['season_id'] == 'orange_s400001' and data['season_name'] == '英雄联盟传奇 · 大橘大利'
    # The mode season is only listed for the creator, never in the ordinary library or simulator.
    for surface in ('library', 'simulator'):
        listed = client.get(f'/api/season-catalog?surface={surface}').get_json()['seasons']
        assert 'orange_s400001' not in {s['season_id'] for s in listed}
    creator = client.get('/api/season-catalog?surface=creator').get_json()
    assert [s['season_id'] for s in creator['seasons']] == ['orange_s400001'] and creator['default_season_id'] == 'orange_s400001'
    assert client.get('/tools/seasons/orange_s400001').status_code == 404
    assert client.get('/static/season-data/orange_s400001/champions.json').status_code == 200
    # Hiding the ordinary simulator season no longer affects the poster tool.
    assert client.put('/api/admin/season-display/simulator/s16_5', json={'status': 'hidden'}, headers=headers).status_code == 200
    assert client.get(API).get_json()['simulator_available'] is True
    assert client.get('/tools/lineup-simulator?creator=orange-fortune').status_code == 200

    assert client.put('/api/admin/season-display/creator/orange_s400001', json={'status': 'hidden'}, headers=headers).status_code == 200
    assert client.get(API).get_json()['simulator_available'] is False
    html = client.get(PAGE).get_data(as_text=True)
    assert '<iframe' not in html and '大橘大利阵容资料暂未开放' in html
    assert client.get('/tools/lineup-simulator?creator=orange-fortune').status_code == 404
    assert client.get('/static/season-data/orange_s400001/champions.json').status_code == 404
    assert client.get('/tools/lineup-simulator').status_code == 200

    # The admin can point the poster tool at another season without code changes.
    assert client.put('/api/admin/season-display/creator/s16_5', json={'status': 'active'}, headers=headers).status_code == 200
    switched = client.put('/api/admin/season-display/creator/s16_5', json={'is_default': True}, headers=headers)
    assert switched.status_code == 200 and switched.get_json()['default_season_id'] == 's16_5'
    assert client.get(API).get_json()['season_id'] == 's16_5'
    assert client.put('/api/admin/season-display/library/s18', json={'is_default': True}, headers=headers).status_code == 400


def test_embedded_editor_does_not_count_as_a_second_page_visit(app, client):
    from db import get_db
    client.get(PAGE)
    client.get(PAGE)
    client.get('/tools/lineup-simulator?creator=orange-fortune')
    with app.app_context():
        rows = get_db().execute('SELECT page_key FROM visit_events').fetchall()
        assert [row['page_key'] for row in rows] == ['orange_creator']
