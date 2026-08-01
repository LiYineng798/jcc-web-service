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
