"""Derive omitted roster entries and trait board objects from official snapshots."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


COUNT_WORDS = {
    '一': 1,
    '二': 2,
    '两': 2,
    '三': 3,
    '四': 4,
    '五': 5,
    '六': 6,
    '七': 7,
    '八': 8,
    '九': 9,
    '十': 10,
}


def data_records(document):
    data = (document or {}).get('data') or {}
    if isinstance(data, dict):
        return [record for record in data.values() if isinstance(record, dict)]
    if isinstance(data, list):
        return [record for record in data if isinstance(record, dict)]
    return []


def _base_id(record):
    raw_id = str(record.get('id') or '')
    return raw_id[1:] if len(raw_id) > 1 and raw_id[0].isdigit() else raw_id


def _star(record):
    raw_id = str(record.get('id') or '')
    return int(raw_id[0]) if raw_id and raw_id[0].isdigit() else 1


def _split_trait_ids(value):
    return [part for part in str(value or '').split('|') if part and part not in {'-1', '0'}]


def _normalize_reference(value):
    text = unicodedata.normalize('NFKC', str(value or '')).lower()
    text = re.sub(r'[\s【】\[\]（）()·,.，。:：;；!！?？、&+\-/|]', '', text)
    text = text.replace('之', '').replace('塔楼', '塔')
    return text


def _name_aliases(name):
    normalized = _normalize_reference(name)
    aliases = {normalized}
    for prefix in ('迷你', '小型', '巨型'):
        if normalized.startswith(prefix) and len(normalized) > len(prefix) + 1:
            aliases.add(normalized[len(prefix):])
    return {alias for alias in aliases if len(alias) >= 2}


def _trait_text(trait):
    parts = [trait.get('description') or '']
    parts.extend(point.get('effect') or '' for point in trait.get('breakpoints') or [])
    return ' '.join(parts)


def _unique_trait_text(trait):
    parts = [trait.get('description') or '']
    parts.extend(point.get('effect') or '' for point in trait.get('breakpoints') or [])
    unique = {}
    for part in parts:
        cleaned = re.sub(r'\s+', ' ', part).strip()
        if cleaned:
            unique.setdefault(_normalize_reference(cleaned), cleaned)
    return ' '.join(unique.values())


def _matching_traits(name, traits):
    aliases = _name_aliases(name)
    return [
        trait
        for trait in traits
        if any(alias in _normalize_reference(_trait_text(trait)) for alias in aliases)
    ]


def _reference_position(text, aliases):
    normalized = _normalize_reference(text)
    positions = [normalized.find(alias) for alias in aliases if alias in normalized]
    return min(positions) if positions else -1


def _explicit_count(text, aliases):
    without_tier = re.sub(r'^\s*[（(]\s*\d+\s*[）)]\s*', '', str(text or ''))
    normalized = _normalize_reference(without_tier)
    position = _reference_position(text, aliases)
    if without_tier != str(text or ''):
        position = _reference_position(without_tier, aliases)
    if position < 0:
        return None
    prefix = normalized[max(0, position - 10):position]
    match = re.search(
        r'([0-9]+|[一二两三四五六七八九十])'
        r'(?:个|座|只|名|枚|颗|块)?(?:可放置的)?(?:迷你|小型)?$',
        prefix,
    )
    if not match:
        return None
    value = match.group(1)
    return int(value) if value.isdigit() else COUNT_WORDS.get(value)


def _activation_rules(name, traits):
    aliases = _name_aliases(name)
    rules = []
    for trait in traits:
        description = trait.get('description') or ''
        current_count = 1 if _reference_position(description, aliases) >= 0 else 0
        explicit = _explicit_count(description, aliases)
        if explicit is not None:
            current_count = explicit
        for point in sorted(trait.get('breakpoints') or [], key=lambda item: int(item.get('min_units') or 0)):
            effect = point.get('effect') or ''
            referenced = _reference_position(effect, aliases) >= 0
            explicit = _explicit_count(effect, aliases)
            if explicit is not None:
                current_count = explicit
            elif referenced and current_count == 0:
                current_count = 1
            if current_count:
                rules.append({
                    'trait_id': str(trait['id']),
                    'min_units': int(point.get('min_units') or 1),
                    'max_units': point.get('max_units'),
                    'max_count': current_count,
                })
        if current_count and not trait.get('breakpoints'):
            rules.append({'trait_id': str(trait['id']), 'min_units': 1, 'max_units': None, 'max_count': current_count})
    return rules


def _can_equip(name, traits):
    aliases = _name_aliases(name)
    for trait in traits:
        text = _trait_text(trait)
        if _reference_position(text, aliases) >= 0 and '携带装备' in text:
            return True
    return False


def _suffix(url, default):
    suffix = Path(urlparse(str(url or '')).path).suffix.lower()
    return suffix if suffix in {'.png', '.jpg', '.jpeg', '.webp'} else default


def _download(url, target):
    if not url or target.is_file():
        return target.is_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(str(url), headers={'User-Agent': 'JCC season library importer/1.0'})
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - official CDN URL from archived snapshot
            target.write_bytes(response.read())
    except Exception as exc:  # noqa: BLE001 - caller reports a recoverable missing asset
        print(f'  警告: 官方特殊单位图片下载失败 {url}: {exc}')
        return False
    return True


def _image(local_path, source_url, alt):
    return {'local_path': local_path, 'source_url': source_url, 'alt': alt}


def _stats(record):
    return {
        'health': float(record.get('initHP') or 0),
        'attack_damage': float(record.get('initAttackDamage') or 0),
        'armor': float(record.get('armor') or 0),
        'magic_resist': float(record.get('magicResist') or 0),
        'attack_speed': float(record.get('attackSpeed') or 0),
        'attack_range': float(record.get('attackRange') or 0),
        'initial_mana': float(record.get('initMP') or 0),
        'max_mana': float(record.get('maxMP') or 0),
        'critical_strike_chance': float(record.get('criticalStrikeChance') or 0),
        'sell_price': float(record.get('sellPrice') or 0),
    }


def _group_records(records, mode):
    groups = {}
    for record in records:
        if str(record.get('setid')) != str(mode):
            continue
        groups.setdefault(_base_id(record), []).append(record)
    for group in groups.values():
        group.sort(key=_star)
    return groups


def _ensure_champion_assets(base_id, base, mode, target_dir):
    icon_url = base.get('picture')
    skill_url = base.get('skillIcon')
    splash_url = (
        f"https://game.gtimg.cn/images/jk/jkimg/mode{mode}s18/1624x750/{base.get('heroPaint')}.jpg"
        if base.get('heroPaint')
        else None
    )
    icon_path = f'assets/champions/{base_id}{_suffix(icon_url, ".png")}'
    skill_path = f'assets/skills/{base_id}{_suffix(skill_url, ".png")}'
    splash_path = f'assets/champions/splash/{base_id}.jpg'
    _download(icon_url, target_dir / icon_path)
    _download(skill_url, target_dir / skill_path)
    _download(splash_url, target_dir / splash_path)
    return {
        'icon': _image(icon_path, icon_url, f"{base.get('name') or base_id}头像") if (target_dir / icon_path).is_file() else None,
        'skill': _image(skill_path, skill_url, f"{base.get('name') or base_id}技能图标") if (target_dir / skill_path).is_file() else None,
        'splash': _image(splash_path, splash_url, f"{base.get('name') or base_id}大图") if (target_dir / splash_path).is_file() else None,
    }


def _supplement_champions(groups, champions_doc, traits_doc, mode, target_dir):
    champions = champions_doc.get('champions') or []
    traits = traits_doc.get('traits') or []
    known_names = {champion.get('name') for champion in champions}
    known_trait_ids = {str(trait['id']) for trait in traits}
    added = []
    for champion_id, stars in groups.items():
        base = stars[0]
        official_trait_ids = _split_trait_ids(base.get('species')) + _split_trait_ids(base.get('class'))
        matching_traits = _matching_traits(base.get('name') or '', traits)
        if (
            int(base.get('price') or 0) <= 0
            or str(base.get('heroType')) == '0'
            or str(base.get('showHeroTag')) != '1'
            or base.get('name') in known_names
            or not matching_traits
            or not any(trait_id in known_trait_ids for trait_id in official_trait_ids)
        ):
            continue
        assets = _ensure_champion_assets(champion_id, base, mode, target_dir)
        if not assets['icon']:
            continue
        descriptions = {}
        for trait in matching_traits:
            description = _unique_trait_text(trait)
            if description:
                descriptions.setdefault(_normalize_reference(description), description)
        availability_description = '；'.join(descriptions.values())
        champions.append({
            'id': champion_id,
            'name': base.get('name') or champion_id,
            'aliases': [],
            'cost': int(base.get('price') or 0),
            'trait_ids': [trait_id for trait_id in official_trait_ids if trait_id in known_trait_ids],
            'role': None,
            'availability': {'type': 'unlock', 'description': availability_description or None, 'rules': []},
            'stats_by_star': {str(_star(record)): _stats(record) for record in stars},
            'skills': [{
                'id': f'{champion_id}_skill',
                'name': base.get('skillName') or '',
                'description': base.get('skillDesc') or '',
                'variables': [],
                'raw_values': stars[-1].get('skillValueDesc') or base.get('skillValueDesc') or None,
                'image': assets['skill'],
            }],
            'images': {'icon': assets['icon'], 'splash': assets['splash'] or assets['icon']},
            'source_ids': {
                'official_id': champion_id,
                'record_ids': [str(record.get('id')) for record in stars],
                'hero_paint': base.get('heroPaint'),
                'tft_hero_id': str(base.get('tftHeroId') or '') or None,
            },
            'tags': ['official-supplement'],
            'extensions': {
                'official_hero_type': str(base.get('heroType')),
                'library_visible': True,
                'simulator_visible': True,
                'supplemented_from_official_snapshot': True,
            },
        })
        known_names.add(base.get('name'))
        added.append(base.get('name') or champion_id)
    return added


def _board_unit_groups(groups, champions_doc, traits_doc):
    champion_names = {champion.get('name') for champion in champions_doc.get('champions') or []}
    traits = traits_doc.get('traits') or []
    matched = []
    for base_id, stars in groups.items():
        base = stars[0]
        if base.get('name') in champion_names:
            continue
        if int(base.get('price') or 0) > 0 and str(base.get('heroType')) != '1':
            continue
        matching_traits = _matching_traits(base.get('name') or '', traits)
        if matching_traits and base.get('picture'):
            matched.append((base_id, stars, matching_traits))

    merged = {}
    for base_id, stars, matching_traits in matched:
        base = stars[0]
        key = (base.get('name'), base.get('heroPaint') or base.get('picture'))
        entry = merged.setdefault(key, {'base_ids': [], 'stars': [], 'traits': {}})
        entry['base_ids'].append(base_id)
        entry['stars'].extend(stars)
        entry['traits'].update({str(trait['id']): trait for trait in matching_traits})
    return list(merged.values())


def _build_board_units(groups, champions_doc, traits_doc, target_dir):
    units = []
    for entry in _board_unit_groups(groups, champions_doc, traits_doc):
        entry['stars'].sort(key=_star)
        base = entry['stars'][0]
        primary_id = sorted(entry['base_ids'], key=lambda value: (len(value), value))[0]
        icon_url = base.get('picture')
        icon_path = f'assets/board-units/{primary_id}{_suffix(icon_url, ".png")}'
        if not _download(icon_url, target_dir / icon_path):
            continue
        traits = list(entry['traits'].values())
        units.append({
            'id': f'board_{primary_id}',
            'name': base.get('name') or primary_id,
            'kind': 'trait_object',
            'aliases': [],
            'trait_ids': [str(trait['id']) for trait in traits],
            'placement_rules': _activation_rules(base.get('name') or '', traits),
            'can_equip': _can_equip(base.get('name') or '', traits),
            'stats': _stats(base),
            'skill': {
                'name': base.get('skillName') or '',
                'description': base.get('skillDesc') or '',
                'image': None,
            },
            'image': _image(icon_path, icon_url, f"{base.get('name') or primary_id}图标"),
            'source_ids': {
                'official_ids': sorted(set(entry['base_ids'])),
                'record_ids': sorted({str(record.get('id')) for record in entry['stars']}),
                'hero_paint': base.get('heroPaint'),
            },
            'extensions': {'library_visible': False, 'simulator_visible': True},
        })
    return units


def apply_official_supplements(version_dir, target_dir, season, champions_doc, traits_doc, load_json):
    """Enrich official seasons without another API data request.

    The archived ``chess.json`` remains the source. Only referenced board-unit
    images may be fetched from the official Tencent CDN when the archive did not
    already contain them.
    """
    snapshot_path = version_dir / 'source-snapshots' / 'chess.json'
    mode = (season.get('official_ids') or {}).get('mode')
    if not mode or not snapshot_path.is_file():
        return {'champions': [], 'board_units': []}
    records = data_records(load_json(snapshot_path))
    groups = _group_records(records, mode)
    added_champions = _supplement_champions(groups, champions_doc, traits_doc, mode, target_dir)
    board_units = _build_board_units(groups, champions_doc, traits_doc, target_dir)
    return {'champions': added_champions, 'board_units': board_units}
