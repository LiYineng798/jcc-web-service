from datetime import datetime

from copy_action_service import record_copy_action
from db import db_kind, get_db, now_text
from db_adapter import insert_ignore_sql, insert_returning_id_sql, last_insert_id
from lineups_serialization import serialize_lineup_row
from lineups_utils import bucket_start, lineup_is_visible_to_user, lineup_row
from scoring import score_map
from notification_service import notify_author
from feedback_service import create_feedback


def like_lineup_record(user, lineup_id):
    row = lineup_row(lineup_id)
    if not lineup_is_visible_to_user(row, user):
        return None, '阵容不存在', 404
    if row['status'] == 'banned':
        return None, '封禁阵容暂不可互动', 409
    today = datetime.now().strftime('%Y-%m-%d')
    db = get_db()
    count = db.execute('SELECT COUNT(*) AS c FROM likes WHERE user_id = ? AND like_date = ?', (user['id'], today)).fetchone()['c']
    if count >= 5:
        return None, '今天点赞次数已用完', 429
    cursor = db.execute(
        'INSERT INTO likes (user_id,lineup_id,like_date,created_at) VALUES (?,?,?,?) ON CONFLICT(user_id,lineup_id,like_date) DO NOTHING',
        (user['id'],lineup_id,today,now_text()),
    )
    if not cursor.rowcount:
        db.rollback()
        return None, '今天已经点赞过该阵容', 409
    notify_author(db, row, 'like', user)
    db.commit()
    return {'ok': True, 'lineup': serialize_lineup_row(lineup_row(lineup_id), score_map(), user=user)}, None, 201


def copy_lineup_record(user, lineup_id, ip, source_page=''):
    row = lineup_row(lineup_id)
    if not lineup_is_visible_to_user(row, user):
        return None, '阵容不存在', 404
    if row['status'] == 'banned':
        return None, '封禁阵容暂不可复制', 409
    copy_key = f'user:{user["id"]}' if user else f'ip:{ip}'
    bucket = bucket_start()
    db = get_db()
    cursor = db.execute('''INSERT INTO copy_events
        (lineup_id,user_id,ip_address,copy_key,bucket_start,counted,created_at)
        VALUES (?,?,?,?,?,1,?) ON CONFLICT(lineup_id,copy_key,bucket_start) DO NOTHING''',
        (lineup_id,user['id'] if user else None,ip,copy_key,bucket,now_text()))
    counted = bool(cursor.rowcount)
    if counted:
        notify_author(db, row, 'copy', user)
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
    if row['status'] == 'banned':
        return None, '封禁阵容暂不可收藏', 409
    db = get_db()
    cursor = db.execute(
        insert_ignore_sql(
            'favorites',
            ['user_id', 'lineup_id', 'created_at'],
            ['user_id', 'lineup_id'],
            db_kind(),
        ),
        (user['id'], lineup_id, now_text()),
    )
    if cursor.rowcount:
        notify_author(db, row, 'favorite', user)
    db.commit()
    return {'ok': True, 'created': bool(cursor.rowcount)}, None, 200


def unfavorite_lineup_record(user, lineup_id):
    get_db().execute('DELETE FROM favorites WHERE user_id = ? AND lineup_id = ?', (user['id'], lineup_id))
    get_db().commit()
    return {'ok': True}, None, 200


def report_lineup_record(user, lineup_id, reason):
    clean_reason = str(reason or '').strip()
    if not clean_reason or len(clean_reason) > 300:
        return None, '请输入 1-300 字失效反馈原因', 400
    row = lineup_row(lineup_id)
    if not lineup_is_visible_to_user(row, user):
        return None, '阵容不存在', 404
    if row['status'] == 'banned':
        return None, '该阵容已封禁，无需重复反馈', 409
    cursor = get_db().execute(
        insert_returning_id_sql(
            'INSERT INTO reports (reporter_user_id, lineup_id, reason, status, created_at) VALUES (?, ?, ?, ?, ?)',
            db_kind(),
        ),
        (user['id'], lineup_id, clean_reason, 'pending', now_text()),
    )
    report_id = last_insert_id(cursor, db_kind())
    receipt = create_feedback(get_db(), 'report', report_id, user['id'], row['name'], clean_reason, lineup_id)
    get_db().commit()
    return {'id': report_id, **receipt}, None, 201
