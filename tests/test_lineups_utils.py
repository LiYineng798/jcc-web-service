from lineups_utils import lineup_is_visible_to_user, normalize_lineup_status, parse_positive_int, row_value, visibility_clause


def test_parse_positive_int_returns_default_for_invalid_values():
    assert parse_positive_int('8', 1) == 8
    assert parse_positive_int('0', 1) == 1
    assert parse_positive_int('bad', 3) == 3
    assert parse_positive_int(None, 5) == 5


def test_normalize_lineup_status_accepts_only_visible_statuses():
    assert normalize_lineup_status('normal') == 'normal'
    assert normalize_lineup_status('HIDDEN') == 'hidden'
    assert normalize_lineup_status('', default='normal') == 'normal'
    assert normalize_lineup_status('deleted') is None


def test_visibility_clause_matches_user_roles():
    assert visibility_clause(None) == ("l.status = 'normal'", [])
    assert visibility_clause({'id': 7, 'role': 'user'}, alias='x') == (
        "(x.status = 'normal' OR (x.status = 'hidden' AND x.user_id = ?))",
        [7],
    )
    assert visibility_clause({'id': 1, 'role': 'admin'}, alias='x') == ("x.status != 'deleted'", [])


def test_lineup_is_visible_to_user_rules():
    normal = {'status': 'normal', 'user_id': 2}
    hidden = {'status': 'hidden', 'user_id': 2}
    deleted = {'status': 'deleted', 'user_id': 2}

    assert lineup_is_visible_to_user(normal, None) is True
    assert lineup_is_visible_to_user(hidden, None) is False
    assert lineup_is_visible_to_user(hidden, {'id': 2, 'role': 'user'}) is True
    assert lineup_is_visible_to_user(hidden, {'id': 3, 'role': 'user'}) is False
    assert lineup_is_visible_to_user(hidden, {'id': 9, 'role': 'admin'}) is True
    assert lineup_is_visible_to_user(deleted, {'id': 9, 'role': 'admin'}) is False


def test_row_value_supports_dict_rows():
    assert row_value({'name': '阵容'}, 'name') == '阵容'
    assert row_value({'name': '阵容'}, 'missing', default='x') == 'x'
