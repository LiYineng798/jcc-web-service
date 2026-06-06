from lineups_query import build_list_clauses, order_by_ids_sql


def test_build_list_clauses_uses_default_season_for_public_view():
    clauses, params = build_list_clauses(
        user=None,
        view='all',
        query='',
        season_id=None,
        default_season_id='s17-star-god',
    )

    assert clauses == ["l.status = 'normal'", 'l.season_id = ?']
    assert params == ['s17-star-god']


def test_build_list_clauses_switches_to_mine_view_scope():
    clauses, params = build_list_clauses(
        user={'id': 7, 'role': 'user'},
        view='mine',
        query='我的',
        season_id='s16-legends',
        default_season_id='s17-star-god',
    )

    assert clauses == ["l.status != 'deleted'", 'l.user_id = ?', 'l.name LIKE ?']
    assert params == [7, '%我的%']


def test_build_list_clauses_adds_favorite_filter():
    clauses, params = build_list_clauses(
        user={'id': 3, 'role': 'user'},
        view='favorites',
        query='收藏',
        season_id='lucky-lantern',
        default_season_id='s17-star-god',
    )

    assert "EXISTS (SELECT 1 FROM favorites f WHERE f.lineup_id = l.id AND f.user_id = ?)" in clauses
    assert 'l.season_id = ?' in clauses
    assert params == [3, 'lucky-lantern', 3, '%收藏%']


def test_order_by_ids_sql_builds_stable_case_order():
    sql = order_by_ids_sql([10, 5, 9])

    assert sql == 'CASE l.id WHEN 10 THEN 0 WHEN 5 THEN 1 WHEN 9 THEN 2 ELSE 3 END'
