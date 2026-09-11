"""Offline, shared upload-package contract. Never fetch URLs or execute package code."""

from __future__ import annotations

import hashlib
import json
import math
import re
import stat
import unicodedata
import zipfile
from functools import lru_cache
from pathlib import Path, PurePosixPath

from PIL import Image

FORMAT = 'jcc-season-package'
SCHEMA = '1.0'
MODULES = ('champions', 'traits', 'items', 'augments', 'board_units')
CAPABILITIES = {
    'reference.cards.v1',
    'reference.variants.v1',
    'reference.stages.v1',
    'reference.table.v1',
    'simulator.placement_rules.v1',
}
PRESENTATIONS = {'cards.v1', 'variants.v1', 'stages.v1', 'table.v1', 'legacy.v1'}
ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,95}$')
VERSION = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
DEFAULT_LIMITS = {'bytes': 256 * 1024**2, 'expanded': 1024**3, 'files': 10000, 'json': 32 * 1024**2}


class PackageError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PackageError(message)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, f'JSON 字段重复：{key}')
        value[key] = item
    return value


def parse_json(raw):
    def finite_float(value):
        number = float(value)
        require(math.isfinite(number), '不允许非有限数字')
        return number

    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique_pairs,
            parse_float=finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(PackageError('不允许非有限数字')),
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PackageError(f'JSON 无效：{str(exc)[:180]}') from exc


def read_json(path):
    return parse_json(path.read_bytes())


def safe_path(value):
    require(isinstance(value, str) and 0 < len(value) <= 240, '包内路径无效')
    require('\\' not in value and ':' not in value and '\x00' not in value, f'路径无效：{value}')
    p = PurePosixPath(value)
    require(
        not p.is_absolute() and all(part not in ('', '.', '..') for part in value.split('/')),
        f'路径越界：{value}',
    )
    require(all(not part.endswith((' ', '.')) for part in p.parts), f'路径不规范：{value}')
    require(
        all(
            not re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?', part)
            for part in p.parts
        ),
        '保留文件名不允许',
    )
    return value


def inspect_zip(path, limits=None):
    """Inspect names/sizes/manifest before extraction; all extraction is explicit."""
    limits = {**DEFAULT_LIMITS, **(limits or {})}
    require(path.stat().st_size <= limits['bytes'], '更新包超过上传大小限制')
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            require(0 < len(infos) <= limits['files'], '文件数量超限')
            total, names, folded = 0, set(), set()
            for info in infos:
                name = safe_path(info.filename)
                normalized = unicodedata.normalize('NFC', name).casefold()
                require(normalized not in folded, f'文件名重复：{name}')
                folded.add(normalized)
                require(not info.is_dir(), '更新包不应包含独立目录条目')
                mode = info.external_attr >> 16
                require(stat.S_IFMT(mode) in (0, stat.S_IFREG), f'不允许链接或特殊文件：{name}')
                require(not info.flag_bits & 1, '不支持加密 ZIP')
                require(
                    info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                    '不支持此压缩算法',
                )
                suffix = PurePosixPath(name).suffix.lower()
                require(
                    suffix in {'.json', '.png', '.jpg', '.jpeg', '.webp'},
                    f'不允许的文件类型：{name}',
                )
                if suffix != '.json':
                    require(name.startswith('assets/'), f'图片必须位于 assets：{name}')
                else:
                    require(info.file_size <= limits['json'], f'JSON 过大：{name}')
                require(info.file_size <= 64 * 1024**2, f'单文件过大：{name}')
                require(info.file_size / max(1, info.compress_size) <= 250, f'压缩比异常：{name}')
                total += info.file_size
                require(total <= limits['expanded'], '解压总大小超限')
                names.add(name)
            require('manifest.json' in names, '缺少 manifest.json')
            require(z.getinfo('manifest.json').file_size <= 4 * 1024**2, 'manifest 过大')
            manifest = parse_json(z.read('manifest.json'))
            validate_manifest(manifest)
            listed = manifest['files']
            require(set(listed) == names - {'manifest.json'}, '文件清单与 ZIP 内容不一致')
            for name, meta in listed.items():
                require(
                    isinstance(meta, dict) and isinstance(meta.get('bytes'), int),
                    f'文件声明无效：{name}',
                )
                require(meta['bytes'] == z.getinfo(name).file_size, f'文件大小不符：{name}')
                require(
                    re.fullmatch('[0-9a-f]{64}', str(meta.get('sha256', ''))),
                    f'文件哈希无效：{name}',
                )
            return manifest
    except (zipfile.BadZipFile, RuntimeError, KeyError) as exc:
        raise PackageError(f'ZIP 无效：{str(exc)[:180]}') from exc


