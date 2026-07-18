import json
from pathlib import Path
from urllib.parse import quote

from s18_preview_service import build_champion_detail, champion_names


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / 'static' / 's18-preview'
PROFESSIONS = {
    '法师',
    '适配者',
    '毁灭者',
    '斗士',
    '迅捷射手',
    '猎手',
    '裁决使',
    '召唤使',
    '重装战士',
    '护卫',
    '主宰',
    '神谕者',
}


def load_json(filename):
    return json.loads((ASSET_ROOT / filename).read_text(encoding='utf-8'))


def test_s18_preview_route_and_homepage_entry(client):
    homepage = client.get('/').get_data(as_text=True)
    assert 'href="/tools/s18-preview"' in homepage
    assert 'S18版本前瞻' in homepage
    assert homepage.index('S18版本前瞻') < homepage.index('S8回归信息差')

    response = client.get('/tools/s18-preview')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<title>S18版本前瞻 - 弈子、羁绊与法杖</title>' in html
    assert 'data-view="champions"' in html
    assert 'data-view="traits"' in html
    assert 'data-view="wands"' in html
    assert 'id="skillToggle"' in html
    assert '浏览新赛季弈子、羁绊与法杖资料。' not in html
    assert 's18-preview.css' in html
    assert 's18-preview.js' in html
    assert 's18-champion-ui.js' in html


def test_s18_champion_detail_renders_champion_traits_and_member_links(client):
    response = client.get(f"/tools/s18-preview/champions/{quote('维迦')}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<title>维迦 - S18弈子详情 - 金铲铲阵容库</title>' in html
    assert 'class="champion-card champion-detail-card"' in html
    assert '能量爆裂' in html
    assert '古神' in html
    assert '森林妖精' in html
    assert '法师' in html
    assert '羁绊数量' in html
    assert 'data-champion-name="维迦"' in html
    assert 's18-champion-detail.css' in html
    assert 's18-champion-detail.js' in html


def test_s18_champion_detail_returns_404_for_unknown_champion(client):
    assert client.get('/tools/s18-preview/champions/not-a-champion').status_code == 404


def test_s18_champion_detail_service_links_every_champion_and_trait_member():
    champions = load_json('champions.json')

    assert champion_names() == [champion['名称'] for champion in champions]
    for champion in champions:
        detail = build_champion_detail(champion['名称'])
        assert detail['champion'] == champion
        assert [trait['名称'] for trait in detail['traits']] == champion['羁绊']
        for trait in detail['traits']:
            assert trait['弈子']
            assert all(trait['名称'] in member['羁绊'] for member in trait['弈子'])


def test_s18_preview_data_and_assets_are_complete():
    champions = load_json('champions.json')
    traits = load_json('traits.json')
    wands = load_json('wands.json')

    assert len(champions) == 65
    assert len(traits) == 36
    assert len(wands) == 200
    assert len({champion['名称'] for champion in champions}) == 65
    assert len({trait['名称'] for trait in traits}) == 36
    assert len({wand['名称'] for wand in wands}) == 200

    trait_names = {trait['名称'] for trait in traits}
    assert PROFESSIONS <= trait_names
    assert (ASSET_ROOT / 'system' / 'gold.png').is_file()

    for champion in champions:
        assert champion['名称']
        assert champion['费用'] in {1, 2, 3, 4, 5}
        assert champion['羁绊']
        assert set(champion['羁绊']) <= trait_names
        assert champion['技能名称']
        assert champion['技能描述']
        assert (ASSET_ROOT / 'bg' / str(champion['费用']) / f"{champion['名称']}.jpg").is_file()
        assert (ASSET_ROOT / 'xt' / str(champion['费用']) / f"{champion['名称']}.jpg").is_file()

    for trait in traits:
        assert trait['名称']
        assert trait['介绍']
        assert isinstance(trait['层级'], list)
        assert (ASSET_ROOT / trait['svg']).is_file()
        for level in trait['层级']:
            assert isinstance(level['数量'], int)
            assert level['效果']

    for wand in wands:
        assert wand['名称']
        assert isinstance(wand['费用'], int)
        assert wand['效果']
        assert wand['出现条件'] is None or isinstance(wand['出现条件'], str)


def test_s18_preview_preserves_traits_without_levels_or_champions():
    champions = load_json('champions.json')
    traits = {trait['名称']: trait for trait in load_json('traits.json')}

    assert traits['日食']['层级'] == []
    assert traits['日月蚀']['层级'] == []
    assert not any('日月蚀' in champion['羁绊'] for champion in champions)


def test_s18_preview_frontend_defines_classification_and_empty_states():
    javascript = (ROOT / 'static' / 's18-preview.js').read_text(encoding='utf-8')
    template = (ROOT / 'templates' / 's18_preview.html').read_text(encoding='utf-8')
    css = (ROOT / 'static' / 's18-preview.css').read_text(encoding='utf-8')
    champion_ui = (ROOT / 'static' / 's18-champion-ui.js').read_text(encoding='utf-8')

    for profession in PROFESSIONS:
        assert f"'{profession}'" in javascript
    assert "empty.textContent = '暂无弈子'" in javascript
    assert "condition.textContent = `出现条件：${wand.出现条件}`" in javascript
    assert 'id="championEmpty"' in template
    assert 'id="championFilterToggle"' in template
    assert 'aria-controls="championFilterPanel"' in template
    assert 'id="championFilterSummary"' in template
    assert 'class="champion-filter-row"' in template
    assert template.index('id="championSearch"') < template.index('id="originFilters"')
    assert template.index('id="originFilters"') < template.index('id="professionFilters"')
    assert template.index('id="professionFilters"') < template.index('id="costFilters"')
    assert template.index('id="costFilters"') < template.index('id="skillToggle"')
    assert 'makeFilterSelect' in javascript
    assert 's18-filter-select-icon' in javascript
    assert 'align-items: stretch;' in css
    assert 'grid-template-columns: minmax(190px, 1.2fr) repeat(3, minmax(140px, 1fr)) auto;' in css
    assert 'height: 44px;' in css
    assert css.count('align-content: start;') >= 2
    assert '@media (prefers-reduced-motion: reduce)' in css
    assert "window.matchMedia('(max-width: 640px)')" in javascript
    assert 'showSkills: !championMobileQuery.matches' in javascript
    assert 'mobileFiltersExpanded: false' in javascript
    assert 'updateChampionFilterSummary(champions.length)' in javascript
    assert 'syncChampionFilterLayout()' in javascript
    mobile_css = css[css.index('@media (max-width: 640px)'):]
    assert '.champion-filter-toggle {' in mobile_css
    assert '.champion-filter-panel.mobile-collapsed {' in mobile_css
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr));' in mobile_css
    assert 'rgb(145, 145, 145)' in javascript
    assert 'rgb(16, 166, 14)' in javascript
    assert 'rgb(67, 156, 204)' in javascript
    assert 'rgb(175, 25, 186)' in javascript
    assert 'rgb(147, 130, 22)' in javascript
    assert "link.className = 'champion-card-link'" in javascript
    assert 'JccS18ChampionUi.createMemberLink' in javascript
    assert 'createHoverCard' in champion_ui
    assert 'data-champion-name' in champion_ui
    assert "pointerenter" in champion_ui
    assert "focus" in champion_ui
    assert '.champion-hover-layer.visible' in css
