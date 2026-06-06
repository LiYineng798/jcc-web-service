from datetime import datetime

from copy_action_service import record_copy_action
from db import get_db, now_text
from lineups_serialization import serialize_lineup_row
from lineups_utils import bucket_start, lineup_is_visible_to_user, lineup_row
from scoring import score_map


def like_lineup_record(user, lineup_id):
    row = lineup_row(lineup_id)
    if not lineup_is_visible_to_user(row, user):
        return None, '阵容不存在', 404
    today = datetime.now().strftime('%Y-%m-%d')
    db = get_db()
    count = db.execute('SELECT COUNT(*) AS c FROM likes WHERE user_id = ? AND like_date = ?', (user['id'], today)).fetchone()['c']
    if count >= 5:
        return None, '今天点赞次数已用完', 429
    try:
        db.execute(
            'INSERT INTO likes (user_id, lineup_id, like_date, created_at) VALUES (?, ?, ?, ?)',
            (user['id'], lineup_id, today, now_text()),
        )
        db.commit()
    except Exception:
        db.rollback()
        return None, '今天已经点赞过该阵容', 409
    return {'ok': True, 'lineup': serialize_lineup_row(lineup_row(lineup_id), score_map(), user=user)}, None, 201


def copy_lineup_record(user, lineup_id, ip, source_page=''):
    row = lineup_row(lineup_id)
    if not lineup_is_visible_to_user(row, user):
        return None, '阵容不存在', 404
    copy_key = f'user:{user["id"]}' if user else f'ip:{ip}'
    bucket = bucket_start()
    db = get_db()
    counted = True
    try:
        db.execute(
            '''INSERT INTO copy_events (lineup_id, user_id, ip_address, copy_key, bucket_start, counted, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)''',
            (lineup_id, user['id'] if user else None, ip, copy_key, bucket, now_text()),
        )
        db.commit()
    except Exception:
        db.rollback()
        counted = False
    record_copy_action(
        target_type='lineup',
        target_id=lineup_id,
        user=user,
        ip_address=ip,
        source_page=source_page,
        success=True,
        counted=counted,
        season_id=row['season_id'],
    )
    db.commit()
    return {'ok': True, 'counted': counted}, None, 200


def favorite_lineup_record(user, lineup_id):
    row = lineup_row(lineup_id)
    if not lineup_is_visible_to_user(row, user):
        return None, '阵容不存在', 404
    db = get_db()
    cursor = db.execute(
        'INSERT OR IGNORE INTO favorites (user_id, lineup_id, created_at) VALUES (?, ?, ?)',
        (user['id'], lineup_id, now_text()),
    )
    db.commit()
    return {'ok': True, 'created': bool(cursor.rowcount)}, None, 200


def unfavorite_lineup_record(user, lineup_id):
    get_db().execute('DELETE FROM favorites WHERE user_id = ? AND lineup_id = ?', (user['id'], lineup_id))
    get_db().commit()
    return {'ok': True}, None, 200


def report_lineup_record(user, lineup_id, reason):
    clean_reason = str(reason or '').strip()
    if not clean_reason or len(clean_reason) > 300:
        return None, '请输入 1-300 字举报原因', 400
    row = lineup_row(lineup_id)
    if not lineup_is_visible_to_user(row, user):
        return None, '阵容不存在', 404
    cursor = get_db().execute(
        'INSERT INTO reports (reporter_user_id, lineup_id, reason, status, created_at) VALUES (?, ?, ?, ?, ?)',
        (user['id'], lineup_id, clean_reason, 'pending', now_text()),
    )
    get_db().commit()
    return {'id': cursor.lastrowid, 'status': 'pending'}, None, 201
