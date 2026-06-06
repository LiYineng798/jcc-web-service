from admin_lineup_service import build_admin_lineups_query, prepare_admin_lineup_update


def test_build_admin_lineups_query_without_search():
    base_sql, count_sql, params = build_admin_lineups_query('')

    assert "WHERE lineups.status != 'deleted'" in base_sql
    assert count_sql.endswith("WHERE lineups.status != 'deleted' ")
    assert params == []


def test_build_admin_lineups_query_with_search():
    base_sql, count_sql, params = build_admin_lineups_query('法师')

    assert 'lineups.name LIKE ?' in base_sql
    assert params == ['%法师%', '%法师%', '%法师%', '%法师%']


def test_prepare_admin_lineup_update_collects_supported_fields():
    fields, params = prepare_admin_lineup_update({'name': '新版', 'status': 'hidden'})

    assert fields == ['name = ?', 'status = ?']
    assert params == ['新版', 'hidden']
