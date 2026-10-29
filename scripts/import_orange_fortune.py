"""Build the self-contained time-card catalog from an archive made by collect_orange_fortune.py."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def build(source, output):
    source, output = Path(source), Path(output)
    selection = json.loads((source / 'selection.json').read_text(encoding='utf-8'))
    card_path = selection['selected']['cardurl']
    payload = json.loads((source / f"parsed{card_path.rsplit('.', 1)[0]}.json").read_text(encoding='utf-8'))
    endpoint = json.loads((source / 'endpoints/cardurl.json').read_text(encoding='utf-8'))
    downloads = json.loads((source / 'images/manifest.json').read_text(encoding='utf-8'))
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    assets, failures = {}, {}
    (output / 'images').mkdir(parents=True, exist_ok=True)
    for key, card in payload['data'].items():
        if not key.isdigit() or card['id'] != key or card['iRarityTier'] not in ('1', '2', '3', '4', '5'):
            raise ValueError(f'Invalid card identity: {key}')
        record = downloads.get(key) or {'error': 'not_downloaded'}
        # A failed download stays missing; earlier art is never reused as this run's result.
        if record.get('error') or record.get('url') != card['sIcon']:
            assets[key] = None
            failures[key] = {'url': card['sIcon'], 'error': record.get('error') or 'url_mismatch',
                             'status': record.get('status'), 'checked_at': record.get('downloaded_at')}
            continue
        data = (source / record['local_path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError(f'Archive image changed after download: {key}')
        with Image.open(source / record['local_path']) as image:
            width, height = image.size
        # Local filenames use card IDs, whereas official icon IDs can differ.
        filename = f'images/{key}.png'
        if record['format'] != 'PNG':
            raise ValueError(f'Unexpected image format for {key}: {record["format"]}')
        (output / filename).write_bytes(data)
        assets[key] = {'file': filename, 'width': width, 'height': height, 'sha256': record['sha256'],
                       'layout': 'icon' if height / width < 1.4 else 'portrait'}
    for stale in (output / 'images').glob('*.png'):
        if assets.get(stale.stem) is None:
            stale.unlink()
    payload['assets'] = assets
    payload['asset_failures'] = failures
    payload['provenance'] = {
        'collected_at': manifest['collected_at'], 'card_url': endpoint['url'],
        'etag': endpoint.get('etag'), 'last_modified': endpoint.get('last_modified'),
        'archive': source.name,
    }
    (output / 'cards.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return len(payload['data']), sum(asset is not None for asset in assets.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'static/tools/orange-fortune')
    options = parser.parse_args()
    cards, images = build(options.source, options.output)
    print(f'Built {cards} cards / {images} images')
