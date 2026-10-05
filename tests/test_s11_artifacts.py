import hashlib
import json
from pathlib import Path
import re

import pytest

from s11_artifacts_service import artifact_guide, artifact_snapshot

ROOT = Path(__file__).resolve().parents[1]
PAGE = '/tools/s11-artifacts'


def test_frozen_guide_and_image_integrity():
    data = artifact_snapshot()
    assert len(data['artifacts']) == 31
    assert len(data['champions']) == 37
    assert data['version'] == '18.11.1'
    assert len({row['id'] for row in data['artifacts']}) == 31
    assert sum(len(row['champion_ids']) for row in data['artifacts']) == 124
    # These visually similar portraits must not be interchanged.
    by_name = {row['name']: row for row in data['artifacts']}
    assert by_name['斯塔缇克电刃']['id'] == '6088'
    for artifact, names in {
        '投机者之刃': ['艾瑞莉娅', '艾希', '巴德', '厄斐琉斯'],
        '鱼骨头': ['霞', '卡莎', '艾希', '厄斐琉斯'],
        '巫妖之祸': ['莉莉娅', '辛德拉', '拉露恩', '千珏'],
        '黎明核心': ['丽桑卓', '彗', '阿兹尔', '莫甘娜'],
    }.items():
        assert [data['champions'][key]['name'] for key in by_name[artifact]['champion_ids']] == names
    provenance = json.loads((ROOT / 'static/s11-artifacts/provenance.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((ROOT / 'scripts/season_library/sources/s11-artifacts.json').read_text(encoding='utf-8').encode('utf-8')).hexdigest() == provenance['guide_sha256']
    referenced = {row['image'] for row in data['artifacts']} | {row['image'] for row in data['champions'].values()}
    assert len(referenced) == len(provenance['asset_sha256']) == 68
    for image in referenced:
        raw = (ROOT / 'static' / image).read_bytes()
        assert raw.startswith(b'\x89PNG\r\n\x1a\n')
        assert hashlib.sha256(raw).hexdigest() == provenance['asset_sha256'][image.removeprefix('s11-artifacts/')]


def test_search_names_effects_aliases_terms_and_cost_intersection():
    assert artifact_guide('阿兹尔')['count'] == artifact_guide('沙皇')['count'] == 5
    assert artifact_guide('孙悟空')['count'] == 8
    assert artifact_guide('飞升')['count'] == 1
    assert artifact_guide('护盾')['count'] == 3
    assert artifact_guide('护盾 阿兹尔')['count'] == 0
    assert artifact_guide('   飞升  塞拉斯 ' , '4')['count'] == 1
    assert artifact_guide('飞升', '5')['count'] == 0
    assert artifact_guide('', '1')['count'] == 1
    assert artifact_guide('不存在')['count'] == 0
    assert artifact_guide('５０％')['count'] == 2
    assert len(artifact_guide('a' * 150)['query']) == 100


def test_public_page_and_filters_work_without_live_season_data(client, monkeypatch):
    # The guide must remain independent when season releases are unavailable.
    import season_data_repository
    def unavailable(*_args, **_kwargs):
        raise AssertionError('Artifact guide attempted to read a mutable season release')
    monkeypatch.setattr(season_data_repository, 'asset_url', unavailable)
    response = client.get(PAGE)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('class="artifact-card"') == 31
    assert html.count('class="artifact-cost cost-') == 124
    assert '系测试服数据' not in html
    assert '/static/season-data/' not in html
    monkeypatch.undo()  # The shared sitemap/home legitimately enumerate other seasons.
    assert PAGE in client.get('/sitemap.xml').get_data(as_text=True)
    assert client.get('/').get_data(as_text=True).count(f'href="{PAGE}"') == 2
    for src in set(re.findall(r'<img src="([^"]+)"', html)):
        assert src.startswith('/static/s11-artifacts/')
        assert client.get(src).status_code == 200
    filtered = client.get(PAGE + '?q=飞升&cost=1').get_data(as_text=True)
    assert '找到 1 / 31 件神器' in filtered
    assert filtered.count(' hidden>\n            <header class="artifact-card-heading"') == 30
    assert 'content="noindex' in filtered
    assert 'value="1" id="artifactCost"' in filtered
    assert '找到 0 / 31 件神器' in client.get(PAGE + '?q=飞升&cost=5').get_data(as_text=True)
    assert '找到 1 / 31 件神器' in client.get(PAGE + '?q=飞升&cost=5&cost=1').get_data(as_text=True)
    assert client.get(PAGE + '?cost=6').status_code == 400
    assert client.get(PAGE + '?cost=oops').status_code == 400
    escaped = client.get(PAGE, query_string={'q': '<script>alert(1)</script>'}).get_data(as_text=True)
    assert '<script>alert(1)</script>' not in escaped


def test_each_reference_row_agrees_with_generated_snapshot():
    source = json.loads((ROOT / 'scripts/season_library/sources/s11-artifacts.json').read_text(encoding='utf-8'))
    data = artifact_snapshot()
    for expected, row in zip(source['artifacts'], data['artifacts'], strict=True):
        assert (expected['name'], expected['description']) == (row['name'], row['description'])
        assert expected['champions'] == [[data['champions'][key]['name'], data['champions'][key]['cost']] for key in row['champion_ids']]


def test_importer_selects_artifact_when_completed_item_has_same_name(tmp_path, monkeypatch):
    from scripts.season_library import import_s11_artifacts as importer
    snapshot = artifact_snapshot()
    source = tmp_path / 'archive'
    source.mkdir()
    (source / 'version.json').write_text(json.dumps({'season_id': 's11', 'game_version': '18.11.1'}), encoding='utf-8')
    items = []
    champions = []
    for row in snapshot['artifacts']:
        items.append({'id': row['id'], 'name': row['name'], 'category': 'other' if row['id'] == '6091' else 'artifact',
                      'image': {'local_path': row['image']}})
    items.append({'id': '21111', 'name': '斯塔缇克电刃', 'category': 'completed', 'image': {'local_path': 'must-not-copy.png'}})
    for row in snapshot['champions'].values():
        champions.append({'id': row['id'], 'name': row['name'], 'cost': row['cost'], 'images': {'icon': {'local_path': row['image']}}})
    for row in items[:-1]:
        image = source / row['image']['local_path']
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b'fixture-artifact')
    for row in champions:
        image = source / row['images']['icon']['local_path']
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b'fixture-champion')
    (source / 'items.json').write_text(json.dumps({'items': items}, ensure_ascii=False), encoding='utf-8')
    (source / 'champions.json').write_text(json.dumps({'champions': champions}, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(importer, 'ROOT', tmp_path / 'output')
    generated = importer.build(source)
    assert next(row['id'] for row in generated['artifacts'] if row['name'] == '斯塔缇克电刃') == '6088'
    assert not (tmp_path / 'output/static/s11-artifacts/items/21111.png').exists()
    (source / 'version.json').write_text(json.dumps({'season_id': 's11', 'game_version': '18.12.1'}), encoding='utf-8')
    with pytest.raises(ValueError, match='18.11.1'):
        importer.build(source)
