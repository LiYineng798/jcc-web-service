"""Local review of poster finishes and analytics, using fictional activity only."""
import json
import os
from datetime import datetime

from serve_search_device_preview import create_preview_app


def create_app():
    app = create_preview_app()
    with open(app.config['SEASON_VISIBILITY_PATH'], 'w', encoding='utf-8') as handle:
        json.dump({'simulator': {'s16_5': {'status': 'active', 'order': 0}}}, handle)
    with app.app_context():
        from analytics import record_growth_event
        from db import get_db
        db = get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        if not db.execute('SELECT id FROM growth_events WHERE created_at >= ?', (today,)).fetchone():
            user = db.execute("SELECT id FROM users WHERE username='previewuser'").fetchone()['id']
            for event, count in [('click_login_entry', 24), ('open_auth_page', 18),
                                 ('guest_click_like', 12), ('guest_click_favorite', 8)]:
                for index in range(count):
                    record_growth_event(event, visitor_token=f'preview-{index}', page_key='home',
                                        created_at=f'{today} 09:00:00')
            for event in ['register_success', 'login_success', 'post_login_like',
                          'post_login_favorite', 'post_login_create_lineup']:
                record_growth_event(event, user_id=user, visitor_token='preview-member',
                                    page_key='home', created_at=f'{today} 09:05:00')
    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.environ.get('POSTER_PREVIEW_PORT', '5146')),
                     debug=False, use_reloader=False, threaded=True)
