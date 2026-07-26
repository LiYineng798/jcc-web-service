"""Build lineup-simulator data files from the season library.

Reads ``static/season-data/<season_id>/`` (produced by
``import_from_archive.py``) and regenerates the simulator's six data files
plus its WebP/blur image trees, so a new season only needs a library import
followed by this build:

    python scripts/season_library/import_from_archive.py --season s19
    python scripts/season_library/build_simulator_from_library.py --season s19

Champions with identical (name, cost, trait set) are collapsed into one
simulator entry (skin variants), while同名 different-trait forms are kept.

Entries the archive does not cover (special consumables scraped from other
sources, summoned pets) live in ``static/tools/lineup-simulator/extras/
<season_id>.json`` with the shape ``{"equips": [...], "pets": [...]}``; they
are appended verbatim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRARY_ROOT = REPO_ROOT / 'static' / 'season-data'
SIMULATOR_ROOT = REPO_ROOT / 'static' / 'tools' / 'lineup-simulator'

ITEM_CATEGORY_TABS = {
    'component': '散件',
    'completed': '成装',
    'radiant': '光明装',
    'artifact': '神器',
    'emblem': '纹章',
    'support': '特殊装备',
    'consumable': '特殊装备',
    'other': '未归类',
}
EQUIP_TABS = ['散件', '成装', '光明装', '神器', '纹章', '特殊装备', '未归类']
TRAIT_STYLE_COLORS = {'bronze': 1, 'silver': 2, 'gold': 3, 'prismatic': 4, 'unique': 5}
ICON_MAX_SIZE = 96
BLUR_SIZE = 16
WEBP_QUALITY = 82


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def image_target(season_id: str, kind: str, entity_id: str) -> str:
    return f'webp/season/{season_id}/{kind}/{entity_id}.webp'


def build_webp(source: Path, relative_target: str, *, max_size: int, skip_existing: bool) -> None:
    for prefix, size in ((SIMULATOR_ROOT, max_size), (SIMULATOR_ROOT / 'blur', BLUR_SIZE)):
        target = prefix / relative_target
        if skip_existing and target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            frame = image.convert('RGBA') if image.mode in {'P', 'LA'} else image.copy()
            frame.thumbnail((size, size), Image.LANCZOS)
            frame.save(target, format='WEBP', quality=WEBP_QUALITY, method=6)


def dedupe_champions(champions: list[dict], trait_names: dict[str, str]) -> list[dict]:
    seen = set()
    kept = []
    for champion in champions:
        names = tuple(trait_names.get(trait_id, trait_id) for trait_id in champion.get('trait_ids') or [])
        signature = (champion['name'], champion.get('cost'), names)
        if signature in seen:
            continue
        seen.add(signature)
        kept.append(champion)
    return kept


def build(season_id: str, *, skip_images: bool = False, skip_existing_images: bool = False) -> None:
    season_dir = LIBRARY_ROOT / season_id
    if not (season_dir / 'index.json').is_file():
        raise SystemExit(f'找不到 {season_dir}/index.json，请先运行 import_from_archive.py --season {season_id}')
    index = load_json(season_dir / 'index.json')
    items_path = season_dir / 'items.json'
    items = load_json(items_path).get('items') or [] if items_path.is_file() else []

    traits = index.get('traits') or []
    trait_names = {trait['id']: trait['name'] for trait in traits}
    champions = dedupe_champions(index.get('champions') or [], trait_names)

    heroes = []
    for champion in champions:
        names = [trait_names.get(trait_id, trait_id) for trait_id in champion.get('trait_ids') or []]
        heroes.append({
            'key': str(champion['id']),
            'name': champion['name'],
            'cost': champion.get('cost'),
            'costLabel': f"{champion.get('cost')}费",
            'traits': names,
            'image': image_target(season_id, 'heroes', champion['id']),
            'searchText': ' '.join([champion['name'], *names]),
        })

    equips = []
    for item in items:
        extensions = item.get('extensions') or {}
        tab = ITEM_CATEGORY_TABS.get(item.get('category'), '未归类')
        if item.get('category') == 'other' and extensions.get('source_type') == '特殊装备':
            tab = '特殊装备'
        granted_trait = ''
        if item.get('category') == 'emblem':
            trait_id = extensions.get('trait_id') or extensions.get('fetter_id')
            granted_trait = trait_names.get(str(trait_id), '') if trait_id else ''
        source_type = extensions.get('source_type') or ''
        equips.append({
            'id': str(item['id']),
            'name': item['name'],
            'type': tab,
            'sourceType': source_type,
            'grantedTrait': granted_trait,
            'image': image_target(season_id, 'items', item['id']),
            'draggable': item.get('category') != 'component',
            'searchText': ' '.join(filter(None, [item['name'], tab, source_type])),
        })

    trait_rows = []
    for trait in traits:
        levels = []
        for position, breakpoint in enumerate(trait.get('breakpoints') or [], start=1):
            values = breakpoint.get('values') or {}
            try:
                color = int(values.get('source_style'))
            except (TypeError, ValueError):
                color = TRAIT_STYLE_COLORS.get(breakpoint.get('style'), position)
            levels.append({'level': position, 'count': breakpoint.get('min_units'), 'color': color})
        trait_rows.append({
            'id': str(trait['id']),
            'name': trait['name'],
            'type': 'job' if trait.get('category') == 'class' else 'race',
            'image': image_target(season_id, 'traits', trait['id']),
            'levels': levels,
        })

    extras_path = SIMULATOR_ROOT / 'extras' / f'{season_id}.json'
    extras = load_json(extras_path) if extras_path.is_file() else {}
    equips.extend(extras.get('equips') or [])
    pets = extras.get('pets') or []

    costs = sorted({hero['cost'] for hero in heroes if hero['cost'] is not None})
    tabs = {
        'heroCostTabs': ['全部', *[f'{cost}费' for cost in costs]],
        'equipTabs': EQUIP_TABS,
    }
    version = {
        'set': season_id,
        'version': index.get('game_version') or 'unknown',
        'updatedAt': index.get('effective_at') or index.get('version_id') or 'unknown',
        'source': f'static/season-data/{season_id}',
        'note': '由 scripts/season_library/build_simulator_from_library.py 生成',
    }

    data_dir = SIMULATOR_ROOT / 'data'
    write_json(data_dir / 'version.json', version)
    write_json(data_dir / 'tabs.json', tabs)
    write_json(data_dir / 'heroes.json', heroes)
    write_json(data_dir / 'equips.json', equips)
    write_json(data_dir / 'traits.json', trait_rows)
    write_json(data_dir / 'pets.json', pets)
    print(f'数据已生成：弈子 {len(heroes)}，装备 {len(equips)}（含补充 {len(extras.get("equips") or [])}），'
          f'羁绊 {len(trait_rows)}，召唤物 {len(pets)}')

    if skip_images:
        return
    missing = []
    jobs = []
    for champion in champions:
        jobs.append((champion.get('icon'), image_target(season_id, 'heroes', champion['id'])))
    for item in items:
        item_image = item.get('image')
        local = item_image.get('local_path') if isinstance(item_image, dict) else None
        jobs.append((local, image_target(season_id, 'items', item['id'])))
    for trait in traits:
        jobs.append((trait.get('image'), image_target(season_id, 'traits', trait['id'])))
    built = 0
    for relative_source, relative_target in jobs:
        source = (season_dir / relative_source) if relative_source else None
        if source is None or not source.is_file():
            missing.append(relative_target)
            continue
        build_webp(source, relative_target, max_size=ICON_MAX_SIZE, skip_existing=skip_existing_images)
        built += 1
    print(f'图片已生成 {built} 组（webp + blur）')
    for relative_target in missing:
        print(f'  警告: 缺少源图片，未生成 {relative_target}')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--season', required=True, help='season-data 下的 season_id，如 s17')
    parser.add_argument('--skip-images', action='store_true', help='只生成 JSON，不生成图片')
    parser.add_argument('--skip-existing-images', action='store_true', help='已存在的 webp 不重新生成')
    args = parser.parse_args(argv)
    build(args.season, skip_images=args.skip_images, skip_existing_images=args.skip_existing_images)
    return 0


if __name__ == '__main__':
    sys.exit(main())
