import json
import re
from pathlib import Path

from admin_lineup_service import parse_bulk_lineup_entries
from lucky_openings import OPENINGS, build_lucky_openings
from test_admin import login_admin

PAGE = '/tools/s16-5-lucky-openings'
EXPECTED = (
    ('阿兹尔开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA0ODUyMjYz'),
    ('稻草人开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA0OTQxNDcy'),
    ('卢锡安开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1MDI4Nzkw'),
    ('希瓦娜开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1MTA4MTQx'),
    ('基兰开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1MjMyMDU2'),
    ('安妮开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1MzE2NDMz'),
    ('千珏开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1NDM5Nzkx'),
    ('杰斯开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1NTIwMjQz'),
    ('奥恩开局', 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1NTY2OTg4'),
)


def test_guest_gets_all_nine_exact_normalized_codes_and_effects(client):
    response = client.get(PAGE)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert tuple((c['name'], c['code']) for c in OPENINGS) == EXPECTED
    expected_codes = [parse_bulk_lineup_entries(f'【阵容码】#{name}#{code}')[0]['code'] for name, code in EXPECTED]
    assert re.findall(r'data-code="([^"]+)"', html) == expected_codes
    assert len(set(expected_codes)) == 9
    assert html.count('class="opening-card"') == 9
    assert '羁绊' not in html
    for removed in ('查看阵容码', 'opening-manual', '<textarea', 'openings-intro', 'openings-rule', 'openings-footer', '浏览 S16.5 资料库'):
        assert removed not in html
    # Full effect text remains readable without JavaScript; formatting changes no numbers.
    text = re.sub(r'<[^>]+>', '', html)
    for opening in OPENINGS:
        assert opening['effect'].removeprefix('在玩家对战回合中，') in text


def test_home_toolbox_groups_both_features_without_loading_opening_cards(client):
    html = client.get('/').get_data(as_text=True)
    assert 'class="toolbox-menu desktop-resource-entry"' in html
    assert 'id="mobileToolsResourceTitle"' in html
    assert html.count(f'href="{PAGE}"') == 2
    assert 'S8回归信息差' in html
    assert 'toolbox-featured' not in html
    assert 'toolbox-badge' not in html
    assert f'class="returning-info-menu-item" href="{PAGE}"' in html
    assert f'class="mobile-resource-subitem" href="{PAGE}"' in html
    for path in ('special-mechanics', 'artifact-guide', 'returning-equipment'):
        assert html.count(f'href="/tools/{path}"') == 2
    assert 'opening-card' not in html
    assert 'lucky-openings.js' not in html
    assert PAGE in client.get('/sitemap.xml').get_data(as_text=True)


def test_images_reuse_reachable_library_webp_files(client):
    html = client.get(PAGE).get_data(as_text=True)
    sources = re.findall(r'<img src="([^"]+)"', html)
    assert len(sources) == 9
    for source in sources:
        assert '/static/season-data/s16_5/assets/champions/card/' in source
        assert '.webp?v=' in source
        assert client.get(source).status_code == 200


def test_hiding_library_does_not_break_codes_or_leak_hidden_art(client):
    headers = login_admin(client)
    response = client.put('/api/admin/season-display/library/s16_5', json={'status': 'hidden'}, headers=headers)
    assert response.status_code == 200
    html = client.get(PAGE).get_data(as_text=True)
    assert html.count('class="opening-card"') == 9
    assert '/assets/champions/' not in html
    assert 'href="/tools/seasons/s16_5"' not in html
    assert len(re.findall(r'data-code="([^"]+)"', html)) == 9


def test_art_resolves_again_after_release_change(app, monkeypatch, tmp_path):
    import lucky_openings
    import season_reference_service
    original = Path('static/season-data/s16_5/index.json')
    updated = json.loads(original.read_text(encoding='utf-8'))
    for champion in updated['champions']:
        if champion['id'] == '5290':
            champion['card'] = 'assets/champions/card/updated-azir.webp'
    (tmp_path / 'index.json').write_text(json.dumps(updated), encoding='utf-8')
    with app.app_context():
        assert 'updated-azir' not in build_lucky_openings()[0]['art']
        monkeypatch.setattr(season_reference_service, 'data_directory', lambda sid: tmp_path)
        monkeypatch.setattr(lucky_openings, 'asset_url', lambda sid: '/season-assets/new-release')
        assert build_lucky_openings()[0]['art'].startswith('/season-assets/new-release/assets/champions/card/updated-azir.webp')
