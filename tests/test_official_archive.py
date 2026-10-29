import json

from scripts.season_library.official_archive import build, build_champions, build_items, build_traits, skill_variables
from scripts.season_library import import_from_archive


def hero(record_id, **extra):
    return {'id': record_id, 'name': '璐璐', 'class': '300', 'species': '351', 'heroPaint': 's16_lulu', 'heroType': '0',
            'picture': 'https://example.invalid/head.png', 'skillIcon': 'https://example.invalid/skill.png',
            'price': '1', 'showHeroTag': '1', 'setid': '16', 'initHP': '500', 'skillName': '奇思妙想',
            'skillDesc': f'星级{record_id[0]}', 'skillValueDesc': '伤害：1000(【法术加成】) 300/450/700/1000', 'tftHeroId': '11405',
            **extra}


def test_skill_values_keep_position_and_skip_irregular_segments():
    raw = '攻击速度：10%=10%+1%每6【灵魂】|伤害：165(【物理加成】) 55/85/125/165|流星数量 12/12/24/40'
    assert skill_variables(raw) == [
        {'key': 'value_2', 'label': '伤害', 'unit': 'raw', 'values': {'1': '55', '2': '85', '3': '125', '4': '165'}},
        {'key': 'value_3', 'label': '流星数量 12/12/24/40', 'unit': 'raw', 'values': {'1': '12', '2': '12', '3': '24', '4': '40'}},
    ]
    assert skill_variables(None) == []


def test_champions_split_shop_and_mission_unlocks_by_official_id():
    chess = {'data': {r['id']: r for r in [hero('11405'), hero('21405'), hero('12400', name='约里克'),
                                           hero('15000', price='0'), hero('15001', showHeroTag='0')]}}
    missions = {'data': {'12400': {'heroid': 12400, 'mission': [{'id': 1240001, 'tasktips': '', 'desc': '在战斗中登场', 'sort': 39,
                                                                  'difficulty': 0, 'conditionId': 0}]}}}
    champions, downloads = build_champions(chess, missions, '16', 'mode16s400001', {'1405'}, {'351', '300'})
    assert [c['id'] for c in champions] == ['1405', '2400']
    lulu, yorick = champions
    assert lulu['availability']['type'] == 'shop' and lulu['tags'] == []
    assert list(lulu['stats_by_star']) == ['1', '2'] and lulu['source_ids']['record_ids'] == ['11405', '21405']
    assert lulu['skills'][0]['extensions']['description_by_star'] == {'1': '星级1', '2': '星级2'}
    assert yorick['availability']['type'] == 'unlock' and yorick['availability']['rules'][0]['params']['task_tips'] is None
    assert yorick['tags'] == ['new']
    assert ('https://game.gtimg.cn/images/jk/jkimg/mode16s400001/1624x750/s16_lulu.jpg', 'assets/champions/splash/1405.jpg') in downloads


def test_unknown_trait_ids_stay_unresolved_instead_of_dropped_silently():
    chess = {'data': {'14335': hero('14335', species='349', **{'class': '0'})}}
    champion = build_champions(chess, None, '16', 'mode16s18', None, {'349'})[0][0]
    assert champion['trait_ids'] == ['349']
    assert champion['extensions']['official_unresolved_trait_ids'] == ['0']
    assert champion['tags'] == []


def test_traits_breakpoints_and_single_text_for_every_tier():
    race = {'data': {'349': {'id': '349', 'name': '巨神峰', 'color': '3|3', 'numList': '1|2', 'desc2': '星辰铸就。',
                             'prefix': '星辰铸就。', 'picture': 'https://example.invalid/t.png', 'tftSpecId': '10003', 'mapID': '10'}}}
    job = {'data': {'291': {'id': '291', 'name': '斗士', 'color': '1|2|5', 'numList': '2|4|6', 'desc2': '(2)A|(4)B|(6)C',
                            'prefix': '前缀', 'picture': 'https://example.invalid/b.png', 'tftClassId': '10011', 'mapID': '1'}}}
    traits, _ = build_traits(race, job)
    targon, brawler = traits
    assert [b['effect'] for b in targon['breakpoints']] == ['星辰铸就。', '星辰铸就。']
    assert brawler['category'] == 'class' and brawler['source_ids']['tft_spec_id'] == '10011'
    assert [(b['min_units'], b['max_units'], b['style']) for b in brawler['breakpoints']] == [(2, 3, 'bronze'), (4, 5, 'silver'), (6, None, 'unique')]


