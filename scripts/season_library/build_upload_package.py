"""Build a self-contained upload ZIP from already prepared local season data. Offline."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from season_package_format import (
    MODULES,
    FORMAT,
    SCHEMA,
    dump,
    read_json,
    sha256,
    require,
    validate_data,
    inspect_zip,
    PackageError,
)


def build_package(source, output, revision, notes, package_id=None, provenance=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    require(source.is_dir(), '本地资料目录不存在')
    require(not any(p.is_symlink() for p in source.rglob('*')), '本地资料不能包含符号链接')
    index = read_json(source / 'index.json')
    sid, version = index['season_id'], index['game_version']
    package_id = package_id or f'{sid}-{version.replace(".","_").lower()}-r{revision}'
    require(not output.exists(), '输出包已存在，请使用新修订号或新文件名')
    with tempfile.TemporaryDirectory(prefix='jcc-package-') as temp:
        root = Path(temp)
        data = root / 'data'
        data.mkdir()
        shutil.copytree(source / 'assets', root / 'assets')
        counts, modules = {}, {}
        for name in MODULES:
            path = source / f'{name}.json'
            doc = (
                read_json(path) if path.is_file() else {'version_id': index['version_id'], name: []}
            )
            dump(data / f'{name}.json', doc)
            counts[name] = len(doc[name])
            modules[name] = {
                'state': 'present' if doc[name] else 'absent',
                'file': f'data/{name}.json',
            }
        if (source / 'tft-codebook.json').is_file():
            shutil.copy2(source / 'tft-codebook.json', data / 'tft-codebook.json')
        mechanics, supplements = [], []
        sources = list((provenance or {}).get('sources', []))
        for mechanic in index.get('mechanics', []):
            mechanic.setdefault(
                'presentation',
                (
                    'legacy.v1'
                    if mechanic.get('kind') in ('charm', 'wand', 'god', 'monster', 'none')
                    else 'cards.v1'
                ),
            )
            entry = {k: mechanic[k] for k in ('id', 'kind', 'display_name', 'presentation')}
            entry.update(file=f'data/mechanics/{mechanic["id"]}.json', targets=['reference'])
            mechanics.append(entry)
            dump(root / entry['file'], mechanic)
            for row in mechanic['entries']:
                provenance = row.get('extensions', {}).get('provenance')
                values = row.get('data', {})
                if not provenance and not (values.get('rounds') or values.get('requires')):
                    continue
                provenance = provenance or {
                    'note': '本地资料补充，尚未核验',
                    'source_type': 'local',
                }
                source_id = f'{mechanic["id"]}-{row["id"]}'
                sources.append({'id': source_id, **provenance})
                for field in ('rounds', 'requires'):
                    if values.get(field):
                        supplements.append(
                            {
                                'mechanic_id': mechanic['id'],
                                'record_id': row['id'],
                                'field': field,
                                'value': values[field],
                                'source_id': source_id,
                                'inherited_from_version': provenance.get('inherited_from_version'),
                                'verification': (
                                    'verified'
                                    if provenance.get('verified_for_current_patch') is True
                                    else 'inherited_unverified'
                                ),
                            }
                        )
        counts['mechanics'] = sum(len(m['entries']) for m in index.get('mechanics', []))
        dump(data / 'index.json', index)
        dump(
            data / 'season.json',
            {
                k: index.get(k)
                for k in (
                    'season_id',
                    'display_name',
                    'set_number',
                    'set_variant',
                    'theme',
                    'status',
                    'game_version',
                    'version_id',
                    'effective_at',
                )
            }
            | {'counts': counts},
        )
        dump(root / 'release-notes.json', notes)
        # Source URLs are provenance only; never followed during packaging/upload.
        sources.append(
            {
                'id': 'prepared-local-data',
                'type': 'local_snapshot',
                'note': '由已处理的本地资料生成；数据真实性不由哈希证明',
            }
        )
        dump(root / 'provenance.json', {'sources': sources})
        dump(root / 'supplements.json', {'entries': supplements})
        manifest = {
            'package_format': FORMAT,
            'package_schema_version': SCHEMA,
            'dataset_schema_version': SCHEMA,
            'package_id': package_id,
            'season_id': sid,
            'game_version': version,
            'data_revision': revision,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'effective_at': index.get('effective_at'),
            'builder': {'name': 'jcc-season-pack', 'version': '1.0.0'},
            'required_capabilities': sorted(
                {'simulator.placement_rules.v1', 'reference.cards.v1'}
                | {
                    f'reference.{m["presentation"]}'
                    for m in mechanics
                    if m['presentation'] != 'legacy.v1'
                }
            ),
            'modules': modules,
            'mechanics': mechanics,
            'files': {},
        }
        for path in sorted(root.rglob('*')):
            if path.is_file():
                manifest['files'][path.relative_to(root).as_posix()] = {
                    'bytes': path.stat().st_size,
                    'sha256': sha256(path),
                }
        dump(root / 'manifest.json', manifest)
        report = validate_data(root, manifest)
        output.parent.mkdir(parents=True, exist_ok=True)
        # ZIP is finalized in the output filesystem then renamed; no half ZIP at the requested path.
        temp_output = output.with_suffix(output.suffix + '.building')
        try:
            with zipfile.ZipFile(
                temp_output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as z:
                for path in sorted(root.rglob('*')):
                    if path.is_file():
                        z.write(path, path.relative_to(root).as_posix())
            inspect_zip(temp_output)
            temp_output.replace(output)
        finally:
            temp_output.unlink(missing_ok=True)
        return manifest, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', required=True)
    parser.add_argument(
        '--source', type=Path, help='已经完成处理的赛季目录，默认 static/season-data/<season>'
    )
    parser.add_argument('--revision', type=int, required=True)
    parser.add_argument(
        '--notes', type=Path, required=True, help='包含 title、summary、sections 的 UTF-8 JSON'
    )
    parser.add_argument(
        '--provenance', type=Path, help='可选来源 JSON，格式为 sources 数组，随包归档但不访问 URL'
    )
    parser.add_argument('--output', type=Path, required=True, help='目标 ZIP 文件')
    args = parser.parse_args()
    source = args.source or ROOT / 'static/season-data' / args.season
    require(read_json(source / 'index.json')['season_id'] == args.season, '赛季选择与资料不一致')
    manifest, report = build_package(
        source,
        args.output,
        args.revision,
        read_json(args.notes),
        provenance=read_json(args.provenance) if args.provenance else None,
    )
    print(
        json.dumps(
            {'package': str(args.output), 'id': manifest['package_id'], **report},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    try:
        main()
    except (PackageError, OSError) as error:
        print(f'打包失败：{error}', file=sys.stderr)
        sys.exit(2)
