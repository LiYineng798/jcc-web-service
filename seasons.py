from copy import deepcopy

DEFAULT_SEASON_ID = 's17-star-god'

SEASON_ALIASES = {
    'default': DEFAULT_SEASON_ID,
    's16-archive': 's16-legends',
}

SEASON_CATALOG = (
    {
        'id': 's17-star-god',
        'name': 'S17 · 星神',
        'status': 'active',
        'order': 1,
        'description': '当前赛季',
        'data_file': 's17-star-god.json',
    },
    {
        'id': 's16-legends',
        'name': 'S16 · 英雄联盟传奇',
        'status': 'active',
        'order': 2,
        'description': '经典赛季',
        'data_file': 's16-legends.json',
    },
    {
        'id': 'lucky-lantern',
        'name': '天选福星',
        'status': 'active',
        'order': 3,
        'description': '返场赛季',
        'data_file': 'lucky-lantern.json',
    },
    {
        'id': 's8-monsters-attack',
        'name': 'S8·怪兽入侵',
        'status': 'active',
        'order': 4,
        'description': '返场赛季',
        'data_file': 's8-monsters-attack.json',
    },
)


def canonical_season_id(season_id):
    raw = str(season_id or '').strip()
    return SEASON_ALIASES.get(raw, raw)


def season_catalog():
    return [deepcopy(season) for season in SEASON_CATALOG]


def season_manifest(default_season_id=DEFAULT_SEASON_ID):
    selected_default = canonical_season_id(default_season_id) or DEFAULT_SEASON_ID
    seasons = season_catalog()
    if not any(season['id'] == selected_default for season in seasons):
        selected_default = DEFAULT_SEASON_ID
    return {
        'default_season_id': selected_default,
        'seasons': seasons,
    }
