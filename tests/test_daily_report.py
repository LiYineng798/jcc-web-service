from test_admin import login_admin
from test_auth import register_user


def _seed_daily_activity(app):
    """Insert one synthetic day of activity on 2026-08-09."""
    with app.app_context():
        from db import get_db
        db = get_db()
        admin_id = db.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()['id']

        db.execute(
            """
            INSERT INTO users (username, email, nickname, password_hash, role, status, created_at, updated_at)
            VALUES ('u1', 'u1@example.com', 'U1', 'x', 'user', 'active', '2026-08-09 09:00:00', '2026-08-09 09:00:00')
            """
        )
        u1 = db.execute("SELECT id FROM users WHERE username = 'u1'").fetchone()['id']
        db.execute(
            """
            INSERT INTO users (username, email, nickname, password_hash, role, status, created_at, updated_at)
            VALUES ('u2', 'u2@example.com', 'U2', 'x', 'user', 'active', '2026-08-08 09:00:00', '2026-08-08 09:00:00')
            """
        )

        cursor = db.execute(
            """
            INSERT INTO lineups (user_id, name, code, season_id, status, created_at, updated_at)
            VALUES (?, '九五至尊', '#CODE888', 's17-star-god', 'normal', '2026-08-09 10:00:00', '2026-08-09 10:00:00')
            """,
            (u1,),
        )
        lineup_id = cursor.lastrowid

        def visit(key, hour, page='home', user_id=None):
            db.execute(
                """
                INSERT INTO visit_events (visit_date, visitor_key, visitor_kind, user_id, visitor_token, ip_address, page_key, created_at)
                VALUES ('2026-08-09', ?, 'guest_token', ?, ?, '1.1.1.1', ?, ?)
                """,
                (key, user_id, 'tok-' + key, page, f'2026-08-09 {hour:02d}:30:00'),
            )

        visit('v1', 8)
        visit('v1', 20, page='lineup_detail')
        visit('v2', 8)
        visit('v2', 20, page='lineup_detail')
        visit('v3', 20)
        # Admin traffic must be excluded from visitor metrics.
        db.execute(
            """
            INSERT INTO visit_events (visit_date, visitor_key, visitor_kind, user_id, visitor_token, ip_address, page_key, created_at)
            VALUES ('2026-08-09', 'admin:1', 'user', ?, NULL, '9.9.9.9', 'admin', '2026-08-09 20:00:00')
            """,
            (admin_id,),
        )

        db.execute(
            """
            INSERT INTO login_events (user_id, ip_address, success, created_at)
            VALUES (?, '1.1.1.1', 1, '2026-08-09 09:05:00')
            """,
            (u1,),
        )
        db.execute(
            """
            INSERT INTO copy_action_events (target_type, target_id, season_id, lineup_id, user_id, visitor_token, ip_address, source_page, success, counted, created_at)
            VALUES ('lineup', ?, 's17-star-god', ?, NULL, 'tok-c1', '2.2.2.2', 'home', 1, 1, '2026-08-09 10:05:00')
            """,
            (str(lineup_id), lineup_id),
        )
        db.execute(
            """
            INSERT INTO copy_action_events (target_type, target_id, season_id, lineup_id, user_id, visitor_token, ip_address, source_page, success, counted, created_at)
            VALUES ('live_comp', 'lc-1', 's17-star-god', NULL, NULL, 'tok-c2', '2.2.2.3', 'home', 1, 1, '2026-08-09 10:06:00')
            """
        )
        db.execute(
            """
            INSERT INTO guestbook_messages (user_id, nickname, content, ip_address, created_at)
            VALUES (?, '游客', '阵容很实用', '1.1.1.1', '2026-08-09 11:00:00')
            """,
            (u1,),
        )
        db.execute(
            """
            INSERT INTO reports (reporter_user_id, lineup_id, reason, status, created_at)
            VALUES (?, ?, '抄袭', 'pending', '2026-08-09 11:30:00')
            """,
            (u1, lineup_id),
        )
        db.execute(
            """
            INSERT INTO likes (user_id, lineup_id, like_date, created_at)
            VALUES (?, ?, '2026-08-09', '2026-08-09 12:00:00')
            """,
            (u1, lineup_id),
        )
        db.commit()


