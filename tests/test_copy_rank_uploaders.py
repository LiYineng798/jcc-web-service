import json

from test_daily_report import _seed_daily_activity


def test_rank_and_report_attribute_uploader_and_preserve_snapshot(app):
    from admin_dashboard_service import build_admin_copy_rank_payload
    from daily_report_service import ensure_daily_report, get_daily_report
    from db import get_db
    _seed_daily_activity(app)
    with app.app_context():
        db = get_db()
        rank = build_admin_copy_rank_payload(db, '2026-08-09')
        regular = next(item for item in rank['items'] if item['target_type'] == 'lineup')
        assert regular['uploader'] == 'U1 (@u1)'
        statements = []
        db.connection.set_trace_callback(statements.append)
        try:
            safe_rank = build_admin_copy_rank_payload(db, '2026-08-09', include_details=False)
        finally:
            db.connection.set_trace_callback(None)
        assert all('details' not in item for item in safe_rank['items'])
        assert not any('LEFT JOIN users owner' in statement for statement in statements)
        report = ensure_daily_report('2026-08-09')
        copied = next(item for item in report['top_copied'] if item['target_type'] == 'lineup')
        assert copied['uploader'] == 'U1 (@u1)'
        db.execute("UPDATE users SET nickname='改名' WHERE username='u1'")
        db.commit()
        reread = get_daily_report('2026-08-09')
        assert next(item for item in reread['top_copied'] if item['target_type'] == 'lineup')['uploader'] == 'U1 (@u1)'
        for item in report['top_copied']:
            item.pop('uploader', None)
        db.execute('UPDATE daily_admin_reports SET payload_json=? WHERE report_date=?',
                   (json.dumps(report), '2026-08-09'))
        db.commit()
        legacy = get_daily_report('2026-08-09')
        copied = next(item for item in legacy['top_copied'] if item['target_type'] == 'lineup')
        assert copied['uploader'] == '改名 (@u1)' and copied['uploader_attribution'] == 'current'
        assert legacy['summary'] == report['summary']


def test_live_upload_attribution_uses_manual_code_actor_before_release_actor(app):
    from copy_rank_service import live_uploader
    from db import get_db
    _seed_daily_activity(app)
    with app.app_context():
        db = get_db()
        owner = db.execute("SELECT id FROM users WHERE username='u1'").fetchone()['id']
        other = db.execute("SELECT id FROM users WHERE username='u2'").fetchone()['id']
        payload = {'_release': {'created_by': owner, 'manual_codes': {'items': {'c1': {'updated_by': other}}}}}
        assert live_uploader(db, payload, 's17-star-god', 'c1') == 'U2 (@u2)'
        assert live_uploader(db, payload, 's17-star-god', 'c2') == 'U1 (@u1)'
        payload['tiers'] = {'S': [{'id': 'c1', 'codeSource': 'original'}]}
        assert live_uploader(db, payload, 's17-star-god', 'c1') == 'U1 (@u1)'
        assert '未记录' in live_uploader(db, {}, 's17-star-god', 'c2')
