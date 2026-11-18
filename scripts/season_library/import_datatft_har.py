"""Build an offline PBE preview from a user-supplied DataTFT HAR.

    python scripts/season_library/import_datatft_har.py --har <capture.har> <more.har> \
        --output-root <new-output-directory> --inherit-from static/season-data/s18 --register

Requires Node.js (built-in crypto), Pillow and CairoSVG. Never executes captured
JavaScript or follows remote URLs. Refuses to overwrite an existing season.
The HAR stays private; only game records, image bytes and a source hash survive.
Multiple captures must contain identical S19 records. Previous-season modules
are optional, copied with their local images, and explicitly marked as inherited.
Use --asset-har for older captures that supply images only; their records are ignored.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from season_rich_text import enrich_rich_text_fields
from scripts.season_library.import_from_archive import (
    build_card_thumbnail, compact_champion, compact_trait, compact_augment,
    dump_json, generate_optimized_images,
)

SID = 's19'
VERSION = 'PBE'
VID = 's19__pbe'
NAME = 'S19 棱彩音乐盛典'
STYLES = {1: 'bronze', 2: 'silver', 3: 'gold', 4: 'prismatic'}
NOTICE = 'PBE 预览资料；缺失数值及 xx 条件保留原样。'
SIM_NOTICE = 'PBE 布阵预览：支持 K/DA 星级计数、娑娜乐队选择、特殊人口与真实伤害 A/B 面。洛克隆体仅作站位及装备复制预览，人口未核定；海之歌乐器数量、合奏随机名单及棱彩追加条件暂缺。'


def display_text(raw):
    """Convert upstream formatting to safe text; retain the untouched source record."""
    class Text(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.blocked = 0

        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style'):
                self.blocked += 1
            elif not self.blocked and tag in ('br', 'p', 'div'):
                self.parts.append('\n')

        def handle_endtag(self, tag):
            if tag in ('script', 'style'):
                self.blocked = max(0, self.blocked - 1)
            elif not self.blocked and tag in ('p', 'div'):
                self.parts.append('\n')

        def handle_data(self, value):
            if not self.blocked:
                self.parts.append(value)

    parser = Text()
    parser.feed(str(raw or ''))
    value = ''.join(parser.parts).strip()
    for old, new in {'【DIST】': ' ', '【SV】': '【全能吸血】', '【MANAREGEN】': '【法力回复】'}.items():
        value = value.replace(old, new)
    return value


def response_bytes(entry):
    content = entry.get('response', {}).get('content', {})
    text = content.get('text', '')
    return base64.b64decode(text, validate=True) if content.get('encoding') == 'base64' else text.encode('utf-8')


def decode_har(path):
    raw = Path(path).read_bytes()
    entries = json.loads(raw.decode('utf-8-sig'))['log']['entries']
    scripts = []
    for entry in entries:
        url = urlsplit(entry['request']['url'])
        if url.hostname == 'www.datatft.com' and url.path.startswith('/assets/') and url.path.endswith('.js'):
            scripts.append((entry['request']['url'], response_bytes(entry).decode('utf-8')))
    key = next((m[1] for _, text in scripts if (m := re.search(r'currentData:null,key:"([A-Za-z0-9+/=]+)"', text))), None)
    payloads = [(url, m[1]) for url, text in scripts if '/data-cn-' in url
                and (m := re.fullmatch(r'const \w+="([A-Za-z0-9+/=]+)";export\{\w+ as data\};\s*', text))]
    if not key or len(payloads) != 1:
        raise ValueError('HAR 需包含一个中文资料包及其客户端解析配置，请重新完整录制')
    # Reimplement the public data decoder; do not eval captured scripts.
    decoder = """const c=require('node:crypto');let s='';process.stdin.setEncoding('utf8');