def test_items_parse_stats_recipe_and_unique_flag():
    equip = {'data': {'2025': {'id': '2025', 'name': '振奋盔甲', 'type': '成型装备', 'basicDesc': '+300生命上限 +8%伤害减免',
                               'desc': '每秒回复。', 'synthesis1': '1004', 'synthesis2': '1007', 'picture': 'https://example.invalid/i.png'},
                      '9001': {'id': '9001', 'name': '神器', 'type': '神器装备', 'basicDesc': '', 'desc': '唯一：只能装备一件。',
                               'synthesis1': '', 'synthesis2': '', 'picture': 'https://example.invalid/a.png'}}}
    armor, artifact = build_items(equip)[0]
    assert armor['stats']['values'] == [{'stat': 'health', 'source_label': '生命上限', 'value': 300, 'unit': 'flat'},
                                        {'stat': 'damage_reduction', 'source_label': '伤害减免', 'value': 8, 'unit': 'percent'}]
    assert armor['recipe'] == {'type': 'components', 'component_ids': ['1004', '1007'], 'description': None}
    assert artifact['stats'] == {'raw': '', 'values': []} and artifact['unique'] and artifact['recipe']['type'] == 'none'


def test_emblem_without_fetter_id_uses_the_trait_named_in_its_text():
    equip = {'data': {'41601': {'id': '41601', 'name': '比尔吉沃特纹章', 'type': '转职纹章', 'basicDesc': '', 'fetterID': '',
                                'desc': '携带者获得【比尔吉沃特】特质/职业。', 'synthesis1': '1008', 'synthesis2': '1004', 'picture': ''},
                      '41699': {'id': '41699', 'name': '未知纹章', 'type': '转职纹章', 'basicDesc': '', 'fetterID': '',
                                'desc': '携带者获得【不存在】特质/职业。', 'picture': ''}}}
    known, unknown = build_items(equip, {'比尔吉沃特': '340'})[0]
    assert known['extensions']['fetter_id'] == '340' and known['extensions']['fetter_id_source'] == 'description'
    assert unknown['extensions']['fetter_id'] is None and 'fetter_id_source' not in unknown['extensions']


def test_build_writes_season_archive_with_creator_surface(tmp_path, monkeypatch):
    official = tmp_path / 'official'
    branch = official / 'parsed/16/18.18.1-S400001'
    branch.mkdir(parents=True)
    entry = {'mode': '16', 'season': 'S400001', 'version': '18.18.1', 'version_start_time': '2026-10-13 19:49:20',
             'herourl': '/16/18.18.1-S400001/chess.js'}
    (official / 'selection.json').write_text(json.dumps({'selected': entry}), encoding='utf-8')
    (official / 'manifest.json').write_text(json.dumps({'collected_at': '2026-10-29T12:00:00+08:00'}), encoding='utf-8')
    (branch / 'chess.json').write_text(json.dumps({'data': {'11405': hero('11405')}}), encoding='utf-8')
    summary = build(official, tmp_path / 'archive', 'orange_s400001', '英雄联盟传奇 · 大橘大利', '16', '', '', None,
                    1, 1, 1, skip_assets=True, surface_status={'creator': 'active'})
    assert summary['version_id'] == 'orange_s400001__18_18_1' and summary['champions'] == 1
    season = json.loads((tmp_path / 'archive/data/seasons/orange_s400001/season.json').read_text(encoding='utf-8'))
    assert season['status'] == 'hidden' and season['surface_status'] == {'creator': 'active'}
    version_entry = json.loads((tmp_path / 'archive/data/seasons/orange_s400001/18.18.1/source-snapshots/version-entry.json').read_text(encoding='utf-8'))
    assert version_entry == entry
    from scripts.season_library.official_supplements import _season_code
    assert _season_code(tmp_path / 'archive/data/seasons/orange_s400001/18.18.1', lambda p: json.loads(p.read_text(encoding='utf-8'))) == '400001'
    catalog = json.loads((tmp_path / 'archive/data/catalog.json').read_text(encoding='utf-8'))
    assert catalog['seasons'] == [{'season_id': 'orange_s400001', 'path': 'seasons/orange_s400001/season.json', 'status': 'hidden'}]


def test_single_season_import_keeps_other_catalog_entries(tmp_path, monkeypatch):
    target = tmp_path / 'site'
    target.mkdir()
    (target / 'catalog.json').write_text(json.dumps({'format_version': '1.0.0', 'seasons': [{'season_id': 's18'}]}), encoding='utf-8')
    source = tmp_path / 'src'
    (source / 'data').mkdir(parents=True)
    (source / 'data/catalog.json').write_text(json.dumps({'seasons': [{'season_id': 'orange_s400001'}]}), encoding='utf-8')
    monkeypatch.setattr(import_from_archive, 'import_season', lambda *a, **k: {'season_id': 'orange_s400001', 'display_name': 'x',
                                                                              'game_version': '1', 'counts': {'champions': 0, 'traits': 0, 'mechanics': 0}})
    import_from_archive.main(['--source', str(source), '--season', 'orange_s400001', '--output-root', str(target)])
    catalog = json.loads((target / 'catalog.json').read_text(encoding='utf-8'))
    assert [s['season_id'] for s in catalog['seasons']] == ['s18', 'orange_s400001']
