import json
from collections import Counter

from orange_fortune_service import CATALOG, card_guide, catalog, parse_arguments

PAGE = '/tools/orange-fortune'


def test_catalog_preserves_official_text_and_matches_local_art():
    source = json.loads(CATALOG.read_text(encoding='utf-8'))
    cards = catalog()['cards']
    assert len(cards) == len(source['data']) == 201
    assert Counter(c['tier'] for c in cards) == {1: 20, 2: 30, 3: 60, 4: 50, 5: 41}
    assert Counter(c['tier_name'] for c in cards) == {'基础': 20, '勇士': 30, '王者': 60, '史诗': 50, '传说': 41}
    assert all(c['energy'] == c['tier'] for c in cards)
    # Missing art is exactly what the archive recorded as failed; no other card's image stands in.
    assert {c['id'] for c in cards if c['image'] is None} == set(source['asset_failures'])
    assert all(failure['error'] == 'http_404' for failure in source['asset_failures'].values())
    for card in cards:
        assert card['source'] == source['data'][card['id']]
        assert card['description'] == source['data'][card['id']]['sDesc']
        if card['image']:
            assert (CATALOG.parents[2] / card['image']).is_file()
    hashes = [a['sha256'] for a in source['assets'].values() if a]
    assert len(hashes) == len(set(hashes))
    # Icon URL IDs must not be substituted for the downloaded card-ID filenames.
    card = next(c for c in cards if c['id'] == '7210024')
    assert card['source']['sIcon'].endswith('/7210025.png')
    assert card['image'].endswith('/7210024.png')
    assert source['provenance']['card_url'].endswith('/16/18.18.1-S400001/card.js')


def test_filters_combine_and_include_secondary_rounds():
    guide = card_guide('  黑玫瑰  ', '5', '1006', '1-3')
    assert guide['visible_ids'] == {'7250036'}
    assert not card_guide('黑玫瑰', '1')['visible_ids']
    card = next(c for c in catalog()['cards'] if c['id'] == '7250044')
    assert card['rounds'] == ['2-5', '4-3']
    assert card['id'] in card_guide(round_value='4-3')['visible_ids']
    assert len(card_guide(tier='999', category='unknown', round_value='x')['visible_ids']) == 201
    assert len(card_guide('x' * 1000)['query']) == 100
    assert parse_arguments('round=1-3^equipNum=2^equipnum=1') == {'round': '1-3', 'equipNum': '2', 'equipnum': '1'}


def test_guest_page_search_and_home_navigation(client):
    page = client.get(PAGE)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert html.count('class="fortune-card"') == 201
    assert '全部品阶 <small>201</small>' in html
    assert '全部星级' not in html and ' 星卡片' not in html and '纹章</option>' not in html and '羁绊</option>' in html
    for name in ('基础', '勇士', '王者', '史诗', '传说'):
        assert f'{name}卡片<em>' in html
    for text in ('稳定传送门', '波动传送门', '未知传送门', '≤ 8', '≤ 10', '≤ 15', '0 金橘币', '400 金橘币', '2,000 金橘币',
                 '不损失卡片', '随机损失两张卡片', '随机损失三张卡片'):
        assert text in html
    assert '黑玫瑰夜市' in html and '卡图暂缺' in html
    filtered = client.get(PAGE, query_string={'q': '黑玫瑰', 'tier': '5'}).get_data(as_text=True)
    assert '找到 <strong>1</strong> 张卡片' in filtered
    assert 'noindex' in filtered
    malicious = client.get(PAGE, query_string={'q': '"><script>alert(1)</script>'}).get_data(as_text=True)
    assert '"><script>alert(1)</script>' not in malicious
    assert client.get('/').get_data(as_text=True).count(f'href="{PAGE}"') == 2
    assert PAGE in client.get('/sitemap.xml').get_data(as_text=True)
    assert client.get('/static/tools/orange-fortune/images/7250036.png').status_code == 200