process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{const p=JSON.parse(s),
k=Buffer.from(p.key,'base64'),d=c.createDecipheriv(`aes-${k.length*8}-ecb`,k,null);
process.stdout.write(Buffer.concat([d.update(Buffer.from(p.data,'base64')),d.final()]));});"""
    result = subprocess.run(['node', '-e', decoder], input=json.dumps({'key': key, 'data': payloads[0][1]}),
                            text=True, encoding='utf-8', capture_output=True, check=True, timeout=30)
    data = json.loads(result.stdout)
    for field in ('heros19', 'races19', 'jobs19', 'equips19', 'hexs19'):
        if not isinstance(data.get(field), list) or not data[field]:
            raise ValueError(f'中文资料包缺少 {field}')
    source = {'id': 'datatft-user-har', 'type': 'community_preview', 'url': payloads[0][0],
              'har_sha256': hashlib.sha256(raw).hexdigest(), 'source_updated_at':
              datetime.fromtimestamp(data['databaseUpdateTime'] / 1000, timezone.utc).isoformat(),
              'verified_for_current_patch': False, 'note': '以用户提供的 HAR 为准；不是官方正式服快照'}
    return data, entries, scripts, source


def image(path, *, url=None, missing=False):
    return {'local_path': path, 'source_url': url, 'placeholder': missing}


def decode_hars(paths):
    paths = [paths] if isinstance(paths, (str, Path)) else list(paths)
    captures = [decode_har(path) for path in paths]
    if not captures:
        raise ValueError('至少需要一份 HAR')
    fingerprints = {hashlib.sha256(json.dumps({k: data[k] for k in (
        'heros19', 'races19', 'jobs19', 'equips19', 'hexs19')}, sort_keys=True).encode()).hexdigest()
        for data, *_ in captures}
    if len(fingerprints) != 1:
        raise ValueError('HAR 中的 S19 资料不一致，请按同一资料版本分组导入')
    data, _, _, source = max(captures, key=lambda c: c[0]['databaseUpdateTime'])
    source = dict(source, capture_count=len(captures),
                  capture_sha256=[c[3]['har_sha256'] for c in captures],
                  data_sha256=next(iter(fingerprints)))
    return data, [e for c in captures for e in c[1]], list(dict.fromkeys(s for c in captures for s in c[2])), source


def inherit_modules(records, previous, target):
    previous = Path(previous).resolve()
    index = json.loads((previous / 'index.json').read_text(encoding='utf-8'))
    source = {'id': 'previous-season-modules', 'type': 'previous_season_snapshot',
              'season_id': index['season_id'], 'version_id': index['version_id'],
              'game_version': index['game_version'], 'verified_for_current_patch': False,
              'modules': ['items', 'augments'], 'sha256': {}}
    old_traits = json.loads((previous / 'traits.json').read_text(encoding='utf-8'))['traits']
    old_names = {str(t['id']): t['name'] for t in old_traits}
    new_traits = {t['name']: t['id'] for t in records['traits']}

    def copy_images(value):
        if isinstance(value, list):
            for child in value:
                copy_images(child)
        elif isinstance(value, dict):
            for key, child in value.items():
                if key in ('local_path', 'optimized_local_path') and child:
                    origin = (previous / child).resolve()
                    if not origin.is_relative_to(previous) or not origin.is_file():
                        raise ValueError(f'沿用资料图片不存在或越界：{child}')
                    local = 'assets/inherited/' + origin.relative_to(previous).as_posix()
                    dest = target / local
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(origin, dest)
                    value[key] = local
                else:
                    copy_images(child)

    for module in source['modules']:
        raw = (previous / f'{module}.json').read_bytes()
        source['sha256'][module] = hashlib.sha256(raw).hexdigest()
        records[module] = copy.deepcopy(json.loads(raw)[module])
        for row in records[module]:
            copy_images(row)
            ext = row.setdefault('extensions', {})
            ext['inherited_from'] = {k: source[k] for k in ('season_id', 'version_id', 'game_version', 'verified_for_current_patch')}
            if module == 'items' and row['category'] == 'emblem':
                old_id = ext.get('trait_id') or ext.get('fetter_id')
                name = old_names.get(str(old_id), row['name'].removesuffix('纹章'))
                ext['inherited_trait_id'] = old_id
                ext['fetter_id'] = None
                ext['trait_id'] = new_traits.get(name)
                ext['simulator_visible'] = bool(ext['trait_id'])
                if not ext['trait_id']:
                    ext['unresolved_trait_name'] = name
    return source, {**index.get('augment_meta', {}), 'source': source}


def placeholder(target):
    path = 'assets/missing.png'
    canvas = Image.new('RGBA', (96, 96), '#263244')
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((8, 8, 88, 88), radius=12, outline='#8995a6', width=2)
    draw.text((38, 28), '?', fill='#dce3ed', font_size=40)
    canvas.save(target / path)
    return image(path, missing=True)


def extract_assets(data, entries, scripts, target):
    import cairosvg
    (target / 'assets').mkdir(parents=True)
    missing = placeholder(target)
    portraits, icons, traits = {}, {}, {}
    hero_ids = {str(row['chessId']) for row in data['heros19']}
    for entry in entries:
        url = urlsplit(entry['request']['url'])
        match = re.fullmatch(r'/images/heros/(bg|default)/[^/]+/(\d+)\.jpg', url.path)
        if url.hostname != 'static.datatft.com' or not match or match[2] not in hero_ids:
            continue
        raw = response_bytes(entry)
        if not raw:
            continue
        with Image.open(BytesIO(raw)) as frame:
            frame.verify()
        kind = 'splash' if match[1] == 'bg' else 'icons'
        local = f'assets/champions/{kind}/{match[2]}.jpg'
        destination = target / local
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        (portraits if kind == 'splash' else icons)[match[2]] = image(local, url=entry['request']['url'])
    known_keys = {r['key'] for r in data['races19'] + data['jobs19']}
    for _, script in scripts:
        for match in re.finditer(r'<symbol id="custom-trait-([^"]+)" viewBox="([\d .-]+)">(.*?)</symbol>', script):
            key = html.unescape(match[1])
            if key not in known_keys:
                continue
            # Only path geometry is accepted. Strip scripts, links and all other SVG attributes.
            paths = re.findall(r'<path\s+d="([MmZzLlHhVvCcSsQqTtAaEe0-9.,+\s-]+)"', match[3])
            if not paths:
                continue
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{match[2]}">' + ''.join(
                f'<path fill="#edf2f7" d="{p}"/>' for p in paths) + '</svg>'
            local = f'assets/traits/{hashlib.sha256(key.encode()).hexdigest()[:16]}.png'
            destination = target / local
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(cairosvg.svg2png(bytestring=svg.encode(), output_width=96, output_height=96))
            traits[key] = image(local)
    return portraits, icons, traits, missing


def split_ids(raw):
    return [v for v in re.split(r'[,|]', str(raw or '')) if v]


def stats_by_star(row):
    health = str(row.get('lifeData2') or row['lifeData']).split('/')
    attack = str(row.get('attackData2') or row['attackData']).split('/')
    fixed = {target: float(row[source]) for source, target in {
        'armor': 'armor', 'spellBlock': 'magic_resist', 'attackSpeed': 'attack_speed',
        'attackRange': 'attack_range', 'startMagic': 'initial_mana', 'magic': 'max_mana',
    }.items() if row.get(source) is not None}
    return {str(i + 1): {**fixed, 'health': float(h), 'attack_damage': float(attack[i]) if i < len(attack) else None}
            for i, h in enumerate(health)}


def trait_breakpoint_style(trait, breakpoint):
    """Match DataTFT's TraitComponent.levelStyleFix, preserving raw source data."""
    style = STYLES.get(breakpoint['levelStyle'], 'bronze')
    if style == 'gold' and len(trait.get('level', [])) == 1 and len(trait.get('heros', [])) == 1:
        return 'unique'
    return style


