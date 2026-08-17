"""Server-side access to the season reference library under static/season-data/.

The library is produced by ``scripts/season_library/import_from_archive.py``.
``catalog.json`` lists seasons in archive order (oldest first); every season
directory carries a compact ``index.json`` for the reference page plus the full
``champions.json``/``traits.json`` snapshots used by champion detail pages.
"""

import json
from functools import lru_cache
from pathlib import Path

from season_rich_text import render_rich_text, strip_rich_text_markers

DATA_ROOT = Path(__file__).resolve().parent / 'static' / 'season-data'

SEASON_STATUS_LABELS = {
    'draft': '前瞻',
    'active': '进行中',
    'archived': '往期',
}

STAT_ROW_SPECS = (
    ('hp', '生命值'),
    ('ad', '攻击力'),
    ('armor', '护甲'),
    ('mr', '魔法抗性'),
    ('as', '攻速'),
    ('range', '射程'),
    ('mana', '法力值'),
    ('crit', '暴击率'),
    ('sell', '出售价'),
)


def format_skill_description(text, tokens=None):
    """Render imported rich-text tokens with a parser fallback for old data."""
    return render_rich_text(text, tokens)


def strip_scaling_tokens(text):
    """Plain-text version for SEO descriptions: drop stat scaling markers."""
    return strip_rich_text_markers(text)


def clean_variable_label(label):
    """Some archive variable labels carry the whole raw string after a colon."""
    if not label:
        return ''
    return label.replace('：', ':').split(':', 1)[0].strip()


def _format_stat(value, *, suffix='', decimals=None):
    if value is None:
        return None
    if decimals is not None and isinstance(value, float):
        value = round(value, decimals)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f'{value}{suffix}'


def _stat_cell(key, stats):
    if key == 'hp':
        return _format_stat(stats.get('health'))
    if key == 'ad':
        return _format_stat(stats.get('attack_damage'))
    if key == 'armor':
        return _format_stat(stats.get('armor'))
    if key == 'mr':
        return _format_stat(stats.get('magic_resist'))
    if key == 'as':
        return _format_stat(stats.get('attack_speed'), decimals=2)
    if key == 'range':
        return _format_stat(stats.get('attack_range'))
    if key == 'mana':
        max_mana = stats.get('max_mana')
        if max_mana is None:
            return None
        initial = stats.get('initial_mana')
        return f'{initial if initial is not None else 0}/{max_mana}'
    if key == 'crit':
        return _format_stat(stats.get('critical_strike_chance'), suffix='%')
    if key == 'sell':
        return _format_stat(stats.get('sell_price'))
    return None


def build_stat_rows(stats_by_star, star_levels):
    rows = []
    for key, label in STAT_ROW_SPECS:
        values = [_stat_cell(key, stats_by_star.get(star) or {}) for star in star_levels]
        if not any(value is not None for value in values):
            continue
        rows.append({
            'key': key,
            'label': label,
            'icon': '/static/season-gold.png' if key == 'sell' else f'/static/season-stats/{key}.png',
            'values': [value if value is not None else '—' for value in values],
        })
    return rows


def normalize_season_id(value):
    if not value:
        return ''
    return str(value).strip().lower().replace('-', '_').replace('.', '_')


def _load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def _catalog_doc():
    return _load_json(DATA_ROOT / 'catalog.json')


def catalog_seasons():
    """All seasons, newest first (reverse of archive/catalog order)."""
    seasons = list(_catalog_doc().get('seasons') or [])
    seasons.reverse()
    return [
        {**season, 'status_label': SEASON_STATUS_LABELS.get(season.get('status'), '')}
        for season in seasons
    ]


def get_season_entry(season_id):
    normalized = normalize_season_id(season_id)
    for season in catalog_seasons():
        if season['season_id'] == normalized:
            return season
    return None


@lru_cache(maxsize=16)
def _season_index(season_id):
    return _load_json(DATA_ROOT / season_id / 'index.json')


@lru_cache(maxsize=16)
def _season_full(season_id):
    champions = _load_json(DATA_ROOT / season_id / 'champions.json').get('champions') or []
    traits = _load_json(DATA_ROOT / season_id / 'traits.json').get('traits') or []
    return {
        'champions': champions,
        'champions_by_id': {champion['id']: champion for champion in champions},
        'traits_by_id': {trait['id']: trait for trait in traits},
    }


