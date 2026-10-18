"""Private inbox; aggregation happens inside the originating write transaction."""
from admin_pagination import parse_page, parse_page_size
from db import get_db, now_text


def publish_notification(db, user_id, kind, group_key, title, body='', lineup_id=None, feedback_id=None):
    if user_id is None:
        return
    now = now_text()
    db.execute('''INSERT INTO user_notifications
        (user_id,kind,group_key,title,body,lineup_id,feedback_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id,group_key) DO UPDATE SET
          title=excluded.title, body=excluded.body, event_count=user_notifications.event_count+1,
          revision=user_notifications.revision+1, notice_state='unread', updated_at=excluded.updated_at''',
        (user_id, kind, group_key, title, body, lineup_id, feedback_id, now, now))


def notify_author(db, lineup, kind, actor=None):
    if actor and actor['id'] == lineup['user_id']:
        return
    if kind == 'favorite':
        inserted = db.execute('''INSERT INTO author_favorite_receipts(lineup_id,user_id) VALUES (?,?)
            ON CONFLICT(lineup_id,user_id) DO NOTHING''', (lineup['id'], actor['id']))
        if not inserted.rowcount:
            return
    publish_notification(db, lineup['user_id'], kind, f'{kind}:{lineup["id"]}',
                         lineup['name'], lineup_id=lineup['id'])


INBOX_SQL = '''
SELECT 'notice:' || CAST(n.id AS TEXT) AS id, n.user_id, n.kind,
       CASE WHEN n.kind='feedback' THEN 'feedback' ELSE 'interaction' END AS category,
       n.lineup_id, n.feedback_id, n.title AS name, n.body, n.event_count, n.read_count,
       n.revision, n.notice_state, n.updated_at,
       COALESCE(f.status,'') AS state, COALESCE(l.status,'') AS lineup_status
FROM user_notifications n LEFT JOIN feedback_threads f ON f.id=n.feedback_id
LEFT JOIN lineups l ON l.id=n.lineup_id
UNION ALL
SELECT 'moderation:' || CAST(m.lineup_id AS TEXT), l.user_id, 'moderation', 'moderation',
       m.lineup_id, NULL, l.name,
       CASE WHEN m.state='pending' THEN '修改已提交，管理员审核后会通知你。'
            WHEN m.review_note<>'' THEN m.review_note ELSE m.reason END,
       1, 0, m.revision, m.notice_state, m.updated_at, m.state, l.status
FROM lineup_moderation m JOIN lineups l ON l.id=m.lineup_id
'''


def serialize_notice(row):
    item = dict(row)
    item.pop("user_id", None)
    item['new_count'] = max(0, item['event_count'] - item['read_count'])
    if item['category'] == 'interaction':
        label = {'like': '赞', 'favorite': '收藏', 'copy': '有效复制'}[item['kind']]
        unit = '个' if item['kind']=='like' else '次'
        item['body'] = f'你的阵容累计收到 {item["event_count"]} {unit}{label}。'
        if item['notice_state'] == 'unread' and item['new_count']:
            item['body'] += f' 本次新增 {item["new_count"]} {unit}。'
    item['url'] = (f'/me/feedback/{item["feedback_id"]}' if item['kind'] == 'feedback' else
                   f'/me/lineup-notifications/{item["lineup_id"]}' if item['kind'] == 'moderation' else
                   f'/lineup/{item["lineup_id"]}' if item['lineup_status'] != 'deleted' else '')
    return item


def list_inbox(user, args):
    status, category = args.get('status', 'all'), args.get('category', 'all')
    if status not in {'all','unread','read'} or category not in {'all','feedback','interaction','moderation'}:
        return None, '通知筛选无效', 400
    db = get_db()
    scope = f'FROM ({INBOX_SQL}) inbox WHERE user_id=?'
    params = [user['id']]
    if category != 'all':
        scope += ' AND category=?'
        params.append(category)
    counts = {r['notice_state']: r['c'] for r in db.execute(
        'SELECT notice_state, COUNT(*) AS c ' + scope + ' GROUP BY notice_state', params).fetchall()}
    total_unread = db.execute(f"SELECT COUNT(*) AS c FROM ({INBOX_SQL}) inbox WHERE user_id=? AND notice_state='unread'",
                             (user['id'],)).fetchone()['c']
    if status != 'all':
        scope += ' AND notice_state=?'
        params.append(status)
    total = db.execute('SELECT COUNT(*) AS c ' + scope, params).fetchone()['c']
    size = parse_page_size(args, default=10, maximum=50)
    pages = max(1, (total + size - 1) // size)
    page = min(parse_page(args), pages)
    rows = db.execute('SELECT * ' + scope + ' ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?',
                      [*params, size, (page-1)*size]).fetchall()
    return {'items': [serialize_notice(r) for r in rows], 'counts': counts, 'unread_total': total_unread,
            'total': total, 'page': page, 'total_pages': pages, 'page_size': size}, None, 200


def mark_notice(user, key, data):
    if key.startswith('moderation:') and key[11:].isdigit():
        from lineup_moderation_service import update_notification
        return update_notification(user, int(key[11:]), data)
    if not key.startswith('notice:') or not key[7:].isdigit():
        return None, '通知不存在', 404
    if not isinstance(data, dict) or not isinstance(data.get('status'), str) or data.get('status') not in {'read','unread'} or type(data.get('revision')) is not int:
        return None, '通知状态或版本无效', 400
    db = get_db()
    cursor = db.execute('''UPDATE user_notifications SET notice_state=?,
        read_count=CASE WHEN ?='read' THEN event_count ELSE read_count END
        WHERE id=? AND user_id=? AND revision=?''',
        (data['status'], data['status'], int(key[7:]), user['id'], data['revision']))
    if not cursor.rowcount:
        return None, '通知已有更新，请刷新后再操作', 409
    db.commit()
    return {'ok': True}, None, 200
