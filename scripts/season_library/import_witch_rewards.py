"""Extract the public witch reward snapshot and embedded images from a HAR.

Only a JSON-like literal is parsed; captured JavaScript is never executed.
The HAR itself (which may contain credentials) must not be committed.
"""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


ICONS = {
    '2费卡': '2costunit', '5费卡': '5costunit', '散件': 'sanjian',
    '成装': 'cz', '成装锻造器': 'czdzq', '装备重铸器': 'chongzhu',
    '基础装备锻造器': 'jczbdzq', '神器锻造器': 'sqdzq', '光明武器': 'gmwq',
    '装备拆卸器': 'chaixie', '随机纹章': 'emblem',
    '金制装备拆卸器': 'chaixiegold', '英雄复制器': 'yxfzq',
}


def extract(har):
    entries = har['log']['entries']
    literals = []
    for entry in entries:
        text = entry['response'].get('content', {}).get('text', '')
        match = re.search(r'魔女:(\[.*?\]),"6幻灵战队jcc"', text)
        if match:
            # Quote only bare object keys; json.loads rejects executable code.
            literal = re.sub(r'([{,])([A-Za-z][A-Za-z0-9]*):', r'\1"\2":', match[1])
            literals.append(json.loads(literal))
    if len(literals) != 1:
        raise ValueError('Expected exactly one witch reward table')
    tiers = literals[0]
    images = {}
    captured = {urlsplit(e['request']['url']).path: e['response'].get('content', {})
                for e in entries if urlsplit(e['request']['url']).hostname == 'static.datatft.com'}
    for tier in tiers:
        for row in tier['list']:
            for reward in row['rewards']:
                if 'heroId' in reward:
                    path = f"/images/heros/default/{reward['heroId']}.jpg"
                elif 'equipId' in reward:
                    path = f"/images/equips/{reward['equipId']}.png"
                else:
                    key = 'gold' if re.fullmatch(r'\d+金币', reward['title']) else ICONS[reward['title']]
                    path = f'/images/reward/{key}.png'
                content = captured.get(path, {})
                if content.get('encoding') != 'base64' or not content.get('text'):
                    raise ValueError(f'Missing embedded image: {path}')
                filename = path.removeprefix('/images/').replace('/', '-')
                images[filename] = base64.b64decode(content['text'], validate=True)
                reward['image'] = f'witch-rewards/images/{filename}'
                reward['count'] = reward.get('count', 1)
                reward['tier'] = reward.get('tier', 1 if 'heroId' in reward else 0)
    return tiers, images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('har', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] / 'static/witch-rewards')
    args = parser.parse_args()
    raw = args.har.read_bytes()
    tiers, images = extract(json.loads(raw.decode('utf-8-sig')))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'images').mkdir(exist_ok=True)
    for filename, data in images.items():
        (args.output / 'images' / filename).write_bytes(data)
    payload = {'season': 's18', 'source': 'datatft.com', 'source_sha256': hashlib.sha256(raw).hexdigest(),
               'patch': None, 'tiers': tiers}
    (args.output / 'rewards.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(tiers)} tiers, {sum(len(t["list"]) for t in tiers)} outcomes, {len(images)} images')


if __name__ == '__main__':
    main()