def season_page_context(season_id):
    """Everything the reference page template needs, or None if unknown."""
    entry = get_season_entry(season_id)
    if entry is None:
        return None
    index = _season_index(entry['season_id'])
    augments = index.get('augments') or []
    return {
        'season': entry,
        'mechanics': [
            {'id': mechanic['id'], 'kind': mechanic.get('kind'), 'display_name': mechanic.get('display_name')}
            for mechanic in index.get('mechanics') or []
        ],
        'champion_count': len(index.get('champions') or []),
        'augment_count': len(augments),
        'has_augments': bool(augments),
        'data_url': f"/static/season-data/{entry['season_id']}/index.json?v={entry.get('version_id', '')}",
        'asset_root': f"/static/season-data/{entry['season_id']}",
    }


def champion_ids(season_id):
    entry = get_season_entry(season_id)
    if entry is None:
        return []
    return [champion['id'] for champion in _season_full(entry['season_id'])['champions']]


def find_champion_id_by_name(season_id, name):
    entry = get_season_entry(season_id)
    if entry is None:
        return None
    for champion in _season_full(entry['season_id'])['champions']:
        if champion['name'] == name:
            return champion['id']
    return None


def _image_path(image):
    if isinstance(image, dict):
        return image.get('local_path')
    return None


def _member_payload(champion):
    return {
        'id': champion['id'],
        'name': champion['name'],
        'cost': champion.get('cost'),
        'icon': _image_path((champion.get('images') or {}).get('icon')),
    }


def build_champion_detail(season_id, champion_id):
    entry = get_season_entry(season_id)
    if entry is None:
        return None
    full = _season_full(entry['season_id'])
    champion = full['champions_by_id'].get(str(champion_id))
    if champion is None:
        return None

    traits = []
    for trait_id in champion.get('trait_ids') or []:
        trait = full['traits_by_id'].get(trait_id)
        if trait is None:
            continue
        members = [
            _member_payload(item)
            for item in full['champions']
            if trait_id in (item.get('trait_ids') or [])
        ]
        members.sort(key=lambda item: (item['cost'] or 0, item['id']))
        traits.append({
            'id': trait['id'],
            'name': trait['name'],
            'category': trait.get('category'),
            'description': trait.get('description'),
            'description_html': format_skill_description(
                trait.get('description'),
                trait.get('description_tokens'),
            ),
            'image': _image_path(trait.get('image')),
            'breakpoints': [
                {
                    **breakpoint,
                    'effect_html': format_skill_description(
                        breakpoint.get('effect'),
                        breakpoint.get('effect_tokens'),
                    ),
                }
                for breakpoint in trait.get('breakpoints') or []
            ],
            'members': members,
        })

    skill = (champion.get('skills') or [{}])[0]
    images = champion.get('images') or {}
    stats_by_star = champion.get('stats_by_star') or {}
    star_levels = sorted(stats_by_star.keys(), key=lambda star: int(star))
    variables = [
        {
            'label': clean_variable_label(variable.get('label')),
            'values': variable.get('values') or {},
        }
        for variable in skill.get('variables') or []
    ]
    return {
        'season': entry,
        'champion': {
            'id': champion['id'],
            'name': champion['name'],
            'cost': champion.get('cost'),
            'tags': champion.get('tags') or [],
            'availability': champion.get('availability') or {},
            'availability_description_html': format_skill_description(
                (champion.get('availability') or {}).get('description'),
            ),
            'icon': _image_path(images.get('icon')),
            'splash': _image_path(images.get('splash')),
            'skill': {
                'name': skill.get('name'),
                'description': skill.get('description'),
                'description_html': format_skill_description(
                    skill.get('description'),
                    skill.get('description_tokens'),
                ),
                'image': _image_path(skill.get('image')),
                'variables': variables,
            },
            'stats_by_star': stats_by_star,
            'star_levels': star_levels,
            'stat_rows': build_stat_rows(stats_by_star, star_levels),
        },
        'traits': traits,
    }


def clear_caches():
    _catalog_doc.cache_clear()
    _season_index.cache_clear()
    _season_full.cache_clear()
