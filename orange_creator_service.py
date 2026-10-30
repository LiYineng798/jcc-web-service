"""Versioned, read-only creator configuration; replace this adapter for future releases."""
from orange_fortune_service import DECK_SIZE, PORTALS, TIERS, catalog
from season_visibility import default_season_id, get_season
from settings_service import get_setting
from db import get_db
from assets_version import static_v


def creator_season():
    """The formation editor uses the creator surface's default season, set in the admin."""
    season_id = default_season_id('creator')
    return get_season('creator', season_id) if season_id else None


def creator_config():
    season = creator_season()
    available = get_setting(get_db(), 'simulator_enabled', 'true') == 'true' and season is not None
    return {
        'schema_version': 2,
        'season_id': season['season_id'] if season else None,
        'season_name': season.get('display_name') if season else None,
        'simulator_available': available,
        'card_slots': DECK_SIZE,
        'export': {'width': 1200, 'height': 1600},
        # An over-limit deck is flagged in the editor and on the poster, never blocked.
        'portals': [dict(portal) for portal in PORTALS],
        'tiers': {str(tier): name for tier, name in TIERS.items()},
        'layouts': [
            {'id': 'guide', 'name': '攻略版', 'description': '卡组、站位与运营', 'formation': True},
            {'id': 'showcase', 'name': '纯构筑版', 'description': '卡组与站位', 'formation': True},
            {'id': 'cards', 'name': '卡组推荐版', 'description': '仅三张卡片', 'formation': False},
        ],
        'targets': ['不标注', '前七', '前五', '前三', '登顶'],
        'backgrounds': [
            {'id': key, 'name': name, 'description': description,
             'image_url': static_v(f'tools/orange-fortune/creator/material-{key}.svg')}
            for key, name, description in [
                ('gilded', '曜石鎏金', '金属星盘 · 深蓝细纹'),
                ('jade', '翡翠棱镜', '玉石切面 · 青铜刻线'),
                ('astral', '星轨紫晶', '轨道光环 · 紫晶微光'),
                ('ivory', '象牙烫金', '暖白纸纹 · 放射金箔'),
                ('editorial', '人文手札', '奶油纸色 · 复古蓝墨'),
                ('folio', '蓝绒藏典', '织物书封 · 古铜雕饰'),
            ]
        ],
        'cards': [{**{key: card[key] for key in ('id', 'tier', 'tier_name', 'energy', 'name', 'description',
                                                 'category', 'rounds', 'image', 'layout')},
                   'image_url': static_v(card['image']) if card['image'] else None} for card in catalog()['cards']],
    }
