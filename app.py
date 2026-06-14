import os

from flask import Flask

from app_pages import register_page_routes, register_test_helpers
from config import apply_config
from db import close_db, init_db, table_names


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    apply_config(app, test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    app.teardown_appcontext(close_db)

    from auth import auth_bp
    from captcha import captcha_bp, lookup_answer_for_tests
    from lineups import lineups_bp
    from admin import admin_bp
    from live_comps import live_comps_bp
    from guestbook import guestbook_bp
    from patch_notes import patch_notes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(captcha_bp)
    app.register_blueprint(lineups_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(live_comps_bp)
    app.register_blueprint(guestbook_bp)
    app.register_blueprint(patch_notes_bp)

    register_page_routes(app)

    with app.app_context():
        init_db()

    def get_table_names_for_tests():
        with app.app_context():
            return table_names()

    def lookup_captcha_answer_for_tests_wrapper(token):
        with app.app_context():
            return lookup_answer_for_tests(token)

    register_test_helpers(app, get_table_names_for_tests, lookup_captcha_answer_for_tests_wrapper)
    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
