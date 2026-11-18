"""Offline HAR import contract; fixtures contain no real browser/session data."""
import base64
import io
import json
import shutil
import subprocess

import pytest
from PIL import Image

from scripts.season_library.import_datatft_har import build, build_records, display_text, decode_har
from scripts.season_library.build_upload_package import build_package


@pytest.fixture
def capture(tmp_path):
    if not shutil.which('node'):
        pytest.skip('HAR conversion requires Node.js built-in crypto')
    data = {
        'databaseUpdateTime': 1794804376278,
        'heros19': [{'chessId': 919060, 'displayName': '伊莉丝', 'price': 1, 'raceIds': '1', 'jobIds': '1',
                     'lifeData': '700/1260/2268', 'attackData': '50/75/113', 'armor': 40, 'spellBlock': 40,
                     'attackSpeed': '0.6', 'attackRange': 1, 'startMagic': 40, 'magic': 100,
                     'skillName': '结茧', 'skillDetail2': '造成魔法伤害，晕眩1.5秒。',
                     'unlockDesc': '携带xx件装备', 'otherNames': ['Elise']}],
        'races19': [{'raceId': 1, 'name': '离子火花', 'key': 'DA_19_IonicSpark', 'introduce': '测试羁绊',
                     'level': [{'level': 3, 'levelStyle': 1, 'levelDesc': '100生命值'}]}],
        'jobs19': [{'jobId': 1, 'name': '泰坦', 'key': 'DA_19_Titan', 'introduce': '', 'level': []}],
        'equips19': [{'equipId': 501, 'name': '暴风大剑', 'type2': 'part', 'key': 'DA_BF', 'effect': '攻击力+10%'}],
        'hexs19': [[{'hexId': 'DA_Test', 'name': '测试', 'desc': '测试效果', 'round': ['2-1']},
                   {'hexId': 'preview-K|DA之心', 'name': 'K/DA之心', 'desc': '测试占位'}], [], []],
        'charms19': [{'key': 'DA_18_old'}], 'charms18': [{'key': 'DA_18_old'}],
    }
    key = base64.b64encode(b'0123456789abcdef').decode()
    encrypted = subprocess.run(['node', '-e', "const c=require('crypto');let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{const d=c.createCipheriv('aes-128-ecb',Buffer.from('0123456789abcdef'),null);process.stdout.write(Buffer.concat([d.update(s),d.final()]).toString('base64'));});"],
                               input=json.dumps(data, ensure_ascii=False), text=True, encoding='utf-8', capture_output=True, check=True).stdout
    raw_img = io.BytesIO()
    Image.new('RGB', (64, 32), '#a84590').save(raw_img, format='JPEG')

    def entry(url, text, encoded=False):
        return {'request': {'url': url, 'cookies': [{'name': 'private', 'value': 'DO-NOT-EXPORT-SESSION'}]},
                'response': {'status': 304, 'content': {'text': text, **({'encoding': 'base64'} if encoded else {})}}}

    entries = [
        entry('https://www.datatft.com/assets/bootstrap-test.js', 'const H={currentData:null,key:"' + key + '"};'),
        entry('https://www.datatft.com/assets/data-cn-test.js', f'const c="{encrypted}";export{{c as data}};'),
        entry('https://static.datatft.com/images/heros/bg/test/919060.jpg', base64.b64encode(raw_img.getvalue()).decode(), True),
        entry('https://www.datatft.com/assets/icons.js', '<symbol id="custom-trait-DA_19_IonicSpark" viewBox="0 0 100 100"><path d="M0 0H100V100Z"/></symbol>'),
    ]
    path = tmp_path / 'capture.har'
    path.write_text(json.dumps({'log': {'entries': entries}}), encoding='utf-8')
    return path


