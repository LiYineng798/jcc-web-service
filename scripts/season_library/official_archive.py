"""Convert an official branch archive into the season-archive layout read by import_from_archive.py.

Input is a directory written by ``scripts/collect_orange_fortune.py`` (``selection.json`` plus
``parsed/<mode>/<version>-<season>/*.json``). Output is a ``数据模板``-shaped root::

    <output>/data/catalog.json
    <output>/data/seasons/<season_id>/season.json
    <output>/data/seasons/<season_id>/<version>/{version.json,champions.json,traits.json,items.json}
    <output>/data/seasons/<season_id>/<version>/source-snapshots/{chess,hex,version-entry}.json
    <output>/data/seasons/<season_id>/<version>/assets/...

Downloaded files are parsed as JSON or images only; nothing is executed. Records keep the
official ids; nothing is merged by name.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / 'scripts'))
from collect_orange_fortune import fetch, inspect_image, now  # noqa: E402
from season_library.official_augments import augment_image_paths  # noqa: E402

STYLES = {'1': 'bronze', '2': 'silver', '3': 'gold', '4': 'prismatic', '5': 'unique'}
ITEM_CATEGORIES = {'基础装备': 'component', '成型装备': 'completed', '光明武器': 'radiant', '神器装备': 'artifact',
                   '转职纹章': 'emblem', '特殊装备': 'other'}
STAT_LABELS = {'伤害减免': 'damage_reduction', '伤害增幅': 'damage_amplification', '全能吸血': 'omnivamp', '护甲': 'armor',
               '攻击速度': 'attack_speed', '暴击率': 'critical_strike_chance', '法力回复': 'mana_regeneration',
               '法术加成': 'ability_power', '物理加成': 'physical_power', '生命上限': 'health', '魔法抗性': 'magic_resist'}
STAT = re.compile(r'^\+(\d+(?:\.\d+)?)(%?)(\S+)$')
GRANTED_TRAIT = re.compile(r'获得【([^】]+)】特质/职业')
SKILL_VALUES = re.compile(r'^[\d.]+%?(?:/[\d.]+%?)+$')


def records(document):
    data = (document or {}).get('data') or {}
    return [r for r in (data.values() if isinstance(data, dict) else data) if isinstance(r, dict)]


def star(record):
    return int(str(record['id'])[0])


def split_ids(value):
    return [part for part in str(value or '').split('|') if part and part not in {'-1', '0'}]


def image(local_path, url, alt):
    return {'local_path': local_path, 'source_url': url, 'alt': alt}


def suffix(url, default='.png'):
    value = Path(urlparse(str(url or '')).path).suffix.lower()
    return value if value in {'.png', '.jpg', '.jpeg', '.webp'} else default


def stats(record):
    return {
        'health': float(record.get('initHP') or 0), 'attack_damage': float(record.get('initAttackDamage') or 0),
        'armor': float(record.get('armor') or 0), 'magic_resist': float(record.get('magicResist') or 0),
        'attack_speed': float(record.get('attackSpeed') or 0), 'attack_range': float(record.get('attackRange') or 0),
        'initial_mana': float(record.get('initMP') or 0), 'max_mana': float(record.get('maxMP') or 0),
        'critical_strike_chance': float(record.get('criticalStrikeChance') or 0),
        'sell_price': float(record.get('sellPrice') or 0),
    }


def skill_variables(raw):
    """Read the per-star list after the last space; the label is the text before a full-width colon.

    Segments without a per-star list are skipped but keep their position in the key numbering.
    """
    variables = []
    for index, part in enumerate(str(raw or '').split('|'), 1):
        part = part.strip()
        values = part.rsplit(' ', 1)[-1] if ' ' in part else ''
        if not SKILL_VALUES.match(values):
            continue
        label = part.split('：', 1)[0].strip() if '：' in part else part
        variables.append({'key': f'value_{index}', 'label': label, 'unit': 'raw',
                          'values': {str(i): v for i, v in enumerate(values.split('/'), 1)}})
    return variables


def build_champions(chess, missions, mode, splash_token, previous_ids, known_trait_ids):
    groups = {}
    for record in records(chess):
        if str(record.get('setid')) == str(mode) and str(record.get('id', ''))[:1].isdigit():
            groups.setdefault(str(record['id'])[1:], []).append(record)
    unlocks = {}
    for mission in records(missions):
        for task in mission.get('mission') or []:
            unlocks.setdefault(str(mission.get('heroid'))[1:], task)
    champions, downloads = [], []
    for base_id, stars in sorted(groups.items(), key=lambda pair: int(pair[0])):
        stars.sort(key=star)
        base, top = stars[0], stars[-1]
        if not 1 <= int(base.get('price') or 0) <= 5 or str(base.get('showHeroTag')) != '1' or str(base.get('heroType')) != '0':
            continue
        raw_trait_ids = [i for i in f"{base.get('species') or ''}|{base.get('class') or ''}".split('|') if i and i != '-1']
        trait_ids = [i for i in raw_trait_ids if i in known_trait_ids]
        task = unlocks.get(base_id)
        availability = {'type': 'shop', 'description': None, 'rules': []}
        if task:
            availability = {'type': 'unlock', 'description': task.get('desc'), 'rules': [{
                'type': 'official_mission', 'params': {
                    'mission_id': str(task.get('id')), 'task_tips': task.get('tasktips') or None, 'description': task.get('desc'),
                    'sort': task.get('sort'), 'difficulty': task.get('difficulty'), 'condition_id': task.get('conditionId')}}]}
        name = base.get('name') or base_id
        icon = f"assets/champions/{base_id}{suffix(base.get('picture'))}"
        skill_icon = f"assets/skills/{base_id}{suffix(base.get('skillIcon'))}"
        splash_url = f"https://game.gtimg.cn/images/jk/jkimg/{splash_token}/1624x750/{base.get('heroPaint')}.jpg"
        splash = f'assets/champions/splash/{base_id}.jpg'
        downloads += [(base.get('picture'), icon), (base.get('skillIcon'), skill_icon), (splash_url, splash)]
        champions.append({
            'id': base_id, 'name': name, 'aliases': [], 'cost': int(base['price']),
            'trait_ids': trait_ids, 'role': None, 'availability': availability,
            'stats_by_star': {str(star(r)): stats(r) for r in stars},
            'skills': [{
                'id': f'{base_id}_skill', 'name': base.get('skillName') or '', 'description': base.get('skillDesc') or '',
                'variables': skill_variables(top.get('skillValueDesc')), 'raw_values': top.get('skillValueDesc') or None,
                'image': image(skill_icon, base.get('skillIcon'), f'{name}技能图标'),
                'extensions': {'description_by_star': {str(star(r)): r.get('skillDesc') or '' for r in stars}},
            }],
            'images': {'icon': image(icon, base.get('picture'), f'{name}头像'),
                       'splash': image(splash, splash_url, f'{name}大图')},
            'source_ids': {'official_id': base_id, 'hero_paint': base.get('heroPaint'),
                           'record_ids': [str(r['id']) for r in stars], 'tft_hero_id': str(base.get('tftHeroId') or '') or None},
            'tags': ['new'] if previous_ids is not None and base_id not in previous_ids else [],
            'extensions': {'official_unresolved_trait_ids': [i for i in raw_trait_ids if i not in known_trait_ids]},
        })
    return champions, downloads


def build_traits(race, job):
    traits, downloads = [], []
    for category, document, id_key in (('origin', race, 'tftSpecId'), ('class', job, 'tftClassId')):
        for record in sorted(records(document), key=lambda r: int(r['id'])):
            counts = [int(n) for n in str(record.get('numList') or '').split('|') if n]
            colors = str(record.get('color') or '').split('|')
            effects = str(record.get('desc2') or '').split('|')
            breakpoints = []
            for i, count in enumerate(counts):
                color = colors[i] if i < len(colors) else ''
                breakpoints.append({
                    'min_units': count, 'max_units': counts[i + 1] - 1 if i + 1 < len(counts) else None,
                    # A single desc2 text describes every breakpoint (e.g. one-unit traits).
                    'style': STYLES.get(color, 'bronze'),
                    'effect': (effects[0] if len(effects) == 1 else effects[i] if i < len(effects) else '').strip(),
                    'values': {'source_style': color}})
            local = f"assets/traits/{record['id']}{suffix(record.get('picture'))}"
            downloads.append((record.get('picture'), local))
            traits.append({
                'id': str(record['id']), 'name': record.get('name'), 'category': category,
                'description': (record.get('prefix') or '').strip(), 'breakpoints': breakpoints,
                'image': image(local, record.get('picture'), f"{record.get('name')}羁绊图标"),
                'source_ids': {'official_id': str(record['id']), 'tft_spec_id': record.get(id_key), 'map_id': record.get('mapID')},
                'tags': [], 'extensions': {'raw_color': record.get('color'), 'raw_description': record.get('desc2')},
            })
    return traits, downloads


def item_stats(raw):
    values = []
    for part in raw.split():
        match = STAT.match(part)
        if not match or match[3] not in STAT_LABELS:
            return {'raw': raw, 'values': []}
        values.append({'stat': STAT_LABELS[match[3]], 'source_label': match[3],
                       'value': float(match[1]) if '.' in match[1] else int(match[1]),
                       'unit': 'percent' if match[2] else 'flat'})
    return {'raw': raw, 'values': values}


def build_items(equip, trait_names=None):
    items, downloads = [], []
    for record in sorted(records(equip), key=lambda r: int(r['id'])):
        category = ITEM_CATEGORIES.get(record.get('type'), 'other')
        components = [c for c in (record.get('synthesis1'), record.get('synthesis2')) if c and c != '0']
        basic, effect = (record.get('basicDesc') or '').strip(), (record.get('desc') or '').strip()
        local = f"assets/items/{record['id']}{suffix(record.get('picture'))}"
        downloads.append((record.get('picture'), local))
        fetter_id, fetter_source = record.get('fetterID') or None, 'official'
        if category == 'emblem' and not fetter_id:
            # Some branches ship emblems without fetterID; the granted trait is named in the text.
            match = GRANTED_TRAIT.search(effect)
            fetter_id = (trait_names or {}).get(match[1]) if match else None
            fetter_source = 'description' if fetter_id else None
        items.append({
            'id': str(record['id']), 'name': record.get('name'), 'category': category,
            'description': ' '.join(part for part in (basic, effect) if part),
            'stats': item_stats(basic),
            'effects': [{'id': f"{record['id']}_effect", 'description': effect, 'values': {}}] if effect else [],
            'recipe': {'type': 'components', 'component_ids': components, 'description': None} if len(components) == 2
            else {'type': 'none', 'component_ids': [], 'description': None},
            'unique': '唯一' in effect,
            'image': image(local, record.get('picture'), f"{record.get('name')}装备图标"),
            'source_ids': {'official_id': str(record['id']), 'tft_equip_id': record.get('tftEquipId'), 'map_id': record.get('mapID')},
            'tags': [],
            'extensions': {'source_type': record.get('type'), 'source_picture_url': record.get('picture'),
                           'effect_type': record.get('EffectType'), 'fetter_id': fetter_id,
                           'plan_id': record.get('planID'), 'sort': record.get('sort'),
                           **({'fetter_id_source': fetter_source} if fetter_source == 'description' else {})},
        })
    return items, downloads


def download_assets(version_dir, downloads, timeout, attempts, workers):
    """Fetch every referenced image once; failures are reported, never replaced by another file."""
    unique = {local: url for url, local in downloads if url}
    results = {}

    def one(pair):
        local, url = pair
        target = version_dir / local
        if target.is_file():
            return local, {'url': url, 'status': 'cached'}
        result = fetch(url, timeout, attempts)
        if result['body'] is None:
            return local, {'url': url, 'error': result['error'], 'status': result.get('status')}
        meta, error = inspect_image(result['body'])
        if error:
            return local, {'url': url, 'error': error, 'status': result.get('status')}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result['body'])
        return local, {'url': url, 'status': result.get('status'), **meta}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for local, record in pool.map(one, sorted(unique.items())):
            results[local] = record
    return results


def drop_missing_images(document, key, version_dir):
    """Keep image objects only when the file exists, so the importer never links to absent art."""
    for entry in document[key]:
        for holder in [entry, *(entry.get('skills') or []), entry.get('images') or {}]:
            for field in ('image', 'icon', 'splash'):
                value = holder.get(field)
                if isinstance(value, dict) and not (version_dir / value['local_path']).is_file():
                    holder[field] = None


def build(official, output, season_id, display_name, set_number, set_variant, theme, previous, timeout, attempts, workers,
          skip_assets=False, surface_status=None):
    selection = json.loads((official / 'selection.json').read_text(encoding='utf-8'))
    entry = selection['selected']
    folder = official / 'parsed' / entry['herourl'].rsplit('/', 1)[0].lstrip('/')
    load = lambda name: json.loads((folder / name).read_text(encoding='utf-8')) if (folder / name).is_file() else None
    mode, version = str(entry['mode']), entry['version']
    version_id = f"{season_id}__{re.sub(r'[^0-9A-Za-z]+', '_', version)}"
    season_dir = output / 'data' / 'seasons' / season_id
    version_dir = season_dir / version
    version_dir.mkdir(parents=True, exist_ok=True)
    previous_ids = None
    if previous:
        previous_ids = {c['id'] for c in json.loads((previous / 'champions.json').read_text(encoding='utf-8'))['champions']}

    splash_token = f"mode{mode}{str(entry['season']).lower()}"
    traits, trait_assets = build_traits(load('race.json'), load('job.json'))
    champions, champion_assets = build_champions(load('chess.json'), load('mission.json'), mode, splash_token, previous_ids,
                                                 {t['id'] for t in traits})
    items, item_assets = build_items(load('equip.json'), {t['name']: t['id'] for t in traits})
    augment_assets = [(url, local) for url, local in augment_image_paths(load('hex.json'))] if load('hex.json') else []
    assets = {} if skip_assets else download_assets(
        version_dir, champion_assets + trait_assets + item_assets + augment_assets, timeout, attempts, workers)
    champions_doc = {'version_id': version_id, 'champions': champions}
    traits_doc = {'version_id': version_id, 'traits': traits}
    items_doc = {'version_id': version_id, 'items': items}
    for document, key in ((champions_doc, 'champions'), (traits_doc, 'traits'), (items_doc, 'items')):
        if not skip_assets:
            drop_missing_images(document, key, version_dir)
        dump(version_dir / f'{key}.json', document)
    snapshots = version_dir / 'source-snapshots'
    for name in ('chess.json', 'hex.json'):
        if load(name) is not None:
            dump(snapshots / name, load(name))
    dump(snapshots / 'version-entry.json', entry)
    dump(version_dir / 'version.json', {
        'version_id': version_id, 'game_version': version, 'effective_at': entry.get('version_start_time') or None,
        'source': {'directory_url': selection.get('directory_url'), 'branch': entry, 'archive': official.name,
                   'collected_at': json.loads((official / 'manifest.json').read_text(encoding='utf-8')).get('collected_at')},
    })
    dump(season_dir / 'season.json', {
        'season_id': season_id, 'display_name': display_name, 'set_number': set_number, 'set_variant': set_variant,
        'theme': theme, 'status': 'hidden', 'surface_status': surface_status or {},
        'official_ids': {'mode': mode, 'client': entry['season']},
        'default_version_id': version_id, 'versions': [{'version_id': version_id, 'path': f'{version}/version.json'}],
    })
    catalog_path = output / 'data' / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.is_file() else {'seasons': []}
    catalog['seasons'] = [s for s in catalog['seasons'] if s['season_id'] != season_id] + [
        {'season_id': season_id, 'path': f'seasons/{season_id}/season.json', 'status': 'hidden'}]
    dump(catalog_path, catalog)
    failures = {local: record for local, record in assets.items() if record.get('error')}
    dump(version_dir / 'asset-report.json', {'generated_at': now(), 'assets': assets, 'failures': failures})
    return {'version_id': version_id, 'champions': len(champions), 'traits': len(traits), 'items': len(items),
            'assets': len(assets), 'asset_failures': len(failures)}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--official', required=True, type=Path, help='archive written by collect_orange_fortune.py')
    parser.add_argument('--output', required=True, type=Path, help='season-archive root (数据模板 layout)')
    parser.add_argument('--season-id', required=True)
    parser.add_argument('--display-name', required=True)
    parser.add_argument('--set-number', required=True)
    parser.add_argument('--set-variant', default='')
    parser.add_argument('--theme', default='')
    parser.add_argument('--previous-season', type=Path, help="season-data dir whose champions decide the 'new' tag")
    parser.add_argument('--surface', action='append', default=[], metavar='KIND=STATUS',
                        help='initial per-surface status, e.g. creator=active; other surfaces start hidden')
    parser.add_argument('--skip-assets', action='store_true', help='write JSON only (comparison runs); images are not fetched')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--workers', type=int, default=4)
    options = parser.parse_args()
    summary = build(options.official, options.output, options.season_id, options.display_name, options.set_number,
                    options.set_variant, options.theme, options.previous_season, options.timeout,
                    max(1, options.attempts), max(1, options.workers), options.skip_assets,
                    dict(item.split('=', 1) for item in options.surface))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
