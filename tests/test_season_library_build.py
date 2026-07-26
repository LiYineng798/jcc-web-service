import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'scripts' / 'season_library') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts' / 'season_library'))

from build_simulator_from_library import ITEM_CATEGORY_TABS, dedupe_champions

SIMULATOR_ROOT = ROOT / 'static' / 'tools' / 'lineup-simulator'
LIBRARY_ROOT = ROOT / 'static' / 'season-data'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


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


def test_generated_simulator_data_matches_library():
    version = load(SIMULATOR_ROOT / 'data' / 'version.json')
    season_id = version['set']
    index = load(LIBRARY_ROOT / season_id / 'index.json')
    heroes = load(SIMULATOR_ROOT / 'data' / 'heroes.json')
    trait_names = {trait['id']: trait['name'] for trait in index['traits']}
    assert len(heroes) == len(dedupe_champions(index['champions'], trait_names))
    assert version['version'] == index['game_version']

    traits = load(SIMULATOR_ROOT / 'data' / 'traits.json')
    assert len(traits) == len(index['traits'])
    for trait in traits:
        assert trait['type'] in {'race', 'job'}

    items = load(LIBRARY_ROOT / season_id / 'items.json')['items']
    equips = load(SIMULATOR_ROOT / 'data' / 'equips.json')
    extras_path = SIMULATOR_ROOT / 'extras' / f'{season_id}.json'
    extras_count = len(load(extras_path).get('equips') or []) if extras_path.is_file() else 0
    assert len(equips) == len(items) + extras_count

    tabs = load(SIMULATOR_ROOT / 'data' / 'tabs.json')
    hero_costs = sorted({hero['cost'] for hero in heroes})
    assert tabs['heroCostTabs'] == ['全部', *[f'{cost}费' for cost in hero_costs]]
    for equip in equips:
        assert equip['type'] in tabs['equipTabs']


def test_generated_simulator_images_exist():
    for name in ('heroes', 'equips', 'traits', 'pets'):
        for row in load(SIMULATOR_ROOT / 'data' / f'{name}.json'):
            image = row.get('image')
            assert image, f'{name} entry {row.get("name")} missing image'
            assert (SIMULATOR_ROOT / image).is_file(), f'missing {image}'
            assert (SIMULATOR_ROOT / 'blur' / image).is_file(), f'missing blur/{image}'
