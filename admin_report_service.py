from __future__ import annotations

from audit import write_audit
from db import now_text


def build_report_list_query(status):
    status = str(status or 'pending').strip()
    params = []
    from_sql = '''FROM reports
             JOIN users AS reporter ON reporter.id = reports.reporter_user_id
             LEFT JOIN users AS handler ON handler.id = reports.handled_by
             JOIN lineups ON lineups.id = reports.lineup_id
             LEFT JOIN users AS owner ON owner.id = lineups.user_id'''
    if status in {'pending', 'resolved', 'dismissed'}:
        from_sql += ' WHERE reports.status = ?'
        params.append(status)
    base_sql = '''SELECT
                reports.*,
                (SELECT status FROM feedback_threads f WHERE f.source_type='report' AND f.source_id=reports.id) AS feedback_status,
                reporter.username AS reporter_username,
                reporter.nickname AS reporter_nickname,
                handler.username AS handled_by_username,
                handler.nickname AS handled_by_nickname,
                lineups.name AS lineup_name,
                lineups.code AS lineup_code,
                lineups.status AS lineup_status,
                owner.username AS owner_username,
                owner.nickname AS owner_nickname
             ''' + from_sql + ' ORDER BY reports.id DESC'
    count_sql = 'SELECT COUNT(*) AS c ' + from_sql
    return base_sql, count_sql, params


def normalize_report_resolution(data):
    data = data or {}
    status = data.get('status') if data.get('status') in {'resolved', 'dismissed'} else 'resolved'
    hide_lineup = bool(data.get('hide_lineup'))
    return {'status': status, 'hide_lineup': hide_lineup}


def resolve_report(db, admin_id, report_id, data):
    before = db.execute('SELECT * FROM reports WHERE id = ?', (report_id,)).fetchone()
    if not before:
        return None, '失效反馈不存在', 404
    payload = normalize_report_resolution(data)
    now = now_text()
    db.execute(
        'UPDATE reports SET status = ?, handled_at = ?, handled_by = ? WHERE id = ?',
        (payload['status'], now, admin_id, report_id),
    )
    if payload['hide_lineup']:
        db.execute(
            "UPDATE lineups SET status = 'hidden', updated_at = ?, version = version + 1 WHERE id = ? AND status IN ('normal', 'hidden')",
            (now, before['lineup_id']),
        )
    write_audit(
        admin_id,
        'handle_report',
        'report',
        report_id,
        before=dict(before),
        after={'status': payload['status'], 'hide_lineup': payload['hide_lineup']},
    )
    from feedback_service import create_feedback, update_feedback
    thread = db.execute("SELECT id,revision FROM feedback_threads WHERE source_type='report' AND source_id=?", (report_id,)).fetchone()
    if not thread:
        receipt = create_feedback(db, 'report', report_id, before['reporter_user_id'], '阵容失效反馈', before['reason'], before['lineup_id'])
        thread = {'id': receipt['feedback_id'], 'revision': 1}
    _, error, code = update_feedback(db, {'id': admin_id, 'role': 'admin', 'status': 'active'}, thread['id'], {
        'revision': (data or {}).get('revision', thread['revision']), 'status': payload['status'],
        'body': (data or {}).get('body') or ('管理员已处理该反馈。' if payload['status']=='resolved' else '管理员核实后暂未采纳该反馈。'),
    })
    if error:
        db.rollback()
        return None, error, code
    return {'ok': True, 'id': report_id, 'status': payload['status'], 'hide_lineup': payload['hide_lineup']}, None, 200
