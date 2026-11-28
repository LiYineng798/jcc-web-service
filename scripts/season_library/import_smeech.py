"""Build the standalone S19 tool snapshot from a DataTFT tracker HAR, offline."""
import argparse
import json
from io import BytesIO
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.season_library.import_datatft_har import decode_har, response_bytes, trait_symbols


def build(har, target):
    data, entries, scripts, _ = decode_har(har)
    images = {
        urlsplit(e['request']['url']).path: e for e in entries
        if urlsplit(e['request']['url']).hostname == 'static.datatft.com'
        and e['response']['content'].get('text')
    }

    def image(source, folder, identifier):
        entry = images.get(source)
        if not entry:
            raise ValueError(f'缺少静态素材 {source}')
        directory = target / folder
        directory.mkdir(parents=True, exist_ok=True)
        with Image.open(BytesIO(response_bytes(entry))) as original:
            original.thumbnail((96, 96))
            original.save(directory / f'{identifier}.webp', quality=86)

    traits = []
    symbol_ids = {}
    for category, records in [('race', data['races19']), ('job', data['jobs19'])]:
        for row in records:
            levels = row.get('level2') or row['level']
            if not levels or (len(levels) == 1 and levels[0]['level'] <= 1):
                continue
            threshold = levels[0]['level']
            if row['key'] == 'DA_KDA19':
                threshold = (threshold + 1) // 2  # The reference assumes two-star K/DA units.
            trait_id = f"{category}_{int(row[category + 'Id'])}"
            symbol_ids[row['key']] = trait_id
            traits.append(dict(id=trait_id, name=row['name'], threshold=threshold))
    by_id = {t['id']: t for t in traits}
    for item in data['equips19']:
        trait = by_id.get(item.get('traitId'))
        if trait and str(item.get('type2', '')).startswith('zhuanzhi'):
            identifier = int(item['equipId'])
            image(f'/images/equips/{identifier}.png', 'emblems', identifier)
            trait['emblem'] = identifier

    heroes = []
    for row in data['heros19']:
        identifier = int(row['chessId'])
        if identifier == 919958:
            continue
        name = row['displayName']
        if identifier in (919952, 919953):
            name += f"（{row['races'][0]}）"
        # Use a unit's base traits. Guest bands listed under Sona in trait rosters
        # are selectable alternatives and cannot all be active at the same time.
        ids = [f'{kind}_{value}' for kind in ('race', 'job')
               for value in re.findall(r'\d+', str(row.get(kind + 'Ids') or ''))]
        heroes.append(dict(id=identifier, name=name, cost=int(row['price']),
                           traits=[key for key in ids if key in by_id], slots=2 if identifier == 919981 else 1,
                           unlock=bool(row.get('unlockLevel') or row.get('unlockDesc'))))
        image(f'/images/heros/default/{identifier}.jpg', 'heroes', identifier)
    # The target is absent from its own picker. Reuse its bundled season portrait.
    target_icon = ROOT / 'static/season-data/s19/assets/optimized/s19__pbe/champions/919958.webp'
    shutil.copyfile(target_icon, target / 'smeech.webp')
    sprite = ET.Element('svg', xmlns='http://www.w3.org/2000/svg')
    for key, view_box, paths in trait_symbols(scripts, symbol_ids):
        identifier = symbol_ids.pop(key)
        symbol = ET.SubElement(sprite, 'symbol', id=identifier, viewBox=view_box)
        for path in paths:
            ET.SubElement(symbol, 'path', d=path)
    if symbol_ids:
        raise ValueError(f"缺少羁绊图标 {', '.join(symbol_ids)}")
    ET.indent(sprite)
    (target / 'traits.svg').write_bytes(ET.tostring(sprite, encoding='utf-8') + b'\n')

    heroes.sort(key=lambda h: (h['cost'], h['id']))
    (target / 'catalog.json').write_text(json.dumps(dict(heroes=heroes, traits=traits),
                                                    ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('har', type=Path)
    args = parser.parse_args()
    build(args.har, ROOT / 'static' / 'smeech')