def build_records(data, portraits, trait_images, missing, icons=None):
    icons = icons or {}
    traits = []
    trait_lookup = {}
    for category, rows, field in (('origin', data['races19'], 'raceId'), ('class', data['jobs19'], 'jobId')):
        for row in rows:
            tid = f'{category}-{row[field]}'
            trait_lookup[category, str(row[field])] = tid
            traits.append({'id': tid, 'name': row['name'], 'category': category,
                           'description': display_text(row.get('introduce')), 'image': dict(trait_images.get(row['key'], missing)),
                           'breakpoints': [{'min_units': int(v['level']), 'max_units': None,
                                            'style': trait_breakpoint_style(row, v), 'effect': display_text(v.get('levelDesc'))}
                                           for v in row.get('level', [])],
                           'source_ids': {'datatft_id': str(row[field]), 'datatft_key': row['key']},
                           'extensions': {'datatft': row}, 'tags': []})
    champions = []
    for row in data['heros19']:
        cid = str(row['chessId'])
        unlock = row.get('unlockDesc') or None
        champions.append({'id': cid, 'name': row['displayName'], 'cost': int(row['price']),
                          'aliases': row.get('otherNames') or [], 'role': row.get('role'),
                          'trait_ids': [trait_lookup[cat, n] for cat, field in (('origin', 'raceIds'), ('class', 'jobIds'))
                                        for n in split_ids(row.get(field))],
                          'availability': {'type': 'unlock' if unlock else 'unknown', 'description': unlock, 'rules': []},
                          'stats_by_star': stats_by_star(row),
                          'skills': [{'id': f'{cid}_skill', 'name': row['skillName'], 'description': display_text(row['skillDetail2']),
                                      'variables': [], 'raw_values': None, 'image': None}],
                          'images': {'icon': dict(icons.get(cid, portraits.get(cid, missing))), 'splash': dict(portraits.get(cid, missing))},
                          'source_ids': {'datatft_chess_id': cid}, 'tags': [],
                          'extensions': {'datatft': row, 'unlock_incomplete': bool(re.search(r'x{2,}', unlock or '')),
                                         'skill_values_complete': False}})
    categories = {'part': 'component', 'common': 'completed', 'aoen': 'artifact', 'guangming': 'radiant',
                  'remove': 'consumable', 'zhuanzhi': 'emblem', 'zhuanzhiJgg': 'emblem', 'zhuanzhi2': 'emblem'}
    trait_names = {t['name']: t['id'] for t in traits}
    items = []
    for row in data['equips19']:
        components = split_ids(row.get('formula'))
        description = display_text('\n'.join(str(row.get(f) or '') for f in ('effectAttr', 'effect')))
        grant = next((tid for name, tid in trait_names.items() if row['name'] in (name + '纹章', name + '转职')) , None)
        category = categories.get(row['type2'], 'other')
        unsupported = category == 'emblem' and not grant
        items.append({'id': str(row['equipId']), 'name': row['name'], 'category': category,
                      'description': description, 'stats': {'raw': display_text(row.get('effectAttr')), 'values': []},
                      'effects': [], 'unique': '唯一' in description, 'image': dict(missing),
                      'recipe': {'type': 'components' if components else 'none', 'component_ids': components},
                      'source_ids': {'datatft_key': row['key']},
                      'extensions': {'datatft': row, 'trait_id': grant,
                                     **({'simulator_visible': False, 'unresolved_trait_name': row['name']} if unsupported else {})}, 'tags': []})
    augments = []
    for group, tier in zip(data['hexs19'], ('silver', 'gold', 'prismatic')):
        for row in group:
            raw_id = str(row['hexId'])
            aid = raw_id.lower() if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', raw_id) else 'har-' + hashlib.sha256(raw_id.encode()).hexdigest()[:20]
            augments.append({'id': aid, 'name': row['name'], 'description': display_text(row['desc']),
                             'tier': tier, 'tier_label': {'silver': '白银', 'gold': '黄金', 'prismatic': '棱彩'}[tier],
                             'tier_order': ('silver', 'gold', 'prismatic').index(tier) + 1,
                             'category': 'other', 'category_label': '其他', 'image': dict(missing),
                             'source_ids': {'datatft_hex_id': raw_id},
                             'appearance_stages': row.get('round') or [],
                             'extensions': {'datatft': row, 'provenance': {'source_type': 'user_har',
                                            'verified_for_current_patch': False}}, 'tags': []})
    return {'champions': champions, 'traits': traits, 'items': items, 'augments': augments, 'board_units': []}