def validate_manifest(m):
    require(isinstance(m, dict), 'manifest 必须是对象')
    require(m.get('package_format') == FORMAT, '不是 JCC 赛季更新包')
    require(
        m.get('package_schema_version') == SCHEMA and m.get('dataset_schema_version') == SCHEMA,
        '不支持的包或数据协议',
    )
    for field in ('package_id', 'season_id'):
        require(isinstance(m.get(field), str) and ID.fullmatch(m[field]), f'{field} 无效')
    require(VERSION.fullmatch(str(m.get('game_version', ''))), 'game_version 无效')
    require(
        type(m.get('data_revision')) is int and m['data_revision'] > 0, 'data_revision 必须是正整数'
    )
    require(isinstance(m.get('required_capabilities'), list), '缺少 required_capabilities')
    require(
        all(isinstance(c, str) and c in CAPABILITIES for c in m['required_capabilities']),
        '网站尚不支持包内必需能力，请先升级代码',
    )
    require(isinstance(m.get('files'), dict), '缺少完整文件清单')
    require(
        isinstance(m.get('modules'), dict) and set(m['modules']) == set(MODULES),
        '必须声明全部核心模块',
    )
    for name in MODULES:
        module = m['modules'][name]
        require(
            isinstance(module, dict) and module.get('state') in ('present', 'absent'),
            f'{name} 状态未知或无效',
        )
        require(module.get('file') == f'data/{name}.json', f'{name} 文件路径无效')
        if name in ('champions', 'traits', 'items'):
            require(module['state'] == 'present', f'{name} 不能缺失')
    require(isinstance(m.get('mechanics'), list) and len(m['mechanics']) <= 20, '玩法清单无效')
    ids = set()
    for mechanic in m['mechanics']:
        require(isinstance(mechanic, dict), '玩法声明必须是对象')
        mid = mechanic.get('id')
        require(isinstance(mid, str) and ID.fullmatch(mid) and mid not in ids, '玩法 ID 重复或无效')
        ids.add(mid)
        require(mechanic.get('file') == f'data/mechanics/{mid}.json', f'{mid} 路径无效')
        require(mechanic.get('presentation') in PRESENTATIONS, f'{mid} 展示模板不受支持')
        if mechanic['presentation'] != 'legacy.v1':
            require(
                f'reference.{mechanic["presentation"]}' in m['required_capabilities'],
                '玩法未声明所需展示能力',
            )
        require(
            mechanic.get('targets') == ['reference'],
            '新玩法的模拟器行为需通过受支持 board_units 能力提供',
        )
        require(
            isinstance(mechanic.get('display_name'), str)
            and 0 < len(mechanic['display_name']) <= 60,
            '玩法名称无效',
        )
        require(
            isinstance(mechanic.get('kind'), str) and ID.fullmatch(mechanic['kind']),
            '玩法 kind 无效',
        )
        if mechanic['presentation'] == 'legacy.v1':
            require(
                mechanic['kind'] in ('charm', 'wand', 'god', 'monster', 'none'),
                '新玩法请使用通用展示模板',
            )


