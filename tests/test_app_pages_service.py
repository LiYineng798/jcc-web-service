from flask import Flask

from app_pages import register_page_routes, register_test_helpers


def test_register_page_routes_adds_core_endpoints():
    app = Flask(__name__)
    register_page_routes(app)
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert '/' in rules
    assert '/auth' in rules
    assert '/favicon.ico' in rules
    assert '/lineup/new' in rules
    assert '/lineup/<int:lineup_id>/edit' in rules
    assert '/lineup/<int:lineup_id>' in rules
    assert '/author/<username>' in rules
    assert '/tools/lineup-simulator' in rules
    assert '/me' in rules
    assert '/api/health' in rules


def test_register_test_helpers_attaches_lookup_functions():
    app = Flask(__name__)

    register_test_helpers(
        app,
        get_table_names_func=lambda: {'users', 'lineups'},
        lookup_captcha_answer_func=lambda token: {'token': token},
    )

    assert app.get_table_names() == {'users', 'lineups'}
    assert app.lookup_captcha_answer_for_tests('abc') == {'token': 'abc'}