def adapt_simulator_rules(records):
    """Translate only explicit captured statements; keep unresolved mechanics auditable."""
    traits = {t['source_ids']['datatft_key']: t for t in records['traits']}
    heroes = {h['id']: h for h in records['champions']}
    kda = next((t for t in traits.values() if t['name'] == 'K/DA' and '总星级' in t['description']), None)
    if kda:
        kda['extensions']['simulator'] = {'count_mode': 'star_sum', 'count_label': '星',
            'note': '按不同弈子的最高星级相加；重复弈子不重复计数。'}
    for trait in records['traits']:
        rules = trait['extensions'].setdefault('simulator', {})
        sides = sorted({m[1] for p in trait['breakpoints'] if (m := re.match(r'【([AB])面】', p['effect']))})
        if sides:
            rules['sides'] = sides
        seen = set()
        for point in trait['breakpoints']:
            m = re.match(r'【([AB])面】', point['effect'])
            if m:
                point['side'] = m[1]
            key = (point.get('side'), point['min_units'])
            if key in seen:
                point['requires_confirmation'] = True
            seen.add(key)
        if any(p.get('requires_confirmation') for p in trait['breakpoints']):
            rules['note'] = '同人数档位的追加条件未完整提供。'
    director = traits.get('DA_19_Maestro') or next((t for t in traits.values() if t['name'] == '音乐总监'), None)
    if director and '919037' in heroes and '不占用队伍栏位' in director['description']:
        names = re.findall(r'【([^】]+)】', director['description'].split('可选的乐队：')[-1])
        ids = [t['id'] for name in names for t in traits.values() if t['name'] == name]
        heroes['919037']['extensions']['simulator'] = {'unit_slots': 0, 'choice_trait_ids': ids,
            'unique_choice': True}
    if '919981' in heroes and any('纳什男爵占用2个弈子栏位' in t['description'] for t in traits.values()):
        heroes['919981']['extensions']['simulator'] = {'unit_slots': 2}
    clones = next((t for t in traits.values() if t['name'] == '幻翎boys' and '2个可放置的克隆体' in t['description']), None)
    if clones and '919497' in heroes:
        records['board_units'].append({'id': 'rakan-clone', 'name': '洛的克隆体', 'kind': 'trait_object',
            'aliases': [], 'trait_ids': [clones['id']], 'contribution_trait_ids': [],
            'placement_rules': [{'champion_id': '919497', 'min_units': 1, 'max_count': 2}],
            'can_equip': False, 'stats': {}, 'skill': {'name': '幻翎克隆体', 'description': clones['description'], 'image': None},
            'image': copy.deepcopy(heroes['919497']['images']['icon']),
            'source_ids': {'datatft_trait': clones['source_ids']['datatft_key']},
            'extensions': {'simulator': {'copy_items_from': '919497', 'population_unverified': True},
                'provenance': {'source_type': 'user_har', 'verified_for_current_patch': False,
                    'note': '站位预览；复用洛头像；不推断克隆体人口、独立羁绊或战斗数值。'}}})
    return {'supported': ['K/DA 总星级', '娑娜五选一乐队及零人口', '纳什男爵两人口',
                          '真实伤害 A/B 面说明', '洛的两个克隆体站位及装备复制'],
            'review': ['洛克隆体人口与独立羁绊未核定；不贡献羁绊，人口显示下限。',
                       '海之歌明确可放置，但每局随机乐器、累计数量与人口规则不完整。',
                       '炼狱偶像仅说明召唤，没有可手动放置的依据。',
                       '神秘乐器明确无法放置；巴德木灵用于备战席出售，不作为布阵对象。',
                       '阿卡丽技能写 A 面金币/B 面回血，说唱女王描述相反；仅保留原文，不计算收益。',
                       '合奏每局随机名单缺失；真实伤害及心之钢重复人数棱彩档缺少追加条件。']}


