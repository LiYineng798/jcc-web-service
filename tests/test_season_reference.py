import json
from pathlib import Path

from season_reference_service import (
    build_champion_detail,
    catalog_seasons,
    champion_ids,
    find_champion_id_by_name,
    normalize_season_id,
    season_page_context,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / 'static' / 'season-data'


def test_catalog_lists_seasons_newest_first():
    seasons = catalog_seasons()
    assert len(seasons) >= 4
    season_ids = [season['season_id'] for season in seasons]
    assert season_ids[0] == 's18'
    assert {'s8', 's16_5', 's17', 's18'} <= set(season_ids)
    for season in seasons:
        assert season['counts']['champions'] > 0
        assert season['counts']['traits'] > 0
        assert (DATA_ROOT / season['path']).is_file()


def test_normalize_season_id_accepts_aliases():
    assert normalize_season_id('s16-5') == 's16_5'
    assert normalize_season_id('S16.5') == 's16_5'
    assert normalize_season_id('s18') == 's18'


def test_season_index_payloads_are_consistent():
    for season in catalog_seasons():
        payload = json.loads((DATA_ROOT / season['path']).read_text(encoding='utf-8'))
        assert payload['season_id'] == season['season_id']
        assert len(payload['champions']) == season['counts']['champions']
        assert len(payload['traits']) == season['counts']['traits']
        trait_ids = {trait['id'] for trait in payload['traits']}
        for champion in payload['champions']:
            assert champion['name']
            for trait_id in champion['trait_ids']:
                assert trait_id in trait_ids
        for trait in payload['traits']:
            assert trait['category'] in {'origin', 'class'}


def test_season_assets_referenced_by_index_exist():
    for season in catalog_seasons():
        season_dir = DATA_ROOT / season['season_id']
        payload = json.loads((season_dir / 'index.json').read_text(encoding='utf-8'))

        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str) and value.startswith('assets/'):
                assert (season_dir / value).is_file(), f"{season['season_id']} missing {value}"

        walk(payload)


def test_every_splash_has_card_thumbnail():
    for season in catalog_seasons():
        payload = json.loads((DATA_ROOT / season['path']).read_text(encoding='utf-8'))
        for champion in payload['champions']:
            if champion['splash']:
                assert champion['card'], f"{season['season_id']} {champion['id']} missing card thumbnail"
                assert champion['card'].endswith('.webp')
                assert (DATA_ROOT / season['season_id'] / champion['card']).is_file()


