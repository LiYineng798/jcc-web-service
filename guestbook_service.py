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


def list_messages(db, page, page_size):
    total = db.execute('SELECT COUNT(*) AS c FROM guestbook_messages').fetchone()['c']
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size
    rows = db.execute(
        'SELECT id, user_id, nickname, content, ip_address, created_at FROM guestbook_messages ORDER BY id DESC LIMIT ? OFFSET ?',
        (page_size, offset),
    ).fetchall()
    return {
        'items': [dict(row) for row in rows],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }


def delete_message(db, message_id):
    db.execute('DELETE FROM guestbook_messages WHERE id = ?', (message_id,))
    db.commit()
    return {'ok': True}, None, 200
