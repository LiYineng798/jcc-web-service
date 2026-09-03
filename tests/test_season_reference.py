import json
from pathlib import Path

from PIL import Image

from season_reference_service import (
    build_champion_detail,
    catalog_seasons,
    champion_ids,
    find_champion_id_by_name,
    normalize_season_id,
    season_page_context,
)
from season_rich_text import parse_rich_text, render_rich_text

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / 'static' / 'season-data'


def test_catalog_lists_seasons_newest_first(app):
    with app.app_context():
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
        assert f'style="--tab-count: {2 + len(context["mechanics"]) + int(context["has_augments"])}"' in html


def test_season_reference_images_wake_on_tab_switch_and_have_fallbacks():
    javascript = Path('static/season-reference.js').read_text(encoding='utf-8')

    assert 'function createImageWithFallback(paths, alt, className = \'\')' in javascript
    assert 'function wakePanelImages(panel)' in javascript
    assert 'wakePanelImages(panel)' in javascript
    assert '[champion.card, champion.splash, champion.icon].map(assetUrl)' in javascript


def test_s18_official_snapshot_supplants_pbe_mechanics(client):
    payload = json.loads((DATA_ROOT / 's18' / 'index.json').read_text(encoding='utf-8'))
    assert payload['game_version'] == '18.18.1c'
    assert payload['version_id'] == 's18__18_18_1c'
    assert payload['display_name'] == 'S18 自然之力'
    assert payload['status'] == 'active'
    assert len(payload['mechanics']) == 1
    assert payload['mechanics'][0]['kind'] == 'charm'
    assert payload['mechanics'][0]['display_name'] == '仙灵'
    assert len(payload['mechanics'][0]['entries']) == 170
    assert len(payload['champions']) == 74
    assert len(payload['augments']) == 258

    html = client.get('/tools/seasons/s18').get_data(as_text=True)
    assert 'data-view="augments"' in html
    assert '>仙灵<' in html
    assert 'data-charm-search="charms"' in html


def test_s18_official_charms_use_site_categories_with_upgrade_layers():
    payload = json.loads((DATA_ROOT / 's18' / 'index.json').read_text(encoding='utf-8'))
    charm = payload['mechanics'][0]
    assert charm['kind'] == 'charm'
    assert len(charm['entries']) == 170
    categories = {entry['data']['category'] for entry in charm['entries']}
    assert categories == {'champion', 'item', 'shop', 'combat', 'gold_xp', 'other'}
    for entry in charm['entries']:
        assert entry['name']
        assert entry['description']
        assert entry['image']
        assert (DATA_ROOT / 's18' / entry['image']).is_file()
        assert entry['data']['category_label']
        assert entry['data']['tier'] in {1, 2, 3}
        assert entry['data']['cost'] is not None
    assert sum(entry['data']['upgrade'] is not None for entry in charm['entries']) == 169
    assert sum(entry['data']['prismatic'] is not None for entry in charm['entries']) == 11
    barrier = next(entry for entry in charm['entries'] if entry['name'] == '屏障')
    assert barrier['data']['prismatic']['effect'] == '友军获得7500护盾值，在30秒内持续衰减。'


def test_s18_champion_detail_and_hover_use_large_splash_art(client):
    payload = json.loads((DATA_ROOT / 's18' / 'index.json').read_text(encoding='utf-8'))
    for champion in payload['champions']:
        splash_path = DATA_ROOT / 's18' / champion['splash']
        icon_path = DATA_ROOT / 's18' / champion['icon']
        with Image.open(splash_path) as splash, Image.open(icon_path) as icon:
            assert splash.width >= 700, champion['name']
            assert splash.width / splash.height > 1.6, champion['name']
            assert splash.width > icon.width * 4, champion['name']

    champion = payload['champions'][0]
    detail_html = client.get(f"/tools/seasons/s18/champions/{champion['id']}").get_data(as_text=True)
    assert champion['splash'] in detail_html
    hover_javascript = (ROOT / 'static' / 'season-champion-ui.js').read_text(encoding='utf-8')
    assert 'const artPath = champion.splash || champion.card || champion.icon;' in hover_javascript


