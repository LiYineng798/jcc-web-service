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
        'export': {'width': 1600, 'height': 1200},
        'portals': [
            {'id': 'unspecified', 'name': '不标注传送门', 'energy_limit': None},
            {'id': 'stable', 'name': '稳定传送门', 'energy_limit': 8},
            {'id': 'custom', 'name': '其他传送门', 'energy_limit': None},
        ],
        'targets': ['不标注', '前七', '前五', '前三', '登顶'],
        'backgrounds': [
            {'id': 'gilded', 'name': '曜石鎏金', 'description': '深色矿石 · 香槟金'},
            {'id': 'jade', 'name': '翡翠秘境', 'description': '松绿玉石 · 古铜金'},
            {'id': 'astral', 'name': '星夜紫晶', 'description': '午夜靛蓝 · 冰紫银'},
            {'id': 'ivory', 'name': '象牙手札', 'description': '暖调纸张 · 褐金墨'},
        ],
        # Rarity is not an energy field. Null deliberately means unknown.
        'cards': [{**{key: card[key] for key in ('id', 'tier', 'name', 'description', 'category', 'rounds', 'image', 'layout')},
                   'image_url': static_v(card['image']) if card['image'] else None,
                   'energy': None} for card in catalog()['cards']],
    }
