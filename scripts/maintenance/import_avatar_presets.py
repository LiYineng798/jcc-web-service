"""Extract selected Avatar Lab shapes and add two compact local designs."""
import argparse
import copy
import json
import math
from pathlib import Path


VIEWPORTS = {
    'strobi': [-165, -165, 330, 330],
    'freddy': [-150, -169, 300, 300],
    'citrus': [-170, -150, 340, 340],
    'nova': [-175, -175, 350, 350],
    'sunee': [-190, -201, 390, 390],
    'cloudee': [-135, -134, 270, 270],
    'sprout': [-145, -155, 290, 290],
    'bloom': [-150, -150, 300, 300],
}


def compatible_surface(surface):
    result = dict(surface)
    # Runtime 0.1.0 validates roundness in [0, 1]; newer studio exports can exceed it.
    for key in ('roundness', 'morphRoundness', 'tipRoundness', 'baseRoundness'):
        if key in result:
            result[key] = max(0, min(1, result[key]))
    return result


def sphere(width, height, depth):
    return {'type': 'sphere', 'width': width, 'height': height, 'depth': depth, 'roundness': 1}


def node(surface, x, y, z=-24, angle=0):
    return {'surface': surface, 'position': [x, y, z], 'rotation': [0, 0, angle]}


def local_presets(eyes):
    eyes = {**eyes, 'widthLeft': 20, 'widthRight': 20, 'heightLeft': 46, 'heightRight': 46,
            'spacing': 30, 'positionYLeft': -2, 'positionYRight': -2}
    sprout = {
        'body': {'primary': sphere(202, 188, 140), 'nodes': [
            node(sphere(80, 38, 30), -30, -99, angle=32),
            node(sphere(80, 38, 30), 30, -104, angle=-32),
        ]},
        'eyes': copy.deepcopy(eyes),
    }
    petals = []
    for index in range(6):
        angle = math.radians(index * 60 - 90)
        petals.append(node(sphere(102, 102, 48), round(72 * math.cos(angle), 3),
                           round(72 * math.sin(angle), 3), z=-32))
    bloom = {'body': {'primary': sphere(150, 150, 120), 'nodes': petals},
             'eyes': copy.deepcopy(eyes)}
    return {'sprout': sprout, 'bloom': bloom}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('studio_document', type=Path)
    args = parser.parse_args()
    document = json.loads(args.studio_document.read_text(encoding='utf-8'))
    names = {'Strobi': 'strobi', 'Freddy': 'freddy', 'Citrus': 'citrus', 'Nova': 'nova',
             'Sunee': 'sunee', 'Cloudee': 'cloudee'}
    selected = {}
    for avatar in document['library']['avatars']:
        if avatar['name'] not in names:
            continue
        body = avatar['body']
        selected[names[avatar['name']]] = {
            'body': {'primary': compatible_surface(body['primary']), 'nodes': [
                {'surface': compatible_surface(item['surface']),
                 'position': item['position'], 'rotation': item['rotation']}
                for item in body['nodes']
            ]},
            'eyes': avatar['eyes'],
        }
    if len(selected) != len(names):
        raise ValueError('The upstream preset schema or names have changed.')
    selected.update(local_presets(selected['sunee']['eyes']))
    for name, preset in selected.items():
        preset['viewport'] = VIEWPORTS[name]
    expressions = {}
    keys = {'joyful-wide': 'happy', 'skeptical-left': 'wink', 'sleepy-squint': 'sleepy',
            'curious-left': 'curious', 'surprised-left': 'surprised',
            'shy-downward': 'shy', 'angry-right': 'determined'}
    for expression in document['expressions']:
        if expression.get('semanticKey') in keys:
            expressions[keys[expression['semanticKey']]] = {
                key: value for key, value in expression.items()
                if key not in ('id', 'semanticKey', 'bodyColor', 'eyeColor')
            }
    if len(expressions) != len(keys):
        raise ValueError('The upstream expression schema or names have changed.')
    target = Path(__file__).resolve().parents[2] / 'frontend' / 'avatar-presets.json'
    target.write_text(json.dumps({'presets': selected, 'expressions': expressions},
                                 ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