def test_offline_har_to_valid_package_preserves_source_and_missing_values(capture, tmp_path, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **k: pytest.fail('import must be offline'))
    root = tmp_path / 'prepared'
    report = build(capture, root, register=True)
    season = root / 's19'
    hero = json.loads((season / 'champions.json').read_text(encoding='utf-8'))['champions'][0]
    assert hero['stats_by_star']['1']['initial_mana'] == 40
    assert hero['stats_by_star']['1']['max_mana'] == 100
    assert hero['trait_ids'] == ['origin-1', 'class-1']
    assert hero['availability']['description'] == '携带xx件装备'
    assert hero['skills'][0]['variables'] == []
    item = json.loads((season / 'items.json').read_text(encoding='utf-8'))['items'][0]
    assert item['category'] == 'component'
    assert report['incomplete_unlocks'] == 1 and report['charms_equal_s18'] is True
    assert report['hero_images'] == 1 and report['trait_images'] == 1
    assert report['missing_images']['traits'] == ['class-1']
    catalog = json.loads((root / 'catalog.json').read_text(encoding='utf-8'))
    assert catalog['seasons'][0]['status'] == 'hidden'
    assert catalog['seasons'][0]['game_version'] == 'PBE'
    for path in season.glob('*.json'):
        assert 'DO-NOT-EXPORT-SESSION' not in path.read_text(encoding='utf-8')
    notes = json.loads((season / 'release-notes.json').read_text(encoding='utf-8'))
    manifest, _ = build_package(season, tmp_path / 'pbe.zip', 1, notes)
    assert manifest['game_version'] == 'PBE'
    assert manifest['modules']['board_units']['state'] == 'absent'
    with pytest.raises(ValueError, match='已存在'):
        build(capture, root, register=True)


def test_incomplete_capture_does_not_register_or_leave_half_season(tmp_path):
    path = tmp_path / 'empty.har'
    path.write_text('{"log":{"entries":[]}}', encoding='utf-8')
    with pytest.raises(ValueError, match='完整录制'):
        build(path, tmp_path / 'out', register=True)
    assert not (tmp_path / 'out/s19').exists()
    assert not (tmp_path / 'out/catalog.json').exists()


def test_display_text_keeps_numbers_and_drops_executable_markup():
    assert display_text('造成120伤害<br>持续1.5秒<script>alert(1)</script>') == '造成120伤害\n持续1.5秒'
    assert display_text('<tftitemrules>规则</tftitemrules>【DIST】【SV】+15%') == '规则 【全能吸血】+15%'


def test_old_emblems_are_preserved_but_cannot_grant_invented_traits(capture):
    data, *_ = decode_har(capture)
    data['equips19'].append({'equipId': 33019, 'name': '旧羁绊纹章', 'key': 'DA_18_Old',
                             'type2': 'zhuanzhi', 'effect': '获得旧羁绊'})
    rows = build_records(data, {}, {}, {'local_path': 'assets/missing.png', 'placeholder': True})
    old = rows['items'][-1]
    assert old['category'] == 'emblem'
    assert old['extensions']['datatft'] == data['equips19'][-1]
    assert old['extensions']['simulator_visible'] is False
    assert old['extensions']['trait_id'] is None


def test_pbe_stays_hidden_until_explicit_preview_policy(client):
    assert client.get('/tools/seasons/s19').status_code == 404
    assert client.get('/static/season-data/s19/index.json').status_code == 404


def test_multiple_captures_supply_dedicated_portraits(capture, tmp_path):
    second = json.loads(capture.read_text(encoding='utf-8'))
    portrait = second['log']['entries'].pop(2)
    portrait['request']['url'] = 'https://static.datatft.com/images/heros/default/test/919060.jpg'
    second['log']['entries'].append(portrait)
    other = tmp_path / 'other.har'
    other.write_text(json.dumps(second), encoding='utf-8')
    report = build([capture, other], tmp_path / 'merged')
    hero = json.loads((tmp_path / 'merged/s19/champions.json').read_text(encoding='utf-8'))['champions'][0]
    assert report['source']['capture_count'] == 2
    assert report['hero_icons'] == report['hero_images'] == 1
    assert '/icons/' in hero['images']['icon']['local_path']
    assert '/splash/' in hero['images']['splash']['local_path']


def test_conflicting_captures_fail_without_partial_output(capture, tmp_path, monkeypatch):
    import copy
    from scripts.season_library import import_datatft_har as importer
    decoded = decode_har(capture)
    changed = copy.deepcopy(decoded)
    changed[0]['heros19'][0]['magic'] = 999
    captures = iter([decoded, changed])
    monkeypatch.setattr(importer, 'decode_har', lambda path: next(captures))
    with pytest.raises(ValueError, match='不一致'):
        build([capture, capture], tmp_path / 'conflict', register=True)
    assert not (tmp_path / 'conflict/s19').exists()
    assert not (tmp_path / 'conflict/catalog.json').exists()


