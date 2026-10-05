"""Freeze the illustrated S11 guide and its images from a specified archive version.

python scripts/season_library/import_s11_artifacts.py --source PATH_TO_18.11.1
Only writes static/s11-artifacts; no season release or database is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).parent / 'sources' / 's11-artifacts.json'

ALIASES = {
    '孙悟空': ['猴子', '悟空'], '李青': ['盲僧', '瞎子'],
    '阿兹尔': ['沙皇'], '艾瑞莉娅': ['刀妹'], '沃利贝尔': ['狗熊', '熊'],
    '诺提勒斯': ['泰坦'], '卡莎': ['卡萨'], '崔丝塔娜': ['小炮'],
    '厄斐琉斯': ['月男'], '丽桑卓': ['冰女'], '瑟提': ['腕豪'],
    '亚托克斯': ['剑魔'], '约里克': ['掘墓'], '彗': ['慧', '画家'],
}


def build(source):
    source = source.resolve()
    guide = json.loads(SOURCE.read_text(encoding='utf-8'))
    version = json.loads((source / 'version.json').read_text(encoding='utf-8'))
    if version.get('season_id') != 's11' or version.get('game_version') != guide['version']:
        raise ValueError('This guide requires the S11 18.11.1 archive')
    # The archive also has a completed item named 斯塔缇克电刃; resolve
    # the illustrated artifact, rather than allowing a same-name overwrite.
    items = {row['name']: row for row in json.loads((source / 'items.json').read_text(encoding='utf-8'))['items']
             if row['category'] == 'artifact' or row['id'] == '6091'}
    champions = {row['name']: row for row in json.loads((source / 'champions.json').read_text(encoding='utf-8'))['champions']}
    output = ROOT / 'static' / 's11-artifacts'
    snapshot = {'season': guide['season'], 'version': guide['version'], 'champions': {}, 'artifacts': []}
    assets = {}

    def image(local_path, kind, identity):
        original = (source / local_path).resolve()
        if not original.is_relative_to(source):
            raise ValueError('Image path escapes the source archive')
        target = f'{kind}/{identity}{original.suffix.lower()}'
        assets[target] = original
        return 's11-artifacts/' + target

    if len(guide['artifacts']) != 31 or len({row['name'] for row in guide['artifacts']}) != 31:
        raise ValueError('The five reference sheets must contain 31 distinct artifacts')
    for row in guide['artifacts']:
        item = items[row['name']]
        champion_ids = []
        if len(row['champions']) != 4:
            raise ValueError(f"Expected four illustrated recommendations: {row['name']}")
        for name, cost in row['champions']:
            champion = champions[name]
            if champion['cost'] != cost:
                raise ValueError(f'Cost mismatch for {name}')
            champion_ids.append(champion['id'])
            snapshot['champions'][champion['id']] = {
                'id': champion['id'], 'name': name, 'cost': cost,
                'aliases': ALIASES.get(name, []),
                'image': image(champion['images']['icon']['local_path'], 'champions', champion['id']),
            }
        snapshot['artifacts'].append({
            'id': item['id'], 'name': row['name'], 'description': row['description'],
            'image': image(item['image']['local_path'], 'items', item['id']),
            'champion_ids': champion_ids,
        })

    # Validate every asset before writing anything; preserve the source bytes.
    hashes = {target: hashlib.sha256(original.read_bytes()).hexdigest() for target, original in assets.items()}
    for target, original in assets.items():
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
    (output / 'data.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    provenance = {
        'version': guide['version'], 'reference': guide['reference'],
        # Normalize text newlines so a Git checkout on Windows or Linux keeps
        # the same guide fingerprint; asset and archive hashes remain bytewise.
        'guide_sha256': hashlib.sha256(SOURCE.read_text(encoding='utf-8').encode('utf-8')).hexdigest(),
        'archive_sha256': {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in ('items.json', 'champions.json')},
        'asset_sha256': hashes,
    }
    (output / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return snapshot


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    data = build(args.source)
    print(f"Frozen {len(data['artifacts'])} artifacts and {len(data['champions'])} champion portraits.")
