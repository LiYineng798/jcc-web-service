import base64
import re
from pathlib import Path

import pytest

from golden_egg_service import golden_egg_rewards
from scripts.season_library.import_golden_egg import extract

PAGE = '/tools/golden-egg'


def test_snapshot_and_local_assets():
    data = golden_egg_rewards()
    rows = data['outcomes']
    assert [r['percent'] for r in rows] == ['15%'] * 4 + ['10%'] * 4
    assert rows[0]['rewards'][-1]['count'] == 88
    assert rows[1]['rewards'][0]['count'] == 2
    assert rows[3]['rewards'][1]['count'] == 2
    assert [r['count'] for r in rows[4]['rewards']] == [1, 2, 4, 30]
    assert len(rows[-1]['rewards']) == 8
    root = Path(__file__).resolve().parents[1] / 'static'
    images = {data['augment_image']} | {r['image'] for row in rows for r in row['rewards']}
    assert len(images) == 19
    for image in images:
        assert (root / image).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')


def test_page_navigation_and_server_rendering(client):
    response = client.get(PAGE)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('class="egg-outcome"') == 8
    assert '金蛋海克斯图标' in html
    assert '×88' in html and '数量 4' in html
    assert PAGE in client.get('/sitemap.xml').get_data(as_text=True)
    assert client.get('/').get_data(as_text=True).count(f'href="{PAGE}"') == 2
    for src in set(re.findall(r'<img src="([^"]+)"', html)):
        assert src.startswith('/static/')
        assert client.get(src).status_code == 200


def captured(script):
    return {'log': {'entries': [{'request': {'url': 'https://www.datatft.com/assets/test.js'},
                               'response': {'content': {'text': script}}}]}}


def test_importer_fails_on_incomplete_or_executable_source():
    for script in ['', '金蛋:[{list:evil()}],寻宝:',
                   '金蛋:[{list:[{percent:"15%",rewards:[]}]}],寻宝:',
                   '金蛋:[{list:[{percent:"100%",rewards:[]}]}],寻宝:']:
        with pytest.raises(ValueError):
            extract(captured(script))


def test_importer_normalizes_duplicates_and_gold():
    har = captured('金蛋:[{list:[{percent:"100%",rewards:[{title:"光明武器"},{title:"光明武器"},{title:"88金币"}]}]}],寻宝:')
    for path in ['hex2/TheGoldenEgg_3_.png', 'reward/gmwq.png', 'reward/gold.png']:
        har['log']['entries'].append({'request': {'url': f'https://static.datatft.com/images/{path}'},
                                    'response': {'content': {'encoding': 'base64', 'text': base64.b64encode(b'fixture').decode()}}})
    data, _ = extract(har)
    assert [(r['title'], r['count']) for r in data['outcomes'][0]['rewards']] == [('光明武器', 2), ('金币', 88)]
