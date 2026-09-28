"""Freeze the curated S11 guide and its assets; the archive is only a build input."""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('s11_recommendations.tsv')
PREFIX = 'tools/s11-items'


def build(archive, output):
    archive = Path(archive)
    version = json.loads((archive / 'version.json').read_text(encoding='utf-8'))
    if version['version_id'] != 's11__12_4_14':
        raise ValueError('This guide requires the fixed S11 12.4.14 archive')
    def read(name, key):
        return json.loads((archive / name).read_text(encoding='utf-8'))[key]

    champions = {c['name']: c for c in read('champions.json', 'champions')}
    items = {i['name']: i for i in read('items.json', 'items') if i['category'] == 'completed'}
    by_id = {i['id']: i for i in read('items.json', 'items')}
    traits = {t['id']: t['name'] for t in read('traits.json', 'traits')}
    copies = {}

    def asset(relative):
        source = (archive / relative).resolve()
        if not source.is_relative_to(archive.resolve()) or not source.is_file():
            raise ValueError(f'Missing or invalid asset: {relative}')
        copies[relative] = source
        return f'{PREFIX}/{relative}'

    selected_items = {}
    def equipment(name):
        item = items[name]
        if item['id'] not in selected_items:
            components = [by_id[i] for i in item['recipe']['component_ids']]
            if len(components) != 2 or any(i['category'] != 'component' for i in components):
                raise ValueError(f'Invalid recipe: {name}')
            selected_items[item['id']] = {
                'name': name, 'image': asset(item['image']['local_path']),
                'components': [{'name': c['name'], 'image': asset(c['image']['local_path'])} for c in components],
            }
        return item['id']

    rows = []
    with SOURCE.open(encoding='utf-8', newline='') as source:
        for cost, name, recommended, alternative in csv.reader(source, delimiter='\t'):
            champion = champions[name]
            recommendations = recommended.split(',')
            if champion['cost'] != int(cost) or len(recommendations) != 3:
                raise ValueError(f'Invalid recommendation: {name}')
            rows.append({
                'id': champion['id'], 'name': name, 'cost': int(cost),
                'traits': [traits[t] for t in champion['trait_ids']],
                'image': asset(champion['images']['icon']['local_path']),
                'recommended': [equipment(n) for n in recommendations],
                'alternative': equipment(alternative),
            })
    if len(rows) != 60 or len({r['id'] for r in rows}) != 60:
        raise ValueError('Expected 60 distinct curated champions')
    payload = {'season': 's11', 'version': '12.4.14', 'champions': rows, 'items': selected_items}
    # Validate every reference before writing; never edit the external archive.
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for relative, source in copies.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (output / 'data.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest = {path: hashlib.sha256(source.read_bytes()).hexdigest() for path, source in sorted(copies.items())}
    (output / 'asset-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path, help='S11 versions/12.4.14 directory')
    parser.add_argument('--output', type=Path, default=ROOT / 'static' / PREFIX)
    args = parser.parse_args()
    result = build(args.archive, args.output)
    print(f"Generated {len(result['champions'])} champions and {len(result['items'])} equipment recipes")
