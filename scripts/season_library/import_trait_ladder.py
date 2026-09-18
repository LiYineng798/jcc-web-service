"""Extract only the reward literal from a user-supplied HAR, without executing JS."""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


ICONS = {'装备重铸器': 'chongzhu', '散件': 'sanjian', '3费卡': '3costunit',
         '4费卡': '4costunit', '5费卡': '5costunit', '成装锻造器': 'czdzq',
         '装备拆卸器': 'chaixie', '杰作升级': 'jzsj'}


def image_path(reward):
    if 'equipId' in reward:
        return f"/images/equips/{reward['equipId']}.png"
    key = 'gold' if re.fullmatch(r'\d+金币', reward['title']) else ICONS[reward['title']]
    return f'/images/reward/{key}.png'


def extract_images(raw, payload):
    captured = {urlsplit(e['request']['url']).path: e['response'].get('content', {})
                for e in json.loads(raw)['log']['entries']
                if urlsplit(e['request']['url']).hostname == 'static.datatft.com'}
    images = {}
    for tier in payload['tiers']:
        for outcome in tier['list']:
            for reward in outcome['rewards']:
                path = image_path(reward)
                content = captured.get(path, {})
                if content.get('encoding') != 'base64' or not content.get('text'):
                    raise ValueError(f'Missing embedded reward image: {path}')
                images[Path(reward['image']).name] = base64.b64decode(content['text'], validate=True)
    return images


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
                gold = re.fullmatch(r'(\d+)金币', reward['title'])
                reward['display_count'] = int(gold[1]) * reward['count'] if gold else reward['count']
                reward['image'] = 'trait-ladder/images/' + image_path(reward).removeprefix('/images/').replace('/', '-')
    return {'source': 'datatft.com · user supplied HAR',
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'captured_date': '2026-09-18', 'patch': None, 'tiers': tiers}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('har', type=Path)
    parser.add_argument('--output', type=Path, default=Path('static/trait-ladder/rewards.json'))
    args = parser.parse_args()
    raw = args.har.read_bytes()
    payload = extract(raw)
    images = extract_images(raw, payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image_dir = args.output.parent / 'images'
    image_dir.mkdir(exist_ok=True)
    for filename, content in images.items():
        (image_dir / filename).write_bytes(content)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Extracted {len(payload['tiers'])} reward tiers and {len(images)} images")
