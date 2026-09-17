import re
from pathlib import Path

import pytest

from scripts.season_library.import_witch_rewards import extract
from witch_rewards_service import reward_tiers


PAGE = '/tools/s18-witch-rewards'


def test_snapshot_complete_and_assets_local():
    tiers = reward_tiers()
    assert [t['label'] for t in tiers] == ['40', '85', '130', '185', '250', '365', '500', '650', '800']
    assert sum(len(t['list']) for t in tiers) == 35
    for tier in tiers:
        assert abs(sum(float(row['percent'].rstrip('%')) for row in tier['list']) - 100) < .3
        for row in tier['list']:
            for reward in row['rewards']:
                assert reward['count'] >= 1
                assert reward['tier'] in (0, 1, 2, 3)
                assert (Path(__file__).resolve().parents[1] / 'static' / reward['image']).is_file()
    sample = tiers[5]
    assert sample['estimatedValue'] == 76
    assert len(sample['list']) == 6
    assert sample['list'][0]['rewards'][0]['count'] == 2
    assert sample['list'][1]['rewards'][0]['tier'] == 2
    assert sample['list'][1]['rewards'][0]['title'] == '莫甘娜'


def test_public_page_deep_links_and_validation(client):
    for stacks in ['40', '365', '800']:
        response = client.get(f'{PAGE}?stacks={stacks}')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert f'data-stack="{stacks}" aria-current="true"' in html
        assert f'id="rewards-{stacks}" aria-labelledby="reward-title-{stacks}" >' in html
    assert client.get(PAGE).status_code == 200
    for invalid in ['0', '366', '-1', '<script>', '']:
        assert client.get(PAGE, query_string={'stacks': invalid}).status_code == 400
    assert PAGE in client.get('/sitemap.xml').get_data(as_text=True)
    home = client.get('/').get_data(as_text=True)
    assert home.count(f'href="{PAGE}"') == 2
    assert home.index('S18 · 当季工具') < home.index('S16.5 · 恭喜发财') < home.index('S8回归信息差')
    for src in set(re.findall(r'<img src="([^"]+)"', html)):
        assert client.get(src).status_code == 200


def test_importer_rejects_missing_data_and_executable_literals():
    with pytest.raises(ValueError):
        extract({'log': {'entries': []}})
    captured = {'request': {'url': 'https://www.datatft.com/assets/example.js'},
                'response': {'content': {'text': '魔女:[{label:evil()}],"6幻灵战队jcc"'}}}
    with pytest.raises(ValueError):
        extract({'log': {'entries': [captured]}})
