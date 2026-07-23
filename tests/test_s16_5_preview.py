import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / 'static' / 's16-5-preview'
NEW_CHAMPIONS = {
    '布兰德', '阿利斯塔', '希维尔', '墨菲特', '维克托', '萨科', '库奇',
    '伊莉丝', '凯隐', '彗', '艾瑞莉娅', '杰斯', '远古巨龙', '莫德凯撒',
}


def load_heroes():
    return json.loads((ASSET_ROOT / 'heroes.json').read_text(encoding='utf-8'))


def test_s16_preview_route_and_homepage_entry(client):
    homepage = client.get('/').get_data(as_text=True)
    assert 'href="/tools/s16-5-preview"' in homepage
    assert '资料库' in homepage
    response = client.get('/tools/s16-5-preview')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<title>S16.5英雄联盟传奇·海克斯宝典 - 金铲铲阵容库</title>' in html
    assert 's16-5-preview.css' in html
    assert 's16-5-preview.js' in html
    assert 'id="championSearch"' in html
    assert 'id="skillToggle"' in html


def test_s16_preview_data_and_assets_are_complete():
    payload = load_heroes()
    heroes = payload['heroes']
    assert payload['count'] == 115
    assert len(heroes) == 115
    assert {hero['price'] for hero in heroes} == {1, 2, 3, 4, 5, 7}
    assert NEW_CHAMPIONS <= {hero['name'] for hero in heroes}
    javascript = (ROOT / 'static' / 's16-5-preview.js').read_text(encoding='utf-8')
    for name in NEW_CHAMPIONS:
        assert name in javascript
    assert (ASSET_ROOT / 'system' / 'gold.png').is_file()
    for hero in heroes:
        image = ASSET_ROOT / 'images' / 'big' / f"{hero['price']}费" / f"{hero['id']}_{hero['name']}.jpg"
        assert image.is_file(), image
    assert any(ASSET_ROOT.joinpath('images', 'traits').rglob('*.png'))


def test_s16_preview_is_in_sitemap_and_datatft_label_is_removed(client):
    sitemap = client.get('/sitemap.xml').get_data(as_text=True)
    assert '<loc>http://localhost/tools/s16-5-preview</loc>' in sitemap
    javascript = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    assert '由 DataTFT 支持' not in javascript