def test_every_s18_champion_has_a_local_optimized_skill_icon():
    payload = json.loads((DATA_ROOT / 's18' / 'champions.json').read_text(encoding='utf-8'))
    assert len(payload['champions']) == 74
    for champion in payload['champions']:
        skill = champion['skills'][0]
        image = skill['image']
        assert image, champion['name']
        assert 'datatft' not in image['source_url'].lower(), champion['name']
        assert (DATA_ROOT / 's18' / image['local_path']).is_file(), champion['name']
        assert (DATA_ROOT / 's18' / image['optimized_local_path']).is_file(), champion['name']

        with Image.open(DATA_ROOT / 's18' / image['optimized_local_path']) as optimized:
            assert optimized.width > 0 and optimized.height > 0, champion['name']


def test_every_s18_item_has_a_local_optimized_image():
    payload = json.loads((DATA_ROOT / 's18' / 'items.json').read_text(encoding='utf-8'))
    assert len(payload['items']) == 156
    assert not any(item['category'] == 'consumable' for item in payload['items'])
    for item in payload['items']:
        assert item['image'], item['name']
        assert (DATA_ROOT / 's18' / item['image']['local_path']).is_file(), item['name']
        assert (DATA_ROOT / 's18' / item['image']['optimized_local_path']).is_file(), item['name']


def test_s18_charm_cards_render_conditions_costs_and_upgrade_layers():
    javascript = (ROOT / 'static' / 'season-reference.js').read_text(encoding='utf-8')
    stylesheet = (ROOT / 'static' / 'season-reference.css').read_text(encoding='utf-8')

    assert 'function createCharmCard(entry, index, showUpgrades)' in javascript
    assert "appendCharmEffect(card, '升级效果'" in javascript
    assert "appendCharmEffect(card, '棱彩效果'" in javascript
    assert 'data.category !== filters.category' in javascript
    assert 'data.requires || []' in javascript
    assert '.charm-card-header' in stylesheet
    assert '.charm-icon' in stylesheet
    assert '.charm-categories' in stylesheet


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
    assert 'class="scale-chip scale-chip-ap"' in html
    assert 'aria-label="法术加成"' in html
    assert '/static/season-stats/ap.png' in html
    assert 'class="scale-chip scale-chip-ad"' in html
    assert '/static/season-stats/ad.png' in html
    assert '&lt;x&gt;' in html

    extended = str(format_skill_description('获得100(【生命上限】)、20(【护甲】)和10(【魔法抗性】)'))
    assert 'scale-chip-health' in extended
    assert 'scale-chip-armor' in extended
    assert 'scale-chip-magic-resist' in extended

    detail = build_champion_detail('s16_5', find_champion_id_by_name('s16_5', '佛耶戈'))
    for variable in detail['champion']['skill']['variables']:
        assert ':' not in variable['label'] and '：' not in variable['label']
        assert '【' not in variable['label']


def test_rich_text_normalizes_s18_and_chinese_stat_markers():
    s18 = parse_rich_text('获得【AP】、【HP】、【AS】并降低【DR】伤害')
    chinese = parse_rich_text('获得【法术加成】、【生命上限】、【攻击速度】并获得【伤害减免】')
    wood_spirit = parse_rich_text('木灵加成：召唤额外0()个木灵')

    assert [token['stat'] for token in s18 if token['type'] == 'stat'] == [
        'ability_power', 'health', 'attack_speed', 'damage_reduction',
    ]
    assert [token['stat'] for token in chinese if token['type'] == 'stat'] == [
        'ability_power', 'health', 'attack_speed', 'damage_reduction',
    ]
    assert [token['source_label'] for token in s18 if token['type'] == 'stat'] == ['AP', 'HP', 'AS', 'DR']
    assert [token['stat'] for token in wood_spirit if token['type'] == 'stat'] == ['wood_spirit_bonus']
    assert next(token for token in wood_spirit if token['type'] == 'stat')['icon'] == 'amp'
    assert wood_spirit[0]['value'].endswith('0(')
    assert wood_spirit[-1]['value'].startswith(')个木灵')


