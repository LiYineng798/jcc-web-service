import os

from flask import Flask, abort, request

from app_pages import register_page_routes, register_test_helpers
from assets_version import register_asset_helpers
from config import apply_config
from db import close_db, init_db, table_names
from daily_report_worker import start_daily_report_worker
from seo import make_seo


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    apply_config(app, test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    app.teardown_appcontext(close_db)
    register_asset_helpers(app)

    from auth import auth_bp
    from captcha import captcha_bp, lookup_answer_for_tests
    from lineups import lineups_bp
    from admin import admin_bp
    from live_comps import live_comps_bp
    from live_comps_helpers import clear_live_comps_caches
    from guestbook import guestbook_bp
    from patch_notes import patch_notes_bp

    clear_live_comps_caches()

    app.register_blueprint(auth_bp)
    app.register_blueprint(captcha_bp)
    app.register_blueprint(lineups_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(live_comps_bp)
    app.register_blueprint(guestbook_bp)
    app.register_blueprint(patch_notes_bp)

    register_page_routes(app)

    @app.errorhandler(404)
    def not_found(_error):
        return app.jinja_env.get_or_select_template('404.html').render(
            seo=make_seo(title='页面不存在', description='页面不存在或当前不可访问。', path=request.path, noindex=True),
        ), 404

    @app.after_request
    def set_mutable_season_data_cache_policy(response):
        if request.path.startswith('/static/season-data/') and request.path.endswith('.json'):
            response.headers['Cache-Control'] = 'public, max-age=0, must-revalidate'
        return response

    @app.before_request
    def reject_hidden_season_assets():
        # Static season JSON/images are otherwise reachable without a page route.
        prefix = '/static/season-data/'
        if not request.path.startswith(prefix):
            return None
        season_id = request.path[len(prefix):].split('/', 1)[0]
        if season_id == 'catalog.json':
            return None
        from season_visibility import get_season
        if not get_season('library', season_id) and not get_season('simulator', season_id):
            abort(404)
        return None

    with app.app_context():
        init_db()

    def get_table_names_for_tests():
        with app.app_context():
            return table_names()

    def lookup_captcha_answer_for_tests_wrapper(token):
        with app.app_context():
            return lookup_answer_for_tests(token)

    register_test_helpers(app, get_table_names_for_tests, lookup_captcha_answer_for_tests_wrapper)
    start_daily_report_worker(app)
    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
