from admin_report_service import build_report_list_query, normalize_report_resolution


def test_build_report_list_query_defaults_to_pending_status():
    base_sql, count_sql, params = build_report_list_query('pending')

    assert 'WHERE reports.status = ?' in base_sql
    assert count_sql.endswith('WHERE reports.status = ?')
    assert params == ['pending']


def test_build_report_list_query_allows_unknown_status_without_filter():
    base_sql, count_sql, params = build_report_list_query('all')

    assert 'WHERE reports.status = ?' not in base_sql
    assert params == []


def test_normalize_report_resolution_defaults_to_resolved():
    payload = normalize_report_resolution({})

    assert payload == {'status': 'resolved', 'hide_lineup': False}


def test_normalize_report_resolution_keeps_dismissed_and_hide_flag():
    payload = normalize_report_resolution({'status': 'dismissed', 'hide_lineup': 1})

    assert payload == {'status': 'dismissed', 'hide_lineup': True}