def test_stat_marker_images_are_local_and_background_free():
    for icon in ('ap', 'amp', 'critmult', 'da', 'dr', 'manaregen', 'serpent', 'soul', 'sv'):
        path = ROOT / 'static' / 'season-stats' / f'{icon}.png'
        assert path.is_file()
        with Image.open(path) as image:
            assert image.format == 'PNG'

    ixtal_path = ROOT / 'static' / 'season-stats' / 'ixtal.svg'
    assert ixtal_path.is_file()
    assert '<svg' in ixtal_path.read_text(encoding='utf-8')

    javascript = (ROOT / 'static' / 'season-champion-ui.js').read_text(encoding='utf-8')
    assert "'ixtal.svg', '太阳碎片'" in javascript
    assert r"/\.[a-z0-9]+$/i.test(iconName)" in javascript

    rendered = str(render_rich_text(
        '【暴击伤害】【法力回复】【全能吸血】【伤害增幅】【伤害减免】【灵魂】【银蛇币】【太阳碎片】'
    ))
    for filename in ('critmult.png', 'manaregen.png', 'sv.png', 'da.png', 'dr.png', 'soul.png', 'serpent.png', 'ixtal.svg'):
        assert f'/static/season-stats/{filename}' in rendered

    css = (ROOT / 'static' / 'season-reference.css').read_text(encoding='utf-8')
    assert '.scale-chip {' in css
    assert 'background: transparent;' in css
    assert 'border: 0;' in css


def test_s17_wood_spirit_tokens_use_amp_asset():
    champions = json.loads((DATA_ROOT / 's17' / 'champions.json').read_text(encoding='utf-8'))['champions']
    wood_token_contexts = [
        (tokens[index - 1], token, tokens[index + 1])
        for champion in champions
        for skill in champion.get('skills', [])
        for tokens in [skill.get('description_tokens', [])]
        for index, token in enumerate(tokens)
        if token.get('stat') == 'wood_spirit_bonus'
    ]
    assert wood_token_contexts
    assert {token.get('icon') for _, token, _ in wood_token_contexts} == {'amp'}
    assert all(before.get('value', '').endswith('(') for before, _, _ in wood_token_contexts)
    assert all(after.get('value', '').startswith(')') for _, _, after in wood_token_contexts)


def test_special_champions_are_prioritized_within_cost_groups():
    javascript = (ROOT / 'static' / 'season-reference.js').read_text(encoding='utf-8')
    assert "b.availability?.type === 'special'" in javascript
    assert "a.availability?.type === 'special'" in javascript


def test_every_season_emits_rich_text_tokens_and_board_unit_document():
    for season in catalog_seasons():
        season_root = DATA_ROOT / season['season_id']
        board_units_path = season_root / 'board_units.json'
        assert board_units_path.is_file()
        board_units = json.loads(board_units_path.read_text(encoding='utf-8')).get('board_units') or []
        assert season['counts']['board_units'] == len(board_units)
        for unit in board_units:
            image = unit['image']
            assert image['optimized_local_path'].endswith('.webp')
            assert (season_root / image['local_path']).is_file()
            assert (season_root / image['optimized_local_path']).is_file()