def test_season_reference_pages_render_for_every_catalog_season(client):
    for season in catalog_seasons():
        response = client.get(f"/tools/seasons/{season['season_id']}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert season['display_name'] in html
        assert 'season-reference.css' in html
        assert 'season-reference.js' in html
        assert f"/static/season-data/{season['season_id']}/index.json?v=" in html
        context = season_page_context(season['season_id'])
        for mechanic in context['mechanics']:
            assert mechanic['display_name'] in html
        assert f'style="--tab-count: {2 + len(context["mechanics"])}"' in html


def test_season_alias_and_unknown_season(client):
    response = client.get('/tools/seasons/s16-5')
    assert response.status_code == 301
    assert response.headers['Location'].endswith('/tools/seasons/s16_5')
    assert client.get('/tools/seasons/unknown').status_code == 404


def test_every_champion_detail_page_renders(client):
    for season in catalog_seasons():
        season_id = season['season_id']
        ids = champion_ids(season_id)
        assert len(ids) == season['counts']['champions']
        for champion_id in ids:
            detail = build_champion_detail(season_id, champion_id)
            assert detail is not None
            for trait in detail['traits']:
                member_ids = {member['id'] for member in trait['members']}
                assert champion_id in member_ids
        response = client.get(f'/tools/seasons/{season_id}/champions/{ids[0]}')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        detail = build_champion_detail(season_id, ids[0])
        assert detail['champion']['name'] in html
        assert 'season-champion-detail.js' in html


def test_champion_detail_shows_star_stats_when_available(client):
    champion_id = find_champion_id_by_name('s16_5', '佛耶戈')
    assert champion_id is not None
    html = client.get(f'/tools/seasons/s16_5/champions/{champion_id}').get_data(as_text=True)
    assert '逐星属性' in html
    assert '技能数值' in html
    assert 'champion-stats-scroll' in html
    for icon in ('hp', 'ad', 'armor', 'mr', 'as', 'range', 'mana', 'crit'):
        assert f'/static/season-stats/{icon}.png' in html
    assert '/static/season-gold.png' in html
    assert 'scale-chip scale-chip-ap' in html
    assert '【法术加成】' not in html


def test_variable_labels_and_skill_chips_are_sanitized():
    from season_reference_service import clean_variable_label, format_skill_description

    assert clean_variable_label('伤害:460=410(【物理加成】)+50(【法术加成】) 135/195/300/410') == '伤害'
    assert clean_variable_label('额外伤害：1320') == '额外伤害'
    assert clean_variable_label('被动每秒攻击次数') == '被动每秒攻击次数'

    html = str(format_skill_description('造成55(【法术加成】)点伤害与10(【物理加成】)点伤害<x>'))
    assert '<span class="scale-chip scale-chip-ap">法术加成</span>' in html
    assert '<span class="scale-chip scale-chip-ad">物理加成</span>' in html
    assert '&lt;x&gt;' in html

    detail = build_champion_detail('s16_5', find_champion_id_by_name('s16_5', '佛耶戈'))
    for variable in detail['champion']['skill']['variables']:
        assert ':' not in variable['label'] and '：' not in variable['label']
        assert '【' not in variable['label']


def test_s16_5_new_champion_tags_render_from_data():
    payload = json.loads((DATA_ROOT / 's16_5' / 'index.json').read_text(encoding='utf-8'))
    tagged = [champion['name'] for champion in payload['champions'] if 'new' in champion['tags']]
    assert len(tagged) == 14
    assert '布兰德' in tagged


def test_legacy_preview_urls_redirect(client):
    response = client.get('/tools/s18-preview')
    assert response.status_code == 301
    assert response.headers['Location'].endswith('/tools/seasons/s18')

    response = client.get('/tools/s16-5-preview')
    assert response.status_code == 301
    assert response.headers['Location'].endswith('/tools/seasons/s16_5')

    champion_id = find_champion_id_by_name('s18', '卡尔玛')
    response = client.get('/tools/s18-preview/champions/卡尔玛')
    assert response.status_code == 301
    assert response.headers['Location'].endswith(f'/tools/seasons/s18/champions/{champion_id}')

    assert client.get('/tools/s18-preview/champions/不存在').status_code == 404


def test_homepage_navigation_is_catalog_driven(client):
    html = client.get('/').get_data(as_text=True)
    for season in catalog_seasons():
        assert f"/tools/seasons/{season['season_id']}" in html
        assert season['display_name'] in html
    assert '/tools/s18-preview' not in html
    assert '/tools/s16-5-preview' not in html


def test_sitemap_uses_season_library_urls(client):
    body = client.get('/sitemap.xml').get_data(as_text=True)
    for season in catalog_seasons():
        assert f"<loc>http://localhost/tools/seasons/{season['season_id']}</loc>" in body
        first_champion = champion_ids(season['season_id'])[0]
        assert f"/tools/seasons/{season['season_id']}/champions/{first_champion}</loc>" in body
    assert '/tools/s18-preview' not in body
    assert '/tools/s16-5-preview' not in body


def test_season_data_static_files_served(client):
    assert client.get('/static/season-data/catalog.json').status_code == 200
    assert client.get('/static/season-data/s18/index.json').status_code == 200
    assert client.get('/static/season-reference.js').status_code == 200
    assert client.get('/static/season-champion-ui.js').status_code == 200
    assert client.get('/static/season-gold.png').status_code == 200
