import json
from functools import lru_cache
from pathlib import Path


DATA_ROOT = Path(__file__).resolve().parent / 'static' / 's18-preview'


@lru_cache(maxsize=1)
def load_s18_preview_data():
    champions = json.loads((DATA_ROOT / 'champions.json').read_text(encoding='utf-8'))
    traits = json.loads((DATA_ROOT / 'traits.json').read_text(encoding='utf-8'))
    return champions, traits


def champion_names():
    champions, _ = load_s18_preview_data()
    return [champion['名称'] for champion in champions]


def build_champion_detail(champion_name):
    champions, traits = load_s18_preview_data()
    champion = next((item for item in champions if item['名称'] == champion_name), None)
    if champion is None:
        return None

    trait_map = {trait['名称']: trait for trait in traits}
    champion_traits = []
    for trait_name in champion['羁绊']:
        trait = trait_map.get(trait_name)
        if trait is None:
            continue
        champion_traits.append({
            **trait,
            '弈子': [item for item in champions if trait_name in item['羁绊']],
        })

    return {
        'champion': champion,
        'traits': champion_traits,
    }
