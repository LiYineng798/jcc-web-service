from test_admin import login_admin

PAGE = '/tools/orange-fortune-creator'
API = '/api/tools/orange-fortune-creator'


def test_creator_static_catalog_and_public_page(client):
    response = client.get(API)
    data = response.get_json()
    assert data['schema_version'] == 1
    assert data['card_slots'] == 3
    assert data['export'] == {'width': 1200, 'height': 1600}
    assert len(data['cards']) == 201
    assert len(data['backgrounds']) == 6
    folio = next(b for b in data['backgrounds'] if b['id'] == 'folio')
    assert 'material-folio.svg?' in folio['image_url']
    assert client.get(folio['image_url']).status_code == 200
    assert all(card['energy'] is None for card in data['cards'])
    assert len({card['id'] for card in data['cards']}) == 201
    assert next(p for p in data['portals'] if p['id'] == 'stable')['energy_limit'] == 8
    assert response.headers['Cache-Control'] == 'no-store'
    html = client.get(PAGE).get_data(as_text=True)
    assert '大橘大利创作者工具' in html
    assert '先遣服' not in html and '测试服' not in html
    assert f'href="{PAGE}"' in client.get('/').get_data(as_text=True)
    assert PAGE in client.get('/sitemap.xml').get_data(as_text=True)
    assert client.get('/tools/lineup-simulator?creator=orange-fortune').status_code == 200


def test_creator_respects_simulator_season_visibility(client):
    headers = login_admin(client)
    assert client.put('/api/admin/season-display/simulator/s16_5', json={'status': 'hidden'}, headers=headers).status_code == 200
    assert client.get(API).get_json()['simulator_available'] is False
    html = client.get(PAGE).get_data(as_text=True)
    assert '<iframe' not in html
    assert '英雄联盟传奇阵容资料暂未开放' in html
    assert client.get('/tools/lineup-simulator?creator=orange-fortune').status_code == 404
    assert client.get('/tools/lineup-simulator').status_code == 200


def test_embedded_editor_does_not_count_as_a_second_page_visit(app, client):
    from db import get_db
    client.get(PAGE)
    client.get(PAGE)
    client.get('/tools/lineup-simulator?creator=orange-fortune')
    with app.app_context():
        rows = get_db().execute('SELECT page_key FROM visit_events').fetchall()
        assert [row['page_key'] for row in rows] == ['orange_creator']
