"""Extract golden egg rewards and embedded assets without executing HAR scripts."""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ICONS = {'光明武器': 'gmwq', '英雄复制器': 'yxfzq', '5费卡': '5costunit',
         '装备拆卸器': 'chaixie', '神器': 'shenqi', '成装': 'cz'}


def extract(har):
    entries = har['log']['entries']
    matches = []
    for entry in entries:
        content = entry['response'].get('content', {})
        text = content.get('text', '')
        if content.get('encoding') == 'base64' and 'javascript' in content.get('mimeType', ''):
            text = base64.b64decode(text, validate=True).decode('utf-8')
        match = re.search(r'金蛋:(\[.*?\]),寻宝:', text)
        if match:
            matches.append(json.loads(re.sub(r'([{,])([A-Za-z][A-Za-z0-9]*):', r'\1"\2":', match[1])))
    if len(matches) != 1:
        raise ValueError('Expected exactly one golden egg table')
    outcomes = matches[0][0]['list']
    if not outcomes or sum(float(row['percent'].rstrip('%')) for row in outcomes) != 100:
        raise ValueError('Reward probabilities must total 100%')
    captured = {urlsplit(e['request']['url']).path: e['response'].get('content', {})
                for e in entries if urlsplit(e['request']['url']).hostname == 'static.datatft.com'}
    images = {}

    def asset(path):
        content = captured.get(path, {})
        if content.get('encoding') != 'base64' or not content.get('text'):
            raise ValueError(f'Missing embedded image: {path}')
        filename = path.removeprefix('/images/').replace('/', '-')
        images[filename] = base64.b64decode(content['text'], validate=True)
        return f'golden-egg/images/{filename}'

    augment = asset('/images/hex2/TheGoldenEgg_3_.png')
    for row in outcomes:
        combined = {}
        for reward in row['rewards']:
            gold = re.fullmatch(r'(\d+)金币', reward['title'])
            path = (f"/images/equips/{reward['equipId']}.png" if 'equipId' in reward else
                    f"/images/reward/{'gold' if gold else ICONS[reward['title']]}.png")
            reward['image'] = asset(path)
            reward['count'] = int(gold[1]) if gold else int(reward.get('count', 1))
            if reward['count'] < 1:
                raise ValueError('Reward count must be positive')
            if gold:
                reward['title'] = '金币'
            key = (reward['title'], reward['image'])
            if key in combined:
                combined[key]['count'] += reward['count']
            else:
                combined[key] = reward
        row['rewards'] = list(combined.values())
    return {'augment_image': augment, 'outcomes': outcomes}, images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('har', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] / 'static/golden-egg')
    args = parser.parse_args()
    raw = args.har.read_bytes()
    payload, images = extract(json.loads(raw.decode('utf-8-sig')))
    payload.update(source='datatft.com', source_sha256=hashlib.sha256(raw).hexdigest(), patch=None)
    (args.output / 'images').mkdir(parents=True, exist_ok=True)
    for name, data in images.items():
        (args.output / 'images' / name).write_bytes(data)
    (args.output / 'rewards.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(payload["outcomes"])} outcomes, {len(images)} images')


if __name__ == '__main__':
    main()