def extract_package(zip_path, target, manifest, progress=lambda *args: None):
    require(not target.exists(), '解包目标已存在')
    target.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        total = len(z.infolist())
        for i, info in enumerate(z.infolist()):
            path = target / safe_path(info.filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            digest, count = hashlib.sha256(), 0
            with z.open(info) as source, path.open('xb') as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    count += len(chunk)
                    require(count <= info.file_size, f'解压大小不符：{info.filename}')
                    digest.update(chunk)
                    output.write(chunk)
            if info.filename != 'manifest.json':
                require(
                    digest.hexdigest() == manifest['files'][info.filename]['sha256'],
                    f'文件校验失败：{info.filename}',
                )
            progress('extracting', 5 + int(35 * (i + 1) / total), info.filename)


def records(document, key):
    require(isinstance(document, dict) and isinstance(document.get(key), list), f'{key} 必须是数组')
    rows = document[key]
    require(len(rows) <= 5000, f'{key} 记录数超限')
    seen = set()
    for row in rows:
        require(isinstance(row, dict), f'{key} 记录无效')
        require(
            row.get('description') is None or isinstance(row['description'], str),
            f'{key} 说明必须是文本',
        )
        rid = row.get('id')
        require(
            isinstance(rid, str) and ID.fullmatch(rid) and rid not in seen,
            f'{key} ID 重复或无效：{rid}',
        )
        seen.add(rid)
        require(
            isinstance(row.get('name'), str) and 0 < len(row['name']) <= 200,
            f'{key}/{rid} 缺少名称',
        )
    return rows


def _walk_images(value, root, location=''):
    if isinstance(value, dict):
        for key, item in value.items():
            loc = f'{location}.{key}'
            if key in ('local_path', 'optimized_local_path') and item:
                require(
                    isinstance(item, str) and item.startswith('assets/'), f'{loc} 必须引用本地图片'
                )
            if key == 'icon' and value.get('type') == 'stat':
                from season_rich_text import STAT_PRESENTATION

                require(
                    item is None or item in {v['icon'] for v in STAT_PRESENTATION.values()},
                    '不支持的属性图标',
                )
            elif key in ('image', 'icon', 'splash', 'card') and isinstance(item, str) and item:
                require(item.startswith('assets/'), f'{loc} 必须引用本地图片')
            _walk_images(item, root, loc)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _walk_images(item, root, f'{location}[{i}]')
    elif isinstance(value, str) and value.startswith('assets/'):
        require((root / safe_path(value)).is_file(), f'缺少资源：{location}: {value}')


def _validate_mechanic(mechanic):
    rows = records(mechanic, 'entries')
    presentation = mechanic['presentation']
    for row in rows:
        require(isinstance(row.get('data', {}), dict), '玩法 data 必须是对象')
        if presentation == 'legacy.v1':
            data = row.get('data', {})
            for field in ('rounds', 'requires', 'stages'):
                require(isinstance(data.get(field, []), list), f'玩法 {field} 必须是数组')
            if mechanic['kind'] == 'charm':
                for field in ('rounds', 'requires'):
                    require(
                        all(isinstance(v, str) for v in data.get(field, [])),
                        f'仙灵 {field} 必须是文本数组',
                    )
                require(
                    data.get('category')
                    in {'champion', 'item', 'shop', 'combat', 'gold_xp', 'other'},
                    '仙灵分类无效',
                )
            continue
        data = row.get('data', {})
        for field in ('category', 'category_label'):
            require(data.get(field) is None or isinstance(data[field], str), '玩法分类必须是文本')
        require(
            set(data)
            <= {
                'category',
                'category_label',
                'tags',
                'rounds',
                'requires',
                'variants',
                'stages',
                'columns',
                'rows',
            },
            '通用玩法含不支持字段',
        )
        for key in ('tags', 'rounds', 'requires'):
            require(
                isinstance(data.get(key, []), list)
                and all(isinstance(x, str) for x in data.get(key, [])),
                f'{key} 必须为文本数组',
            )
        for key in ('variants', 'stages'):
            require(
                isinstance(data.get(key, []), list) and len(data.get(key, [])) <= 50, f'{key} 无效'
            )
            for v in data.get(key, []):
                require(
                    isinstance(v, dict) and set(v) <= {'label', 'effect', 'cost', 'requirements'},
                    f'{key} 字段无效',
                )
                require(
                    isinstance(v.get('label'), str) and isinstance(v.get('effect'), str),
                    '阶段/变体需标签和效果',
                )
                require(v.get('cost') is None or type(v['cost']) in (int, float), '费用必须是数字')
                require(
                    isinstance(v.get('requirements', []), list)
                    and all(isinstance(x, str) for x in v.get('requirements', [])),
                    '条件必须为文本数组',
                )
        if presentation == 'table.v1':
            cols, values = data.get('columns'), data.get('rows')
            require(
                isinstance(cols, list)
                and 0 < len(cols) <= 8
                and all(isinstance(x, str) for x in cols),
                '表格列无效',
            )
            require(isinstance(values, list) and len(values) <= 100, '表格行无效')
            require(
                all(
                    isinstance(row, list)
                    and len(row) == len(cols)
                    and all(type(x) in (str, int, float) for x in row)
                    for row in values
                ),
                '表格单元格无效',
            )
    return rows


def validate_data(root, manifest, progress=lambda *args: None):
    """Validate every referenced file and full/compact data consistency offline."""
    validate_manifest(manifest)
    for path, meta in manifest['files'].items():
        file = root / safe_path(path)
        require(
            file.is_file()
            and file.stat().st_size == meta['bytes']
            and sha256(file) == meta['sha256'],
            f'资源完整性失败：{path}',
        )
        if file.suffix.lower() == '.json':
            read_json(file)
    docs = {name: read_json(root / f'data/{name}.json') for name in MODULES}
    index, season = read_json(root / 'data/index.json'), read_json(root / 'data/season.json')
    require(isinstance(index, dict) and isinstance(season, dict), '资料元数据无效')
    for doc in (index, season):
        require(
            doc.get('season_id') == manifest['season_id']
            and doc.get('game_version') == manifest['game_version'],
            '赛季或版本不一致',
        )
    require(isinstance(season.get('display_name'), str) and season['display_name'], '缺少赛季名称')
    require(
        season.get('version_id') == index.get('version_id')
        and isinstance(index.get('version_id'), str),
        'version_id 不一致',
    )
    rows = {name: records(doc, name) for name, doc in docs.items()}
    for name, doc in docs.items():
        require(doc.get('version_id') == index['version_id'], f'{name} 版本不一致')
        if manifest['modules'][name]['state'] == 'absent':
            require(not rows[name], f'{name} 标为不适用但有内容')
    require(rows['champions'] and rows['traits'] and rows['items'], '基础资料不能为空')
    sets = {name: {r['id'] for r in values} for name, values in rows.items()}
    for name in ('champions', 'board_units'):
        for row in rows[name]:
            for key in ('trait_ids', 'contribution_trait_ids'):
                require(
                    isinstance(row.get(key, []), list)
                    and all(x in sets['traits'] for x in row.get(key, [])),
                    f'{name}/{row["id"]} 羁绊引用不存在',
                )
            require(
                isinstance(row.get('skills', []), list)
                and all(isinstance(s, dict) for s in row.get('skills', [])),
                'skills 无效',
            )
            require(isinstance(row.get('stats_by_star', {}), dict), 'stats_by_star 无效')
            if name == 'champions':
                require(type(row.get('cost')) is int and 0 < row['cost'] <= 20, '弈子费用无效')
            for rule in row.get('placement_rules', []):
                require(isinstance(rule, dict), 'placement_rules 无效')
                require(
                    not rule.get('trait_id') or rule['trait_id'] in sets['traits'],
                    '棋盘对象羁绊规则引用不存在',
                )
                require(
                    not rule.get('champion_id') or rule['champion_id'] in sets['champions'],
                    '棋盘对象弈子规则引用不存在',
                )
    require(not sets['champions'] & sets['board_units'], '弈子和棋盘对象 ID 冲突')
    for row in rows['items']:
        recipe = row.get('recipe') or {}
        require(
            isinstance(recipe, dict)
            and all(x in sets['items'] for x in recipe.get('component_ids', [])),
            '装备配方引用不存在',
        )
    from season_package_validation import validate_core

    validate_core(rows)
    codebook_path = root / 'data/tft-codebook.json'
    if codebook_path.is_file():
        codebook = read_json(codebook_path)
        require(isinstance(codebook, dict), '阵容码映射必须是对象')
        for key in ('codes', 'source_ids'):
            mapping = codebook.get(key, {})
            require(isinstance(mapping, dict) and len(mapping) <= 5000, '阵容码映射无效')
            require(
                all(isinstance(v, str) and v in sets['champions'] for v in mapping.values()),
                '阵容码映射的弈子不存在',
            )
    # Reuse production serializers instead of accepting inconsistent page-only payloads.
    from scripts.season_library.import_from_archive import (
        compact_champion,
        compact_trait,
        compact_augment,
    )

    for name, compact in (
        ('champions', compact_champion),
        ('traits', compact_trait),
        ('augments', compact_augment),
    ):
        actual = records(index, name)
        require(
            [x['id'] for x in actual] == [x['id'] for x in rows[name]],
            f'{name} 完整/紧凑资料 ID 不一致',
        )
        for full, small in zip(rows[name], actual):
            expected = compact(full, small.get('card')) if name == 'champions' else compact(full)
            require(small == expected, f'{name}/{full["id"]} 完整/紧凑资料不一致')
    require(isinstance(index.get('mechanics'), list), 'index 缺少玩法数组')
    require(len(index['mechanics']) == len(manifest['mechanics']), '玩法数量不一致')
    for declared, mechanic in zip(manifest['mechanics'], index['mechanics']):
        require(isinstance(mechanic, dict), '玩法无效')
        for key in ('id', 'kind', 'display_name', 'presentation'):
            require(mechanic.get(key) == declared.get(key), f'玩法 {key} 不一致')
        require(mechanic == read_json(root / declared['file']), '玩法文件与 index 不一致')
        _validate_mechanic(mechanic)
    notes, provenance, supplements = (
        read_json(root / f'{name}.json') for name in ('release-notes', 'provenance', 'supplements')
    )
    require(
        isinstance(notes, dict) and isinstance(notes.get('title'), str) and notes['title'],
        '更新说明缺少标题',
    )
    require(
        isinstance(notes.get('summary', ''), str) and isinstance(notes.get('sections', []), list),
        '更新说明格式错误',
    )
    for section in notes.get('sections', []):
        require(
            isinstance(section, dict)
            and isinstance(section.get('title'), str)
            and isinstance(section.get('items'), list)
            and all(isinstance(x, str) for x in section['items']),
            '更新说明分类无效',
        )
    require(
        isinstance(provenance, dict) and isinstance(provenance.get('sources'), list), '来源清单无效'
    )
    require(
        isinstance(supplements, dict) and isinstance(supplements.get('entries'), list),
        '补充清单无效',
    )
    source_ids = set()
    for source in provenance['sources']:
        require(
            isinstance(source, dict)
            and isinstance(source.get('id'), str)
            and source['id'] not in source_ids,
            '来源 ID 无效',
        )
        source_ids.add(source['id'])
    seen_supplements = set()
    mechanics = {x['id']: {r['id']: r for r in x['entries']} for x in index['mechanics']}
    warnings = []
    for s in supplements['entries']:
        require(isinstance(s, dict), '补充记录无效')
        identity = (s.get('mechanic_id'), s.get('record_id'), s.get('field'))
        require(
            all(isinstance(x, str) for x in identity) and identity not in seen_supplements,
            '补充记录重复或无效',
        )
        seen_supplements.add(identity)
        require(s.get('source_id') in source_ids, '补充来源不存在')
        require(s.get('verification') in ('verified', 'inherited_unverified'), '补充核验状态无效')
        record = mechanics.get(identity[0], {}).get(identity[1])
        require(
            record is not None and identity[2] in ('rounds', 'requires'), '补充字段或对象不存在'
        )
        require(s.get('value') == record.get('data', {}).get(identity[2]), '补充值与页面不一致')
    for mid, entries in mechanics.items():
        for rid, record in entries.items():
            for field in ('rounds', 'requires'):
                require(
                    not record.get('data', {}).get(field) or (mid, rid, field) in seen_supplements,
                    '玩法回合/条件缺少来源与核验记录',
                )
    inherited = sum(x['verification'] == 'inherited_unverified' for x in supplements['entries'])
    if inherited:
        warnings.append(f'{inherited} 个补充字段沿用历史资料，尚未核验当前补丁')
    for doc in [index, *docs.values()]:
        _walk_images(doc, root)
    images = (
        [p for p in (root / 'assets').rglob('*') if p.is_file()]
        if (root / 'assets').is_dir()
        else []
    )
    for i, path in enumerate(images):
        try:
            with Image.open(path) as im:
                require(
                    im.width * im.height <= 24_000_000 and im.format in ('PNG', 'JPEG', 'WEBP'),
                    f'图片格式/像素超限：{path.name}',
                )
                require(getattr(im, 'n_frames', 1) == 1, '不允许动画图片')
                im.verify()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise PackageError(f'图片损坏：{path.name}') from exc
        progress('images', 45 + int(45 * (i + 1) / max(1, len(images))), path.name)
    counts = {name: len(value) for name, value in rows.items()}
    counts['mechanics'] = sum(len(x['entries']) for x in index['mechanics'])
    require(season.get('counts') == counts, '数量声明与实际内容不一致')
    return {
        'counts': counts,
        'warnings': warnings,
        'notes': notes,
        'sources': provenance['sources'],
        'supplement_count': len(supplements['entries']),
        'inherited_count': inherited,
        'images': len(images),
    }


@lru_cache(maxsize=12)
def _asset_hashes(directory):
    # Called only on immutable releases and the code-deployed baseline.
    root = Path(directory)
    return {p.relative_to(root).as_posix(): sha256(p) for p in root.rglob('*') if p.is_file()}


def structural_diff(old_root, new_root):
    result = {}

    def clean(value):
        if isinstance(value, dict):
            return {
                k: clean(v)
                for k, v in value.items()
                if k
                not in ('version_id', 'optimized_local_path', 'description_tokens', 'effect_tokens')
            }
        if isinstance(value, list):
            return [clean(x) for x in value]
        return value

    for name in MODULES:
        old = (
            read_json(old_root / f'{name}.json')
            if (old_root / f'{name}.json').is_file()
            else {name: []}
        )
        new = read_json(new_root / f'{name}.json')
        a, b = ({r['id']: r for r in d[name]} for d in (old, new))
        changed = []
        for key in a.keys() & b.keys():
            fields = sorted(
                k
                for k in a[key].keys() | b[key].keys()
                if clean(a[key].get(k)) != clean(b[key].get(k))
                and k not in ('version_id', 'description_tokens')
            )
            if fields:
                changed.append({'id': key, 'name': b[key]['name'], 'fields': fields})
        result[name] = {
            'added': [{'id': k, 'name': b[k]['name']} for k in sorted(b.keys() - a.keys())],
            'removed': [{'id': k, 'name': a[k]['name']} for k in sorted(a.keys() - b.keys())],
            'changed': sorted(changed, key=lambda r: r['id']),
        }
    old_index, new_index = read_json(old_root / 'index.json'), read_json(new_root / 'index.json')
    a, b = ({m['id']: m for m in d.get('mechanics', [])} for d in (old_index, new_index))
    result['mechanics'] = {
        'added': sorted(b.keys() - a.keys()),
        'removed': sorted(a.keys() - b.keys()),
        'changed': sorted(k for k in a.keys() & b.keys() if clean(a[k]) != clean(b[k])),
    }
    old_assets = (
        old_root / 'assets' if (old_root / 'assets').is_dir() else old_root.parent / 'assets'
    )
    new_assets = (
        new_root / 'assets' if (new_root / 'assets').is_dir() else new_root.parent / 'assets'
    )
    a, b = _asset_hashes(str(old_assets)), _asset_hashes(str(new_assets))
    result['assets'] = {
        'added': sorted(b.keys() - a.keys()),
        'removed': sorted(a.keys() - b.keys()),
        'changed': sorted(k for k in a.keys() & b.keys() if a[k] != b[k]),
    }
    return result
