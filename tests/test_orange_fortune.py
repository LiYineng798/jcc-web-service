import json
from collections import Counter

from orange_fortune_service import CATALOG, card_guide, catalog, parse_arguments

PAGE = '/tools/orange-fortune'


def test_catalog_preserves_official_text_and_matches_local_art():
    source = json.loads(CATALOG.read_text(encoding='utf-8'))
    cards = catalog()['cards']
    assert len(cards) == 200
    assert Counter(c['tier'] for c in cards) == {1: 20, 2: 30, 3: 60, 4: 49, 5: 41}
    assert [c['id'] for c in cards if c['image'] is None] == ['7250012']
    for card in cards:
        assert card['source'] == source['data'][card['id']]
        assert card['description'] == source['data'][card['id']]['sDesc']
        if card['image']:
            assert (CATALOG.parents[2] / card['image']).is_file()
    # Icon URL IDs must not be substituted for the downloaded card-ID filenames.
    card = next(c for c in cards if c['id'] == '7210024')
    assert card['source']['sIcon'].endswith('/7210025.png')
    assert card['image'].endswith('/7210024.png')
    assert Counter((a['width'], a['height']) for a in source['assets'].values() if a) == {(326, 430): 113, (326, 524): 59, (324, 526): 27}


def test_filters_combine_and_include_secondary_rounds():
    guide = card_guide('  黑玫瑰  ', '5', '1006', '1-3')
    assert guide['visible_ids'] == {'7250036'}
    assert not card_guide('黑玫瑰', '1')['visible_ids']
    card = next(c for c in catalog()['cards'] if c['id'] == '7250044')
    assert card['rounds'] == ['2-5', '4-1']
    assert card['id'] in card_guide(round_value='4-1')['visible_ids']
    assert len(card_guide(tier='999', category='unknown', round_value='x')['visible_ids']) == 200
    assert len(card_guide('x' * 1000)['query']) == 100
    assert parse_arguments('round=1-3^equipNum=2^equipnum=1') == {'round': '1-3', 'equipNum': '2', 'equipnum': '1'}


def test_guest_page_search_and_home_navigation(client):
    page = client.get(PAGE)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert html.count('class="fortune-card"') == 200
    assert '黑玫瑰夜市' in html and '卡图暂缺' in html
    filtered = client.get(PAGE, query_string={'q': '黑玫瑰', 'tier': '5'}).get_data(as_text=True)
    assert '找到 <strong>1</strong> 张卡片' in filtered
    assert 'noindex' in filtered
    malicious = client.get(PAGE, query_string={'q': '"><script>alert(1)</script>'}).get_data(as_text=True)
    assert '"><script>alert(1)</script>' not in malicious
    assert client.get('/').get_data(as_text=True).count(f'href="{PAGE}"') == 2
    assert PAGE in client.get('/sitemap.xml').get_data(as_text=True)
    assert client.get('/static/tools/orange-fortune/images/7250036.png').status_code == 200
