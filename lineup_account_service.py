from db import get_db
from lineups_serialization import serialize_lineup_row


def build_author_profile_payload(username, viewer, scores):
    author = get_db().execute(
        "SELECT id, username, nickname, role, created_at FROM users WHERE username = ? AND role != 'admin'",
        (username,),
    ).fetchone()
    if not author:
        return None, '作者不存在', 404

    rows = get_db().execute(
        '''
        SELECT
            l.*,
            users.username AS owner_username,
            users.nickname AS owner_nickname_raw,
            users.role AS owner_role
        FROM lineups l
        JOIN users ON users.id = l.user_id
        WHERE l.user_id = ? AND l.status = 'normal'
        ORDER BY l.updated_at DESC, l.id DESC
        ''',
        (author['id'],),
    ).fetchall()
    lineups = [serialize_lineup_row(row, scores, user=viewer) for row in rows]
    return {
        'profile': {
            'username': author['username'],
            'nickname': author['nickname'],
            'created_at': author['created_at'],
        },
        'summary': {
            'published_lineups': len(lineups),
            'total_likes': sum(item['like_count'] for item in lineups),
            'total_copies': sum(item['copy_count'] for item in lineups),
        },
        'lineups': lineups,
    }, None, 200


def build_my_dashboard_payload(user_id):
    db = get_db()
    published_lineups = db.execute(
        "SELECT COUNT(*) AS c FROM lineups WHERE user_id = ? AND status != 'deleted'",
        (user_id,),
    ).fetchone()['c']
    hidden_lineups = db.execute(
        "SELECT COUNT(*) AS c FROM lineups WHERE user_id = ? AND status = 'hidden'",
        (user_id,),
    ).fetchone()['c']
    received_likes = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM likes
        JOIN lineups ON lineups.id = likes.lineup_id
        WHERE lineups.user_id = ?
        ''',
        (user_id,),
    ).fetchone()['c']
    received_favorites = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM favorites
        JOIN lineups ON lineups.id = favorites.lineup_id
        WHERE lineups.user_id = ?
        ''',
        (user_id,),
    ).fetchone()['c']
    received_copies = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM copy_events
        JOIN lineups ON lineups.id = copy_events.lineup_id
        WHERE lineups.user_id = ? AND copy_events.counted = 1
        ''',
        (user_id,),
    ).fetchone()['c']
    submitted_reports = db.execute(
        'SELECT COUNT(*) AS c FROM reports WHERE reporter_user_id = ?',
        (user_id,),
    ).fetchone()['c']
    pending_reports_on_my_lineups = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM reports
        JOIN lineups ON lineups.id = reports.lineup_id
        WHERE lineups.user_id = ? AND reports.status = 'pending'
        ''',
        (user_id,),
    ).fetchone()['c']
    return {
        'published_lineups': published_lineups,
        'hidden_lineups': hidden_lineups,
        'received_likes': received_likes,
        'received_favorites': received_favorites,
        'received_copies': received_copies,
        'submitted_reports': submitted_reports,
        'pending_reports_on_my_lineups': pending_reports_on_my_lineups,
    }


def list_my_reports_payload(user_id):
    rows = get_db().execute(
        '''
        SELECT
            reports.id,
            reports.reason,
            reports.status,
            reports.created_at,
            reports.handled_at,
            lineups.id AS lineup_id,
            lineups.name AS lineup_name,
            lineups.status AS lineup_status
        FROM reports
        JOIN lineups ON lineups.id = reports.lineup_id
        WHERE reports.reporter_user_id = ?
        ORDER BY reports.id DESC
        ''',
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]
