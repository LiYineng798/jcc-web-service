import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'scripts' / 'season_library') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts' / 'season_library'))

from build_simulator_from_library import ITEM_CATEGORY_TABS, dedupe_champions

def test_dedupe_keeps_distinct_trait_forms_and_collapses_skins():
    trait_names = {'a': '羁绊A', 'b': '羁绊B'}
    champions = [
        {'id': '1', 'name': '厄运小姐', 'cost': 3, 'trait_ids': ['a']},
        {'id': '2', 'name': '厄运小姐', 'cost': 3, 'trait_ids': ['b']},
        {'id': '3', 'name': '璐璐', 'cost': 3, 'trait_ids': ['a']},
        {'id': '4', 'name': '璐璐', 'cost': 3, 'trait_ids': ['a']},
    ]
    kept = dedupe_champions(champions, trait_names)
    assert [champion['id'] for champion in kept] == ['1', '2', '3']


def test_item_category_tab_mapping_is_complete():
    assert set(ITEM_CATEGORY_TABS) == {
        'component', 'completed', 'radiant', 'artifact', 'emblem', 'support', 'consumable', 'other',
    }


def test_official_only_augments_never_request_observed_stages(tmp_path, monkeypatch):
    import json
    import official_augments

    snapshot = tmp_path / 'version' / 'source-snapshots'
    snapshot.mkdir(parents=True)
    (snapshot / 'version-entry.json').write_text(json.dumps({
        'version': '18.18.2', 'hexurl': '/18/18.18.2-S19/hex.js',
    }), encoding='utf-8')
    monkeypatch.setattr(official_augments, '_request_hex_document', lambda *args: (
        {'data': {'1': {'id': '1', 'name': '测试强化', 'desc': '获得金币', 'level': '1'}}},
        'https://game.gtimg.cn/images/lol/act/jkzlk/js/18/18.18.2-S19/hex.js', '18.18.2',
    ))
    calls = []
    monkeypatch.setattr(official_augments, '_request_stage_document', lambda *args: calls.append(args))
    monkeypatch.setattr(official_augments, '_download_images', lambda entries: [])
    payload, _ = official_augments.collect_official_augments(
        snapshot.parent, tmp_path / 'output', 's18', 's18__18_18_2', official_only=True,
    )
    assert calls == []
    assert payload['stage_source'] is None
    assert payload['augments'][0]['appearance_stages'] == []
    assert payload['augments'][0]['extensions']['appearance_stage_source'] == 'stage_data_unavailable'
