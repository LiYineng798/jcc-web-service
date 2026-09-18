"""S18 ladder view model; champion assets always use the selected public release."""
import json
import re
from pathlib import Path

from season_data_repository import asset_url, data_directory
from season_visibility import get_season


def reward_tiers():
    return json.loads((Path(__file__).parent / 'static/trait-ladder/rewards.json').read_text(encoding='utf-8'))['tiers']


def calculator_data():
    season = get_season('simulator', 's18') or get_season('library', 's18')
    if not season:
        return None
    root = data_directory('s18')
    base = asset_url('s18')

    def read(name):
        return json.loads((root / f'{name}.json').read_text(encoding='utf-8'))[name]

    def icon(image):
        path = image.get('optimized_local_path') or image.get('local_path')
        return f'{base}/{path}' if path else ''

    raw_traits = read('traits')
    traits = [{'id': t['id'], 'name': t['name'], 'icon': icon(t.get('image', {})),
               'threshold': min((b['min_units'] for b in t['breakpoints']), default=1),
               # Reference tracker marks single-level traits as soleTrait.
               'unique': len(t['breakpoints']) == 1 or t['category'] == 'unique' or any(b['style'] == 'unique' for b in t['breakpoints']),
               'breakpoints': [b['min_units'] for b in t['breakpoints']]}
              for t in raw_traits]
    by_id = {t['id']: t for t in raw_traits}
    by_name = {t['name']: t['id'] for t in raw_traits}
    champions, lux_choices = [], []
    tanks = {'4500', '4502', '4503', '4504', '4505', '5450', '5451', '5452'}
    for c in read('champions'):
        is_lux = c['name'] == '拉克丝'
        if is_lux and len(c['trait_ids']) > 1:
            lux_choices.append({'id': c['trait_ids'][-1], 'championId': c['id']})
            continue
        descriptions = ' '.join(by_id[t]['description'] for t in c['trait_ids'] if t in by_id)
        slots = re.search(r'【' + re.escape(c['name']) + r'】占用(\d+)个弈子栏位', descriptions)
        contribution = {t: 1 for t in c['trait_ids']}
        for count, name in re.findall(r'提供\s*[+＋]\s*(\d+)\s*【([^】]+)】(?:特质|羁绊|职业)', descriptions):
            if name in by_name:
                contribution[by_name[name]] = int(count)
        champions.append({'id': c['id'], 'name': c['name'], 'aliases': c.get('aliases', []),
                          'cost': c['cost'], 'traits': contribution,
                          'slots': int(slots[1]) if slots else 1,
                          'lux': is_lux, 'khazix': c['name'] == '卡兹克',
                          'role': ('tank' if c['id'] in tanks else 'carry') if c['cost'] >= 4 else '',
                          'icon': icon(c.get('images', {}).get('icon', {}))})
    emblems, seen = [], set()
    for item in read('items'):
        trait = str(item.get('extensions', {}).get('fetter_id') or '')
        if item['category'] != 'emblem' or trait not in by_id or trait in seen:
            continue
        seen.add(trait)
        emblems.append({'id': item['id'], 'trait': trait, 'name': item['name'], 'icon': icon(item.get('image', {}))})
    champions.sort(key=lambda c: (c['cost'], int(c['id'])))
    return {'version': season['game_version'], 'champions': champions, 'traits': traits,
            'emblems': emblems, 'luxChoices': lux_choices,
            'khazixChoices': [by_name[n] for n in ['狂战士', '迅捷射手', '法师', '裁决使'] if n in by_name],
            'composite': {'id': by_name.get('日月双蚀'), 'sources': [by_name.get('日蚀骑士'), by_name.get('月蚀骑士')]}}
