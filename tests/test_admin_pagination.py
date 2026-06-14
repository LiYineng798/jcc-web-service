from admin_pagination import paginate_items, parse_page, parse_page_size


def test_parse_page_clamps_invalid_values():
    assert parse_page({'page': '3'}) == 3
    assert parse_page({'page': '0'}) == 1
    assert parse_page({'page': 'bad'}) == 1
    assert parse_page({}) == 1


def test_parse_page_size_uses_default_and_maximum():
    assert parse_page_size({'page_size': '50'}, default=20, maximum=100) == 50
    assert parse_page_size({'page_size': '500'}, default=20, maximum=100) == 100
    assert parse_page_size({'page_size': '0'}, default=20, maximum=100) == 20
    assert parse_page_size({'page_size': 'bad'}, default=20, maximum=100) == 20


def test_paginate_items_clamps_page_to_total_pages():
    result = paginate_items(list(range(12)), page=9, page_size=5)

    assert result == {
        'items': [10, 11],
        'total': 12,
        'page': 3,
        'page_size': 5,
        'total_pages': 3,
    }