def test_pbe_simulator_rules_and_serialization():
    if not shutil.which('node'):
        pytest.skip('requires Node.js')
    result = subprocess.run(['node', 'tests/simulator_pbe_rules.cjs'], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr


def test_inherited_modules_are_self_contained_and_do_not_grant_old_traits(capture, tmp_path):
    previous_root = tmp_path / 'previous'
    build(capture, previous_root)
    previous = previous_root / 's19'
    index_path = previous / 'index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    index.update(season_id='s18', version_id='s18__test', game_version='18.test')
    index_path.write_text(json.dumps(index), encoding='utf-8')
    items_path = previous / 'items.json'
    items = json.loads(items_path.read_text(encoding='utf-8'))
    for ident, trait in [('known', 'origin-1'), ('old', 'old-trait')]:
        item = json.loads(json.dumps(items['items'][0]))
        item.update(id=ident, name=ident + '纹章', category='emblem')
        item['extensions'] = {'fetter_id': trait}
        items['items'].append(item)
    items_path.write_text(json.dumps(items), encoding='utf-8')
    before = items_path.read_bytes()
    output = tmp_path / 'inherited'
    report = build(capture, output, inherit_from=previous)
    season = output / 's19'
    rows = json.loads((season / 'items.json').read_text(encoding='utf-8'))['items']
    assert rows[1]['extensions']['trait_id'] == 'origin-1'
    assert rows[1]['extensions']['simulator_visible'] is True
    assert rows[2]['extensions']['trait_id'] is None
    assert rows[2]['extensions']['fetter_id'] is None
    assert rows[2]['extensions']['simulator_visible'] is False
    assert rows[0]['extensions']['inherited_from']['season_id'] == 's18'
    assert report['inherited_modules']['version_id'] == 's18__test'
    assert items_path.read_bytes() == before
    assert (season / rows[0]['image']['local_path']).is_file()
    assert rows[0]['image']['local_path'].startswith('assets/inherited/')
    notes = json.loads((season / 'release-notes.json').read_text(encoding='utf-8'))
    build_package(season, tmp_path / 'inherited.zip', 2, notes)


@pytest.mark.parametrize('levels,heroes,expected', [
    ([(1, 3)], [1], ['unique']),
    ([(2, 3)], [1, 2], ['gold']),
    ([(1, 1), (2, 3)], [1], ['bronze', 'gold']),
    ([(1, 3)], [], ['gold']),
    ([(1, 4)], [1], ['prismatic']),
])
def test_trait_frame_matches_captured_component(capture, levels, heroes, expected):
    import copy
    data, *_ = decode_har(capture)
    trait = data['races19'][0]
    trait['heros'] = heroes
    trait['level'] = [{'level': n, 'levelStyle': style, 'levelDesc': '测试'} for n, style in levels]
    original = copy.deepcopy(trait)
    rows = build_records(data, {}, {}, {'local_path': 'assets/missing.png', 'placeholder': True})
    result = rows['traits'][0]
    assert [p['style'] for p in result['breakpoints']] == expected
    assert result['category'] == 'origin'
    assert result['extensions']['datatft'] == original
    assert trait == original


def test_asset_only_capture_never_replaces_newer_records(capture, tmp_path, monkeypatch):
    import copy
    from scripts.season_library import import_datatft_har as importer
    current = decode_har(capture)
    old = copy.deepcopy(current)
    old[0]['heros19'][0]['displayName'] = '旧英雄名'
    old[3]['har_sha256'] = 'old-images-only'
    red = io.BytesIO()
    Image.new('RGB', (64, 32), '#ff0000').save(red, format='JPEG')
    old[1][2]['response']['content']['text'] = base64.b64encode(red.getvalue()).decode()
    icon = copy.deepcopy(old[1][2])
    icon['request']['url'] = 'https://static.datatft.com/images/heros/default/test/919060.jpg'
    old[1].append(icon)
    monkeypatch.setattr(importer, 'decode_har', lambda path: old if str(path) == 'old' else current)
    report = build(capture, tmp_path / 'assets-only', asset_hars=['old'])
    root = tmp_path / 'assets-only/s19'
    hero = json.loads((root / 'champions.json').read_text(encoding='utf-8'))['champions'][0]
    assert hero['name'] == '伊莉丝'
    assert hero['extensions']['datatft'] == current[0]['heros19'][0]
    assert report['source']['asset_capture_sha256'] == ['old-images-only']
    assert report['source']['capture_count'] == 1
    assert (root / hero['images']['splash']['local_path']).read_bytes() == base64.b64decode(current[1][2]['response']['content']['text'])
    assert (root / hero['images']['icon']['local_path']).read_bytes() == red.getvalue()
