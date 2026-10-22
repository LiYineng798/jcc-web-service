"""Versioned, read-only creator configuration; replace this adapter for future releases."""
from orange_fortune_service import catalog
from season_visibility import public_seasons
from settings_service import get_setting
from db import get_db
from assets_version import static_v

CREATOR_SEASON = 's16_5'


def creator_config():
    available = (get_setting(get_db(), 'simulator_enabled', 'true') == 'true'
                 and any(s['season_id'] == CREATOR_SEASON for s in public_seasons('simulator')))
    return {
        'schema_version': 1,
        'season_id': CREATOR_SEASON,
        'simulator_available': available,
        'card_slots': 3,
        'export': {'width': 1200, 'height': 1600},
        'portals': [
            {'id': 'unspecified', 'name': '不标注传送门', 'energy_limit': None},
            {'id': 'stable', 'name': '稳定传送门', 'energy_limit': 8},
            {'id': 'custom', 'name': '其他传送门', 'energy_limit': None},
        ],
        'targets': ['不标注', '前七', '前五', '前三', '登顶'],
        'backgrounds': [
            {'id': key, 'name': name, 'description': description,
             'image_url': static_v(f'tools/orange-fortune/creator/portal-{key}.png')}
            for key, name, description in [
                ('gilded', '时空宝库', '鎏金星门 · 深海蓝晶'),
                ('jade', '翡翠遗迹', '青铜古树 · 秘境微光'),
                ('astral', '棱彩星门', '紫晶星河 · 浮空秘藏'),
                ('ivory', '象牙圣域', '暖金云海 · 冰晶石阶'),
            ]
        ],
        # Rarity is not an energy field. Null deliberately means unknown.
        'cards': [{**{key: card[key] for key in ('id', 'tier', 'name', 'description', 'category', 'rounds', 'image', 'layout')},
                   'image_url': static_v(card['image']) if card['image'] else None,
                   'energy': None} for card in catalog()['cards']],
    }