def test_s16_5_supplements_galio_and_trait_created_towers(client):
    champions = json.loads((DATA_ROOT / 's16_5' / 'champions.json').read_text(encoding='utf-8'))['champions']
    assert len(champions) == 115
    galio = next(champion for champion in champions if champion['name'] == '加里奥')
    assert galio['id'] == '5285'
    assert galio['availability']['type'] == 'unlock'
    assert galio['extensions']['library_visible'] is True
    assert galio['extensions']['simulator_visible'] is True
    assert galio['extensions']['supplemented_from_official_snapshot'] is True

    detail = client.get('/tools/seasons/s16_5/champions/5285')
    assert detail.status_code == 200
    detail_html = detail.get_data(as_text=True)
    assert '解锁条件' in detail_html
    assert '特殊获取' not in detail_html

    board_units = json.loads((DATA_ROOT / 's16_5' / 'board_units.json').read_text(encoding='utf-8'))['board_units']
    tower = next(unit for unit in board_units if unit['name'] == '冰封塔楼')
    rules = tower['placement_rules']
    assert any(rule['min_units'] == 3 and rule['max_count'] == 1 for rule in rules)
    assert all(rule['max_count'] == (1 if rule['min_units'] == 3 else 2) for rule in rules)
    tibbers = next(unit for unit in board_units if unit['name'] == '提伯斯')
    forge = next(unit for unit in board_units if unit['name'] == '海克斯科技锻炉')
    rock = next(unit for unit in board_units if unit['name'] == '岩石')
    assert tibbers['can_equip'] is True
    assert tibbers['trait_ids'] == ['355']
    assert tibbers['contribution_trait_ids'] == ['300']
    assert tibbers['extensions']['discovery_sources'] == [
        {'type': 'trait', 'id': '355', 'name': '黑暗之女'},
    ]
    assert forge['placement_rules'] == [
        {'champion_id': '5402', 'min_units': 1, 'max_units': None, 'max_count': 1},
    ]
    assert forge['extensions']['discovery_sources'] == [
        {'type': 'champion_skill', 'id': '5402', 'name': '杰斯'},
    ]
    assert rock['can_equip'] is False
    assert rock['placement_rules'][0]['max_count'] == 2
    public_names = {
        champion['name']
        for champion in json.loads((DATA_ROOT / 's16_5' / 'index.json').read_text(encoding='utf-8'))['champions']
    }
    assert '冰封塔楼' not in public_names


def test_s17_emits_relic_and_black_hole_as_simulator_only_board_units():
    board_units = json.loads((DATA_ROOT / 's17' / 'board_units.json').read_text(encoding='utf-8'))['board_units']
    by_name = {unit['name']: unit for unit in board_units}
    assert {'圣物', '羊咩咩 & 咩咩羊', '迷你黑洞'} <= set(by_name)
    shepherd_summon = by_name['羊咩咩 & 咩咩羊']
    assert shepherd_summon['source_ids']['official_ids'] == ['8407', '8408', '8422']
    assert shepherd_summon['placement_rules'] == [
        {'trait_id': '319', 'min_units': 3, 'max_units': 4, 'max_count': 1},
        {'trait_id': '319', 'min_units': 5, 'max_units': 6, 'max_count': 1},
        {'trait_id': '319', 'min_units': 7, 'max_units': None, 'max_count': 1},
    ]
    assert shepherd_summon['extensions']['discovery_sources'] == [
        {'type': 'trait', 'id': '319', 'name': '牧羊人'},
    ]
    assert all(unit['extensions']['library_visible'] is False for unit in by_name.values())
    assert all(unit['extensions']['simulator_visible'] is True for unit in by_name.values())


def test_board_unit_discovery_audit_includes_released_s18_objects():
    for season_id in ('s8', 's16_5', 's17', 's18'):
        payload = json.loads((DATA_ROOT / season_id / 'board_units.json').read_text(encoding='utf-8'))
        audit = payload.get('discovery_audit') or {}
        assert audit['strategy_version'] == 2
        assert audit['candidate_count'] == audit['included_count'] + audit['review_count']
        assert all(candidate['status'] in {'included', 'review'} for candidate in audit['candidates'])

    s18 = json.loads((DATA_ROOT / 's18' / 'board_units.json').read_text(encoding='utf-8'))
    by_name = {unit['name']: unit for unit in s18['board_units']}
    assert set(by_name) == {'威朗普', '石皮树', '生命花', '深林守卫'}
    assert by_name['威朗普']['trait_ids'] == ['456']
    assert by_name['石皮树']['trait_ids'] == ['450']
    assert by_name['生命花']['trait_ids'] == ['450']
    assert by_name['深林守卫']['trait_ids'] == ['450']
    assert by_name['威朗普']['placement_rules'][0] == {'trait_id': '456', 'min_units': 3, 'max_units': 4, 'max_count': 1}
    assert by_name['石皮树']['placement_rules'][0] == {'trait_id': '450', 'min_units': 3, 'max_units': 4, 'max_count': 1}
    assert by_name['深林守卫']['placement_rules'][0]['min_units'] == 7
    assert by_name['威朗普']['skill']['name'] == '恐惧咆哮 / 大闹奇境'
    assert '<active:' not in by_name['威朗普']['skill']['name']
    review_names = {
        candidate['name'] for candidate in s18['discovery_audit']['candidates']
        if candidate['status'] == 'review'
    }
    assert review_names == {'木桩假人'}


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


