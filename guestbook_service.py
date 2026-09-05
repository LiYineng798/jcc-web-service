from db import get_db, now_text
from rate_limit import hit_limit


def create_message(user, data, ip):
    db = get_db()

    if hit_limit('guestbook', ip, 1, 10):
        return None, '留言过于频繁，请稍后再试', 429

    if user:
        nickname = (user['nickname'] or '').strip()
    else:
        nickname = str(data.get('nickname', '')).strip()

    content = str(data.get('content', '')).strip()

    if not nickname or len(nickname) > 20:
        return None, '昵称需为 1-20 位', 400
    if not content or len(content) > 500:
        return None, '留言内容需为 1-500 字', 400

    db.execute(
        '''INSERT INTO guestbook_messages (user_id, nickname, content, ip_address, created_at)
           VALUES (?, ?, ?, ?, ?)''',
        (user['id'] if user else None, nickname, content, ip, now_text()),
    )
    db.commit()
    return {'ok': True}, None, 201


def list_messages(db, page, page_size, status='active'):
    status = str(status or 'active').strip().lower()
    allowed = {'active', 'unread', 'read', 'archived', 'all'}
    if status not in allowed:
        status = 'active'
    where = ''
    params = []
    if status == 'active':
        where = " WHERE status != 'archived'"
    elif status != 'all':
        where = ' WHERE status = ?'
        params.append(status)
    total = db.execute(f'SELECT COUNT(*) AS c FROM guestbook_messages{where}', params).fetchone()['c']
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size
    query_params = [*params, page_size, offset]
    rows = db.execute(
        f'''SELECT id, user_id, nickname, content, ip_address, created_at,
                   status, read_at, archived_at
            FROM guestbook_messages{where}
            ORDER BY id DESC LIMIT ? OFFSET ?''',
        query_params,
    ).fetchall()
    unread_total = db.execute("SELECT COUNT(*) AS c FROM guestbook_messages WHERE status = 'unread'").fetchone()['c']
    return {
        'items': [dict(row) for row in rows],
        'total': total,
        'unread_total': unread_total,
        'status': status,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }


def delete_message(db, message_id):
    db.execute('DELETE FROM guestbook_messages WHERE id = ?', (message_id,))
    db.commit()
    return {'ok': True}, None, 200


def update_message_status(db, message_id, status, admin_id):
    status = str(status or '').strip().lower()
    if status not in {'read', 'archived', 'unread'}:
        return None, '无效的留言状态', 400
    row = db.execute(
        'SELECT id, status FROM guestbook_messages WHERE id = ?',
        (message_id,),
    ).fetchone()
    if not row:
        return None, '留言不存在', 404
    if status == 'archived' and row['status'] == 'unread':
        return None, '请先标记为已读，再归档留言', 400
    now = now_text()
    db.execute(
        '''UPDATE guestbook_messages
           SET status = ?,
               read_at = CASE WHEN ? = 'read' AND read_at IS NULL THEN ? ELSE read_at END,
               read_by = CASE WHEN ? = 'read' THEN ? ELSE read_by END,
               archived_at = CASE WHEN ? = 'archived' THEN ? WHEN ? != 'archived' THEN NULL ELSE archived_at END,
               archived_by = CASE WHEN ? = 'archived' THEN ? WHEN ? != 'archived' THEN NULL ELSE archived_by END
           WHERE id = ?''',
        (status, status, now, status, admin_id, status, now, status, status, admin_id, status, message_id),
    )
    db.commit()
    updated = db.execute(
        '''SELECT id, user_id, nickname, content, ip_address, created_at,
                  status, read_at, archived_at
           FROM guestbook_messages WHERE id = ?''',
        (message_id,),
    ).fetchone()
    return dict(updated), None, 200
