"""Read-only catalog for the independent S400001 time-card mode."""
import json
import re
from functools import lru_cache
from pathlib import Path

CATEGORIES = {'1001': '经济', '1002': '弈子', '1003': '装备', '1004': '强化', '1005': '羁绊', '1006': '特殊'}
# Mode rules confirmed for launch. A card's energy equals its rarity tier, so
# three Legendary cards (15) fill the Unknown portal exactly.
TIERS = {1: '基础', 2: '勇士', 3: '王者', 4: '史诗', 5: '传说'}
DECK_SIZE = 3
PORTALS = (
    {'id': 'stable', 'name': '稳定传送门', 'energy_limit': 8, 'entry_fee': 0, 'loss_cards': 0, 'loss': '不损失卡片'},
    {'id': 'volatile', 'name': '波动传送门', 'energy_limit': 10, 'entry_fee': 400, 'loss_cards': 2, 'loss': '随机损失两张卡片'},
    {'id': 'unknown', 'name': '未知传送门', 'energy_limit': 15, 'entry_fee': 2000, 'loss_cards': 3, 'loss': '随机损失三张卡片'},
)
CATALOG = Path(__file__).resolve().parent / 'static/tools/orange-fortune/cards.json'
ROUND = re.compile(r'\d+-\d+')


def parse_arguments(value):
    """Keep case and values intact: similarly named parameters are not interchangeable."""
    return dict(part.split('=', 1) for part in value.split('^') if '=' in part)


@lru_cache(maxsize=1)
def catalog():
    payload = json.loads(CATALOG.read_text(encoding='utf-8'))
    cards = []
    for source in payload['data'].values():
        args = parse_arguments(source['sArgs'])
        tags = source['sTags'].split('|')
        round_keys = sorted((key for key in args if re.fullmatch(r'round\d*', key)),
                            key=lambda key: int(key[5:] or 0))
        rounds = [args[key] for key in round_keys if ROUND.fullmatch(args[key])]
        asset = payload['assets'].get(source['id'])
        cards.append({
            'id': source['id'], 'tier': int(source['iRarityTier']), 'name': source['sName'],
            'tier_name': TIERS[int(source['iRarityTier'])], 'energy': int(source['iRarityTier']),
            'description': source['sDesc'], 'category': CATEGORIES.get(tags[-1], '其他'),
            'category_id': tags[-1], 'round': args.get('round', ''), 'rounds': rounds,
            'image': f"tools/orange-fortune/{asset['file']}" if asset else None,
            'layout': asset['layout'] if asset else 'missing', 'source': source,
        })
    # Lead the five-star gallery with recognizable mode-specific art, not a ranking.
    showcase = ('7250036', '7250046', '7250034', '7250042', '7250061')
    order = {card_id: index for index, card_id in enumerate(showcase)}
    cards.sort(key=lambda c: (-c['tier'], order.get(c['id'], len(showcase)), int(c['id'])))
    return {**{key: payload[key] for key in ('version', 'season', 'setId', 'time')}, 'cards': cards}


def card_guide(query='', tier='', category='', round_value=''):
    data = catalog()
    query = str(query).strip()[:100]
    tier = tier if tier in ('1', '2', '3', '4', '5') else ''
    category = category if category in CATEGORIES else ''
    rounds = sorted({r for card in data['cards'] for r in card['rounds']}, key=lambda r: tuple(map(int, r.split('-'))))
    round_value = round_value if round_value in rounds else ''
    terms = query.casefold().split()
    visible_ids = {card['id'] for card in data['cards'] if
                   (not tier or card['tier'] == int(tier)) and
                   (not category or card['category_id'] == category) and
                   (not round_value or round_value in card['rounds']) and
                   all(term in f"{card['name']} {card['description']} {card['id']}".casefold() for term in terms)}
    return {
        'catalog': data, 'tiers': TIERS, 'portals': PORTALS, 'deck_size': DECK_SIZE,
        'groups': [{'tier': t, 'tier_name': TIERS[t], 'cards': [c for c in data['cards'] if c['tier'] == t],
                                   'visible': sum(c['id'] in visible_ids and c['tier'] == t for c in data['cards'])}
                                  for t in range(5, 0, -1)],
        'visible_ids': visible_ids, 'query': query, 'tier': tier, 'category': category,
        'round_value': round_value, 'round_options': rounds, 'categories': CATEGORIES,
    }