def test_released_seasons_publish_official_augments_with_local_images():
    expected_counts = {'s8': 322, 's16_5': 298, 's17': 277, 's18': 258}
    expected_observed_counts = {'s8': 0, 's16_5': 265, 's17': 243, 's18': 0}
    allowed_categories = {'economy', 'combat', 'equipment', 'trait', 'exclusive', 'other'}
    for season_id, expected_count in expected_counts.items():
        season_root = DATA_ROOT / season_id
        document = json.loads((season_root / 'augments.json').read_text(encoding='utf-8'))
        assert len(document['augments']) == expected_count
        assert document['source']['type'] == 'official_jkzlk_hex'
        assert document['source']['url'].startswith('https://game.gtimg.cn/')
        assert 'datatft' not in document['source']['url'].lower()
        assert document['stage_options'] == ['2-1', '3-2', '4-2']
        assert document['stage_source']['type'] == 'dataj_observed_match_rounds'
        assert document['stage_source']['record_count'] == expected_observed_counts[season_id]
        assert document['stage_source']['provenance_note'] == '版本化实战样本观察结果，并非腾讯官方逐条配置'
        assert (season_root / document['stage_source']['snapshot_path']).is_file()
        for augment in document['augments']:
            assert augment['category'] in allowed_categories
            assert augment['name'] and augment['description']
            assert augment['image']['source_url'].startswith('https://game.gtimg.cn/')
            assert (season_root / augment['image']['local_path']).is_file()
            assert (season_root / augment['image']['optimized_local_path']).is_file()
            assert set(augment['appearance_stages']) <= {'2-1', '3-2', '4-2'}

    s8 = json.loads((DATA_ROOT / 's8' / 'augments.json').read_text(encoding='utf-8'))['augments']
    assert sum(augment['augment_type'] == 'hero' for augment in s8) == 122
    assert all(augment['category'] == 'exclusive' for augment in s8 if augment['augment_type'] == 'hero')
    s16 = json.loads((DATA_ROOT / 's16_5' / 'augments.json').read_text(encoding='utf-8'))
    assert s16['source']['requested_version'] == '17.17.8b'
    assert s16['source']['resolved_version'] == '17.17.8'
    assert s16['source']['used_base_patch_fallback'] is True

    s17 = json.loads((DATA_ROOT / 's17' / 'augments.json').read_text(encoding='utf-8'))['augments']
    stages_by_name = {augment['name']: augment['appearance_stages'] for augment in s17}
    assert stages_by_name['蔓延之根'] == ['2-1']
    assert stages_by_name['四费增援'] == ['4-2']
    assert stages_by_name['专属定制'] == ['3-2', '4-2']
    assert stages_by_name['便携锻炉'] == ['2-1', '3-2', '4-2']
    assert stages_by_name['玻璃大炮 I'] == ['3-2', '4-2']
    assert len({tuple(stages) for stages in stages_by_name.values()}) > 4

    s8_unavailable = [
        augment for augment in s8
        if augment['extensions']['appearance_stage_source'] == 'stage_data_unavailable'
    ]
    assert len(s8_unavailable) == len(s8)
    assert all(not augment['appearance_stages'] for augment in s8_unavailable)

    s18 = json.loads((DATA_ROOT / 's18' / 'augments.json').read_text(encoding='utf-8'))
    assert s18['source']['requested_version'] == '18.18.1c'
    assert s18['source']['resolved_version'] == '18.18.1c'
    assert s18['source']['used_base_patch_fallback'] is False
    assert s18['source']['url'].startswith('https://game.gtimg.cn/')
    assert len(s18['augments']) == 258
    assert all(not augment['appearance_stages'] for augment in s18['augments'])
    assert all(
        augment['extensions']['appearance_stage_source'] == 'stage_data_unavailable'
        for augment in s18['augments']
    )


