"""Build the self-contained time-card catalog from a downloaded official snapshot."""
import argparse
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def build(source, output):
    source, output = Path(source), Path(output)
    payload = json.loads((source / 'card.js').read_text(encoding='utf-8-sig'))
    assets = {}
    (output / 'images').mkdir(parents=True, exist_ok=True)
    for key, card in payload['data'].items():
        if not key.isdigit() or card['id'] != key or card['iRarityTier'] not in ('1', '2', '3', '4', '5'):
            raise ValueError(f'Invalid card identity: {key}')
        # Local filenames use card IDs, whereas official icon IDs can differ.
        matches = list((source / f"{card['iRarityTier']}星").glob(f'{key}_*.png'))
        if len(matches) > 1:
            raise ValueError(f'Ambiguous image: {key}')
        if not matches:
            assets[key] = None
            continue
        with Image.open(matches[0]) as image:
            width, height = image.size
        filename = f'images/{key}.png'
        shutil.copyfile(matches[0], output / filename)
        assets[key] = {'file': filename, 'width': width, 'height': height,
                       'layout': 'icon' if height / width < 1.4 else 'portrait'}
    payload['assets'] = assets
    (output / 'cards.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return len(payload['data']), sum(asset is not None for asset in assets.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'static/tools/orange-fortune')
    options = parser.parse_args()
    cards, images = build(options.source, options.output)
    print(f'Built {cards} cards / {images} images')
