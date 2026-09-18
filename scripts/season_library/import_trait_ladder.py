"""Extract only the reward literal from a user-supplied HAR, without executing JS."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def extract(raw):
    tables = []
    for entry in json.loads(raw)['log']['entries']:
        content = entry['response'].get('content', {})
        text = content.get('text', '')
        if content.get('encoding') == 'base64':
            continue
        match = re.search(r'羁绊天梯:(\[.*?\]),幻灵战队jcc:', text)
        if match:
            literal = re.sub(r'([{,])([A-Za-z][A-Za-z0-9]*):', r'\1"\2":', match[1])
            tables.append(json.loads(literal))
    if len(tables) != 1:
        raise ValueError('Expected exactly one trait ladder reward table')
    tiers = tables[0]
    for tier in tiers:
        tier['threshold'] = int(tier['label'].split()[0])
        for outcome in tier['list']:
            for reward in outcome['rewards']:
                reward.setdefault('count', 1)
    return {'source': 'datatft.com · user supplied HAR',
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'captured_date': '2026-09-18', 'patch': None, 'tiers': tiers}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('har', type=Path)
    parser.add_argument('--output', type=Path, default=Path('static/trait-ladder/rewards.json'))
    args = parser.parse_args()
    payload = extract(args.har.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Extracted {len(payload['tiers'])} reward tiers")
