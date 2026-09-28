import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from s11_items_service import recommendation_guide
from test_admin import login_admin

ROOT = Path(__file__).resolve().parents[1]
PAGE = '/tools/s11-items'


def test_frozen_guide_matches_curated_recommendations_and_asset_hashes():
    groups = recommendation_guide()
    rows = [c for g in groups for c in g['champions']]
    assert Counter(c['cost'] for c in rows) == {5: 9, 4: 12, 3: 13, 2: 13, 1: 13}
    assert len({c['id'] for c in rows}) == 60
    with (ROOT / 'scripts/season_library/s11_recommendations.tsv').open(encoding='utf-8', newline='') as f:
        expected = list(csv.reader(f, delimiter='\t'))
    assert [(str(c['cost']), c['name'], ','.join(i['name'] for i in c['equipment'][:3]), c['equipment'][3]['name']) for c in rows] == [tuple(r) for r in expected]
    for c in rows:
        for item in c['equipment']:
            assert len(item['components']) == 2
            for obj in [c, item, *item['components']]:
                assert obj['image'].startswith('tools/s11-items/assets/')
                assert (ROOT / 'static' / obj['image']).is_file()
    base = ROOT / 'static/tools/s11-items'
    manifest = json.loads((base / 'asset-manifest.json').read_text(encoding='utf-8'))
    assert len(manifest) == 101  # 60 portraits, 33 completed items, 8 components
    for name, checksum in manifest.items():
        assert hashlib.sha256((base / name).read_bytes()).hexdigest() == checksum
    items = {i['name']: i for c in rows for i in c['equipment']}
    assert [c['name'] for c in items['班克斯的魔法帽']['components']] == ['无用大棒', '无用大棒']
    assert [c['name'] for c in items['红霸符']['components']] == ['反曲之弓', '反曲之弓']
    assert [c['name'] for c in items['坚定之心']['components']] == ['锁子甲', '拳套']


def test_public_render_assets_and_both_navigation_surfaces(client):
    response = client.get(PAGE)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('class="ink-card"') == 60
    assert html.count('class="ink-recipe"') == 240
    assert '全弈子推荐出装' in html
    assert '/season-assets/' not in html and '/static/season-data/' not in html
    for image in set(re.findall(r'<img[^>]+src="([^"]+)"', html)):
        assert client.get(image).status_code == 200
    home = client.get('/').get_data(as_text=True)
    assert home.count(f'href="{PAGE}"') == 2
    sitemap = client.get('/sitemap.xml').get_data(as_text=True)
    assert PAGE in sitemap
    for route in ['special-mechanics', 'artifact-guide', 'returning-equipment']:
        assert f'/tools/{route}' not in home
        assert f'/tools/{route}' not in sitemap
        assert client.get(f'/tools/{route}').status_code == 200


def test_guide_and_frozen_images_survive_hidden_s11_library(client):
    headers = login_admin(client)
    assert client.put('/api/admin/season-display/library/s11', json={'status': 'hidden'}, headers=headers).status_code == 200
    html = client.get(PAGE).get_data(as_text=True)
    assert html.count('class="ink-card"') == 60
    for image in set(re.findall(r'<img[^>]+src="([^"]+)"', html)):
        assert client.get(image).status_code == 200
