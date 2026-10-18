"""Feedback progress and replies. Public responses never expose IPs or staff accounts."""
from audit import write_audit
from db import db_kind, get_db, now_text
from db_adapter import insert_returning_id_sql, last_insert_id
from notification_service import publish_notification

STATUS_LABELS = {'pending': '已收到', 'in_progress': '核实中', 'resolved': '已解决', 'dismissed': '未采纳 / 无法复现'}


def create_feedback(db, source_type, source_id, user_id, title, content, lineup_id=None):
    now = now_text()
    cursor = db.execute(insert_returning_id_sql('''INSERT INTO feedback_threads
        (user_id,source_type,source_id,lineup_id,title,content,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)''', db_kind()),
        (user_id, source_type, source_id, lineup_id, title, content,
         now, now))
    feedback_id = last_insert_id(cursor, db_kind())
    db.execute('''INSERT INTO feedback_events(thread_id,actor_user_id,actor_role,status,body,created_at)
        VALUES (?,?,'user','pending',?,?)''', (feedback_id, user_id, content, now))
    publish_notification(db, user_id, 'feedback', f'feedback:{feedback_id}', title,
                         '反馈已收到，后续进度和管理员回复会在这里更新。', lineup_id, feedback_id)
    return {'feedback_id': feedback_id, 'feedback_url': f'/me/feedback/{feedback_id}', 'status': 'pending'}


def feedback_detail(user, feedback_id):
    db = get_db()
    row = db.execute('SELECT * FROM feedback_threads WHERE id=?', (feedback_id,)).fetchone()
    if not row:
        return None, '反馈不存在', 404
    is_admin = bool(user and user['role'] == 'admin' and user['status'] == 'active')
    is_owner = bool(user and user['status'] == 'active' and row['user_id'] == user['id'])
    if not (is_admin or is_owner):
        return None, '反馈不存在或无权查看', 404
    item = {key: row[key] for key in ('id','source_type','source_id','lineup_id','title','content','status','revision','created_at','updated_at')}
    item['status_label'] = STATUS_LABELS[item['status']]
    item['events'] = [dict(r) for r in db.execute('''SELECT id,actor_role,status,body,created_at
        FROM feedback_events WHERE thread_id=? ORDER BY id''', (feedback_id,)).fetchall()]
    notice = db.execute("SELECT id,revision,notice_state FROM user_notifications WHERE feedback_id=? AND user_id=?",
                        (feedback_id, user['id'] if is_owner else -1)).fetchone()
    item['notification'] = {'id': f'notice:{notice["id"]}', 'revision': notice['revision'], 'notice_state': notice['notice_state']} if notice and notice['revision'] == row['revision'] else None
    item['can_reply'] = is_admin
    return item, None, 200


def update_feedback(db, admin, feedback_id, data):
    if not isinstance(data, dict) or type(data.get('revision')) is not int:
        return None, '请携带当前反馈版本', 400
    status = data.get('status')
    body = data.get('body', '')
    if not isinstance(status, str) or status not in STATUS_LABELS or not isinstance(body, str) or len(body.strip()) > 1000:
        return None, '处理状态无效或回复超过 1000 字', 400
    body = body.strip()
    if status in {'resolved','dismissed'} and not body:
        return None, '请填写处理结果，让用户知道原因', 400
    row = db.execute('SELECT * FROM feedback_threads WHERE id=?', (feedback_id,)).fetchone()
    if not row:
        return None, '反馈不存在', 404
    if status == row['status'] and not body:
        return None, '请填写回复或变更处理状态', 400
    now = now_text()
    cursor = db.execute('''UPDATE feedback_threads SET status=?, revision=revision+1, updated_at=?
        WHERE id=? AND revision=?''', (status, now, feedback_id, data['revision']))
    if not cursor.rowcount:
        return None, '反馈已被其他管理员更新，请刷新后再回复', 409
    message = body or f'处理进度已更新为：{STATUS_LABELS[status]}。'
    db.execute('''INSERT INTO feedback_events(thread_id,actor_user_id,actor_role,status,body,created_at)
        VALUES (?,?,'admin',?,?,?)''', (feedback_id, admin['id'], status, message, now))
    if row['source_type'] == 'report':
        legacy = status if status in {'resolved','dismissed'} else 'pending'
        db.execute('UPDATE reports SET status=?,handled_at=?,handled_by=? WHERE id=?',
                   (legacy, now if legacy != 'pending' else None, admin['id'] if legacy != 'pending' else None, row['source_id']))
        if data.get('hide_lineup') and status == 'resolved':
            db.execute("UPDATE lineups SET status='hidden',updated_at=?,version=version+1 WHERE id=? AND status IN ('normal','hidden')",
                       (now, row['lineup_id']))
    else:
        # Inbox read/archive status is independent from the public handling progress.
        db.execute("UPDATE guestbook_messages SET status=CASE WHEN status='unread' THEN 'read' ELSE status END, read_at=COALESCE(read_at,?),read_by=? WHERE id=?",
                   (now, admin['id'], row['source_id']))
    publish_notification(db, row['user_id'], 'feedback', f'feedback:{feedback_id}', row['title'],
                         f'{STATUS_LABELS[status]}：{message}', row['lineup_id'], feedback_id)
    write_audit(admin['id'], 'reply_feedback', 'feedback', feedback_id,
                before={'status': row['status'], 'revision': row['revision']},
                after={'status': status, 'body': message, 'revision': row['revision']+1})
    db.commit()
    return feedback_detail(admin, feedback_id)


def feedback_for_source(user, source, source_id):
    row = get_db().execute('SELECT id FROM feedback_threads WHERE source_type=? AND source_id=?', (source, source_id)).fetchone()
    if not row:
        return None, '该反馈尚无处理记录', 404
    return feedback_detail(user, row['id'])
