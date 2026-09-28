"""Standalone, frozen equipment recommendations independent of season releases."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def recommendation_guide():
    source = Path(__file__).resolve().parent / 'static/tools/s11-items/data.json'
    data = json.loads(source.read_text(encoding='utf-8'))
    groups = []
    for cost in range(5, 0, -1):
        champions = []
        for row in data['champions']:
            if row['cost'] != cost:
                continue
            equipment = [data['items'][key] for key in [*row['recommended'], row['alternative']]]
            search = [row['name'], *row['traits']]
            for item in equipment:
                search.extend([item['name'], *(c['name'] for c in item['components'])])
            champions.append({**row, 'equipment': equipment, 'search': ' '.join(search)})
        groups.append({'cost': cost, 'champions': champions})
    return groups