def test_s18_publishes_official_augments_tab_after_release(client):
    assert (DATA_ROOT / 's18' / 'augments.json').is_file()
    html = client.get('/tools/seasons/s18').get_data(as_text=True)
    assert 'data-view="augments"' in html
    assert 'id="augmentGrid"' in html


def test_released_season_reference_pages_render_augment_filters(client):
    javascript = (ROOT / 'static' / 'season-reference.js').read_text(encoding='utf-8')
    stylesheet = (ROOT / 'static' / 'season-reference.css').read_text(encoding='utf-8')
    for season_id in ('s8', 's16_5', 's17', 's18'):
        html = client.get(f'/tools/seasons/{season_id}').get_data(as_text=True)
        assert 'data-view="augments"' in html
        assert 'id="augmentSearch"' in html
        assert 'class="augment-filter-bar"' in html
        assert 'id="augmentTierFilters"' in html
        assert 'id="augmentStageFilters"' in html
        assert 'id="augmentCategoryFilters"' in html
        assert 'id="augmentGrid"' in html

    assert "state[stateKey] = state[stateKey] === option.value ? 'all' : option.value;" in javascript
    assert "const AUGMENT_STAGE_ORDER = ['2-1', '3-2', '4-2'];" in javascript
    assert "const AUGMENT_CATEGORY_ORDER = ['economy', 'combat', 'equipment', 'trait', 'exclusive', 'other'];" in javascript
    assert 'container.hidden = options.length === 0;' in javascript
    assert '全部等级' not in javascript
    assert '全部时机' not in javascript
    assert '全部分类' not in javascript
    filter_rule = stylesheet.split('.augment-filter-group {', 1)[1].split('}', 1)[0]
    assert 'overflow-x' not in filter_rule


def test_augment_classifier_keeps_inference_rules_explicit():
    from scripts.season_library.official_augments import _observed_game_version, build_change_report, classify_augment

    assert classify_augment({'name': '明智消费', 'desc': '刷新商店时获得经验值'}, 'standard') == 'economy'
    assert classify_augment({'name': '便携锻炉', 'desc': '获得一个神器锻造器'}, 'standard') == 'equipment'
    assert classify_augment({'name': '斗士之徽', 'desc': '获得一个斗士纹章'}, 'standard') == 'trait'
    assert classify_augment({'name': '叠上叠', 'desc': '提供一个内瑟斯'}, 'hero') == 'exclusive'
    assert classify_augment({'name': '三阶段强化', 'desc': '强化符文改变出现阶段'}, 'special') == 'other'
    assert _observed_game_version('17.17.8') == '17.8'
    assert _observed_game_version('17.17.8b') == '17.8b'

    previous = {'version_id': 'v1', 'augments': [{'id': '1', 'name': '测试', 'image': {
        'local_path': 'assets/augments/1.png', 'source_url': 'https://game.gtimg.cn/1.png',
        'alt': '测试', 'optimized_local_path': 'assets/optimized/v1/augments/1.webp',
    }}]}
    current = {'version_id': 'v1', 'augments': [{'id': '1', 'name': '测试', 'image': {
        'local_path': 'assets/augments/1.png', 'source_url': 'https://game.gtimg.cn/1.png', 'alt': '测试',
    }}]}
    assert build_change_report(previous, current)['summary']['changed'] == 0