def _build(har, output_root, inherit_from=None, asset_hars=None):
    output_root = Path(output_root).resolve()
    target = output_root / SID
    if target.exists():
        raise ValueError('目标 s19 目录已存在，请使用新的输出目录，避免覆盖已有资料')
    data, entries, scripts, source = decode_hars(har)
    if asset_hars:
        assets = [decode_har(path) for path in asset_hars]
        # Old snapshots contribute captured assets only. The primary HAR wins
        # for duplicate image IDs and remains the sole source of game records.
        entries = [e for _, es, _, _ in assets for e in es] + entries
        scripts = [s for _, _, ss, _ in assets for s in ss] + scripts
        source['asset_capture_sha256'] = [meta['har_sha256'] for _, _, _, meta in assets]
    portraits, icons, trait_images, missing = extract_assets(data, entries, scripts, target)
    records = build_records(data, portraits, trait_images, missing, icons)
    mechanics_audit = adapt_simulator_rules(records)
    inherited = None
    augment_meta = {'category_labels': {'other': '其他'}, 'stage_options': ['2-1', '3-2', '4-2'], 'source': source}
    notice, sim_notice = NOTICE, SIM_NOTICE
    if inherit_from:
        inherited, augment_meta = inherit_modules(records, inherit_from, target)
        inherited_notice = f"装备与强化符文暂沿用 {inherited['season_id'].upper()} {inherited['game_version']}，未核定为 S19 正式资料。"
        notice += inherited_notice
        sim_notice += inherited_notice
    documents = {name: {'version_id': VID, 'rich_text_version': 1, name: rows, 'source': source}
                 for name, rows in records.items()}
    documents['champions']['preview_notice'] = sim_notice
    documents['champions']['simulator_controls'] = True
    documents['board_units']['discovery_audit'] = mechanics_audit
    if inherited:
        for module in inherited['modules']:
            documents[module]['source'] = inherited
        documents['augments'].update(augment_meta)
    for doc in documents.values():
        originals = [(row, row['extensions'].pop('datatft')) for rows in doc.values() if isinstance(rows, list)
                     for row in rows if isinstance(row, dict) and 'datatft' in row.get('extensions', {})]
        enrich_rich_text_fields(doc)
        for row, raw in originals:
            row['extensions']['datatft'] = raw
    generate_optimized_images(target, VID, *(documents[k] for k in ('champions', 'traits', 'items', 'board_units', 'augments')))
    cards = {}
    for cid, img in portraits.items():
        cards[cid] = f'assets/champions/card/{cid}.webp'
        build_card_thumbnail(target / img['local_path'], target / cards[cid])
    for name, doc in documents.items():
        dump_json(target / f'{name}.json', doc, indent=2)
    metadata = {'season_id': SID, 'display_name': NAME, 'set_number': '19', 'set_variant': None,
                'theme': '棱彩音乐盛典', 'status': 'hidden', 'game_version': VERSION, 'version_id': VID,
                'effective_at': source['source_updated_at']}
    index = {**metadata, 'rich_text_version': 1, 'preview_notice': notice, 'simulator_notice': sim_notice,
             'champions': [compact_champion(r, cards.get(r['id'])) for r in records['champions']],
             'traits': [compact_trait(r) for r in records['traits']],
             'augments': [compact_augment(r) for r in records['augments']], 'mechanics': [],
             'augment_meta': augment_meta}
    dump_json(target / 'index.json', index)
    dump_json(target / 'tft-codebook.json', {'codes': {}, 'source_ids': {}})
    counts = {name: len(rows) for name, rows in records.items()} | {'mechanics': 0}
    dump_json(target / 'season.json', metadata | {'counts': counts})
    report = {'source': source, 'counts': counts, 'hero_images': len(portraits), 'hero_icons': len(icons), 'trait_images': len(trait_images),
              'unique_traits': [r['name'] for r in records['traits'] if any(p['style'] == 'unique' for p in r['breakpoints'])],
              'inherited_modules': inherited,
              'simulator_audit': mechanics_audit,
              'unlocks': sum(bool(r.get('unlockDesc')) for r in data['heros19']),
              'incomplete_unlocks': sum(bool(r['extensions']['unlock_incomplete']) for r in records['champions']),
              'unsupported_simulator_items': [r['id'] for r in records['items'] if r['extensions'].get('simulator_visible') is False],
              'missing_images': {k: [r['id'] for r in rows if (r.get('image') or r.get('images', {}).get('icon') or {}).get('placeholder')]
                                 for k, rows in records.items()},
              'excluded_modules': {'charms19': '与 charms18 完全相同，保留为来源审计，不接入 S19 玩法',
                                   'regions19': '开局奇遇未接入本次资料预览'},
              'charms_equal_s18': data.get('charms19') == data.get('charms18'),
              'notes': [notice, sim_notice, '仅使用本地 HAR 和已选上一赛季资料；未请求远端图片。']}
    dump_json(target / 'import-report.json', report, indent=2)
    dump_json(target / 'provenance.json', {'sources': [source] + ([inherited] if inherited else [])}, indent=2)
    dump_json(target / 'release-notes.json', {'title': 'S19 PBE 资料预览', 'summary': notice,
              'sections': [{'title': '资料', 'items': ['以用户 HAR 为准导入英雄、羁绊与图片。', sim_notice]}]}, indent=2)
    return report