def test_daily_report_generation_aggregates_site_activity(app):
    _seed_daily_activity(app)
    with app.app_context():
        from daily_report_service import ensure_daily_report
        report = ensure_daily_report('2026-08-09')

    assert report is not None
    summary = report['summary']
    assert summary['unique_visitors'] == 3
    assert summary['page_visits'] == 5
    assert summary['new_visitors'] == 3
    assert summary['returning_visitors'] == 0
    assert summary['new_registrations'] == 1
    assert summary['successful_logins'] == 1
    assert summary['lineup_copies'] == 1
    assert summary['live_comp_copies'] == 1
    assert summary['total_copies'] == 2
    assert summary['new_lineups'] == 1
    assert summary['guestbook_messages'] == 1
    assert summary['reports_submitted'] == 1
    assert summary['like_actions'] == 1
    assert summary['favorite_actions'] == 0

    assert len(report['hourly']['uv']) == 24
    assert report['hourly']['uv'][8] == 2
    assert report['hourly']['uv'][20] == 3
    assert report['hourly']['visits'][8] == 2
    assert report['hourly']['copies'][10] == 2
    assert report['peak_visit_hour'] == {'hour': 20, 'value': 3}
    assert report['peak_copy_hour'] == {'hour': 10, 'value': 2}

    assert report['top_pages'][0]['page_key'] == 'home'
    assert report['top_pages'][0]['visits'] == 3
    assert report['top_pages'][0]['uv'] == 3

    lineup_rank = next(item for item in report['top_copied'] if item['target_type'] == 'lineup')
    assert lineup_rank['title'] == '九五至尊'
    assert lineup_rank['code'] == '#CODE888'
    assert lineup_rank['copies'] == 1
    assert report['top_copied'][1]['target_type'] == 'live_comp'
    assert report['deltas'] is None


def test_daily_report_generation_is_idempotent(app):
    _seed_daily_activity(app)
    with app.app_context():
        from daily_report_service import ensure_daily_report
        first = ensure_daily_report('2026-08-09')
        second = ensure_daily_report('2026-08-09')
        assert first['generated_at'] == second['generated_at']
        from db import get_db
        row = get_db().execute(
            "SELECT COUNT(*) AS c FROM daily_admin_reports WHERE report_date = '2026-08-09'"
        ).fetchone()
        assert row['c'] == 1


def test_force_regenerates_existing_report(app):
    _seed_daily_activity(app)
    with app.app_context():
        from daily_report_service import ensure_daily_report
        ensure_daily_report('2026-08-09')

    with app.app_context():
        from db import get_db
        db = get_db()
        db.execute(
            """
            INSERT INTO visit_events (visit_date, visitor_key, visitor_kind, user_id, visitor_token, ip_address, page_key, created_at)
            VALUES ('2026-08-09', 'v4', 'guest_token', NULL, 'tok-v4', '1.1.1.4', 'home', '2026-08-09 21:00:00')
            """
        )
        db.commit()

    with app.app_context():
        from daily_report_service import ensure_daily_report
        report = ensure_daily_report('2026-08-09', force=True)
        assert report['summary']['unique_visitors'] == 4


def test_daily_report_deltas_compare_previous_report(app):
    _seed_daily_activity(app)
    with app.app_context():
        from daily_report_service import ensure_daily_report
        ensure_daily_report('2026-08-08')
        report = ensure_daily_report('2026-08-09')

    assert report['previous_date'] == '2026-08-08'
    assert report['deltas']['unique_visitors'] == 3
    assert report['deltas']['page_visits'] == 5
    assert report['deltas']['total_copies'] == 2


def test_daily_report_api_requires_admin(client):
    assert client.get('/api/admin/daily-reports').status_code == 401
    register_user(client)
    assert client.get('/api/admin/daily-reports').status_code == 403


def test_daily_report_api_list_detail_and_generate(client):
    _seed_daily_activity(client.application)
    headers = login_admin(client)

    response = client.post('/api/admin/daily-reports/2026-08-09/generate', headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data['report_date'] == '2026-08-09'
    assert data['summary']['unique_visitors'] == 3

    listing = client.get('/api/admin/daily-reports', headers=headers).get_json()
    assert any(item['report_date'] == '2026-08-09' for item in listing['items'])

    detail = client.get('/api/admin/daily-reports/2026-08-09', headers=headers).get_json()
    assert detail['summary']['total_copies'] == 2
    assert len(detail['hourly']['uv']) == 24


def test_daily_report_api_rejects_invalid_dates(client):
    headers = login_admin(client)
    assert client.get('/api/admin/daily-reports/not-a-date', headers=headers).status_code == 404
    assert client.post('/api/admin/daily-reports/not-a-date/generate', headers=headers).status_code == 400
    assert client.get('/api/admin/daily-reports/2026-08-01', headers=headers).status_code == 404


def test_daily_report_generate_requires_csrf(client):
    _seed_daily_activity(client.application)
    login_admin(client)
    response = client.post('/api/admin/daily-reports/2026-08-09/generate')
    assert response.status_code in (400, 403)


def test_admin_page_includes_daily_report_entry(client):
    login_admin(client)
    html = client.get('/admin').get_data(as_text=True)
    assert 'data-admin-tab="daily-reports"' in html
    assert 'admin/daily-reports.js' in html


def test_background_worker_is_disabled_in_tests(app):
    from daily_report_worker import start_daily_report_worker
    assert start_daily_report_worker(app) is None