def build(har, output_root, register=False, inherit_from=None, asset_hars=None):
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / SID
    catalog_path = output_root / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.exists() else {'format_version': '1.0.0', 'seasons': []}
    if target.exists() or (register and any(r['season_id'] == SID for r in catalog['seasons'])):
        raise ValueError('目标赛季已存在，请使用新的输出目录，避免覆盖已有资料')
    with tempfile.TemporaryDirectory(prefix='.pbe-build-', dir=output_root) as staging:
        report = _build(har, staging, inherit_from, asset_hars)
        staged = Path(staging) / SID
        metadata = json.loads((staged / 'season.json').read_text(encoding='utf-8'))
        staged.rename(target)
    if register:
        catalog['seasons'].append(metadata | {'path': f'{SID}/index.json',
                                             'surface_status': {'library': 'hidden', 'simulator': 'hidden', 'creator': 'hidden'}})
        dump_json(catalog_path, catalog)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--har', required=True, type=Path, nargs='+')
    parser.add_argument('--inherit-from', type=Path, help='沿用指定本地赛季的装备、强化符文及图片')
    parser.add_argument('--asset-har', type=Path, nargs='+', help='旧 HAR 仅补充图片，不混入旧赛季记录；主 HAR 图片优先')
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--register', action='store_true')
    args = parser.parse_args()
    report = build(args.har, args.output_root, args.register, args.inherit_from, args.asset_har)
    print(json.dumps({k: report[k] for k in ('counts', 'hero_images', 'trait_images', 'unlocks', 'incomplete_unlocks')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
