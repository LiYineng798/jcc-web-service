"""Transactional ban/revision/review lifecycle. Original content stays immutable in review."""
import json

from admin_pagination import paginate_rows, parse_page, parse_page_size
from audit import write_audit
from db import get_db, now_text
from lineups_utils import lineup_row

RESTRICTED_STATES = {'banned', 'pending', 'rejected'}
CONTENT_FIELDS = ('name', 'code', 'season_id')


def content(row):
    return {key: row[key] for key in CONTENT_FIELDS}


def moderation_row(lineup_id):
    return get_db().execute('SELECT * FROM lineup_moderation WHERE lineup_id = ?', (lineup_id,)).fetchone()


def has_restricted_code(user_id, code, exclude_id=0):
    return bool(get_db().execute(
        "SELECT id FROM lineups WHERE user_id=? AND code=? AND status='banned' AND id!=? LIMIT 1",
        (user_id, code, exclude_id),
    ).fetchone())


def moderation_payload(row):
    if not row:
        return None
    result = dict(row)
    result['proposal'] = ({key: result.pop('proposed_' + key) for key in CONTENT_FIELDS}
                          if row['proposed_name'] is not None else None)
    for key in CONTENT_FIELDS:
        result.pop('proposed_' + key, None)
    return result


def moderation_detail(user, lineup_id):
    row = lineup_row(lineup_id)
    if not row or (row['user_id'] != user['id'] and user['role'] != 'admin'):
        return None, '阵容不存在', 404
    events = get_db().execute(
        'SELECT id, action, reason, before_json, after_json, created_at FROM lineup_moderation_events WHERE lineup_id = ? ORDER BY id DESC',
        (lineup_id,),
    ).fetchall()
    return {
        'lineup': {**content(row), 'id': row['id'], 'version': row['version'], 'status': row['status']},
        'moderation': moderation_payload(moderation_row(lineup_id)),
        'events': [{**{key: event[key] for key in ('id', 'action', 'reason', 'created_at')},
                    'before': json.loads(event['before_json']), 'after': json.loads(event['after_json'])} for event in events],
    }, None, 200


def claim_lineup(row, data, assignments=None, require_version=True):
    """CAS also guards legacy edit/hide/delete paths against concurrent moderation."""
    version = data.get('version', None if require_version else row['version'])
    if type(version) is not int or version != row['version']:
        return False
    values = dict(assignments or {})
    values['updated_at'] = now_text()
    cursor = get_db().execute(
        'UPDATE lineups SET ' + ', '.join(f'{key} = ?' for key in values)
        + ', version = version + 1 WHERE id = ? AND version = ? AND status = ?',
        [*values.values(), row['id'], version, row['status']],
    )
    return cursor.rowcount == 1


def _conflict():
    get_db().rollback()
    return None, '阵容或审核状态已变化，请刷新后重试', 409


def _record(user, row, action, reason):
    updated = lineup_row(row['id'])
    before, after = content(row), content(updated)
    if action == 'submit':
        after = moderation_payload(moderation_row(row['id']))['proposal']
    get_db().execute(
        '''INSERT INTO lineup_moderation_events
           (lineup_id, actor_user_id, action, reason, before_json, after_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (row['id'], user['id'], action, reason, json.dumps(before, ensure_ascii=False),
         json.dumps(after, ensure_ascii=False), now_text()),
    )
    write_audit(user['id'], 'lineup_' + action, 'lineup', row['id'],
                before={**before, 'status': row['status']},
                after={**after, 'status': updated['status'], 'reason': reason})
    get_db().commit()
    return moderation_detail(user, row['id'])


def moderate_lineup(user, lineup_id, action, data):
    if user['role'] != 'admin':
        return None, '需要管理员权限', 403
    if not isinstance(data, dict):
        return None, '请求格式无效', 400
    if action not in {'ban', 'approve', 'reject', 'release'}:
        return None, '操作无效', 400
    row = lineup_row(lineup_id)
    if not row or row['status'] == 'deleted':
        return None, '阵容不存在', 404
    reason = data.get('reason', '')
    if not isinstance(reason, str) or len(reason.strip()) > 500 or (action != 'approve' and not reason.strip()):
        return None, '请填写 1–500 字原因', 400
    reason = reason.strip()
    moderation = moderation_row(lineup_id)
    db, now = get_db(), now_text()
    if action == 'ban':
        if row['status'] not in {'normal', 'hidden'}:
            return _conflict()
        if not claim_lineup(row, data, {'status': 'banned'}):
            return _conflict()
        db.execute(
            '''INSERT INTO lineup_moderation (lineup_id, state, reason, prior_status, created_at, updated_at)
               VALUES (?, 'banned', ?, ?, ?, ?)
               ON CONFLICT(lineup_id) DO UPDATE SET state='banned', reason=excluded.reason,
               prior_status=excluded.prior_status, proposed_name=NULL, proposed_code=NULL, proposed_season_id=NULL,
               review_note='', notice_state='unread', revision=lineup_moderation.revision+1,
               created_at=excluded.created_at, updated_at=excluded.updated_at, submitted_at=NULL, reviewed_at=NULL''',
            (lineup_id, reason, row['status'], now, now),
        )
    else:
        allowed = {'pending'} if action in {'approve', 'reject'} else {'banned', 'rejected'}
        if row['status'] != 'banned' or not moderation or moderation['state'] not in allowed:
            return _conflict()
        assignments = {}
        if action in {'approve', 'release'}:
            assignments['status'] = moderation['prior_status']
        if action == 'approve':
            from lineup_write_service import validate_lineup_payload
            proposal = {key: moderation['proposed_' + key] for key in CONTENT_FIELDS}
            payload, validation_error = validate_lineup_payload(proposal)
            if validation_error:
                return None, '提交内容已不可用：' + validation_error + '。请退回后让用户重新修改。', 400
            assignments.update({key: payload[key] for key in CONTENT_FIELDS})
        if not claim_lineup(row, data, assignments):
            return _conflict()
        db.execute(
            '''UPDATE lineup_moderation SET state=?, review_note=?, notice_state='unread',
               revision=revision+1, reviewed_at=?, updated_at=? WHERE lineup_id=?''',
            ({'approve': 'approved', 'reject': 'rejected', 'release': 'released'}[action], reason, now, now, lineup_id),
        )
    return _record(user, row, action, reason)


def submit_revision(user, lineup_id, data):
    if not isinstance(data, dict):
        return None, '请求格式无效', 400
    row = lineup_row(lineup_id)
    if not row or row['user_id'] != user['id']:
        return None, '阵容不存在', 404
    moderation = moderation_row(lineup_id)
    if row['status'] != 'banned' or not moderation or moderation['state'] not in {'banned', 'rejected'}:
        return _conflict()
    if set(data) - {*CONTENT_FIELDS, 'version'}:
        return None, '仅可修改名称、阵容码和所属赛季', 400
    from lineup_write_service import validate_lineup_payload
    payload, validation_error = validate_lineup_payload(data)
    if validation_error:
        return None, validation_error, 400
    if has_restricted_code(user['id'], payload['code'], lineup_id):
        return None, '该阵容码对应另一条封禁记录，请先处理原记录', 409
    if content(payload) == content(row):
        return None, '请至少修改名称、阵容码或所属赛季中的一项', 400
    if not claim_lineup(row, data):
        return _conflict()
    get_db().execute(
        '''UPDATE lineup_moderation SET state='pending', proposed_name=?, proposed_code=?, proposed_season_id=?,
           review_note='', notice_state='read', revision=revision+1, submitted_at=?, reviewed_at=NULL, updated_at=?
           WHERE lineup_id=?''',
        (payload['name'], payload['code'], payload['season_id'], now_text(), now_text(), lineup_id),
    )
    return _record(user, row, 'submit', '')


def list_notifications(user, args):
    state = args.get('status', 'all')
    if state not in {'unread', 'read', 'all'}:
        return None, '通知状态无效', 400
    from_sql = 'FROM lineup_moderation m JOIN lineups l ON l.id=m.lineup_id WHERE l.user_id=?'
    params = [user['id']]
    if state != 'all':
        from_sql += ' AND m.notice_state=?'
        params.append(state)
    result = paginate_rows(
        get_db(), 'SELECT m.*, l.name, l.status AS lineup_status, l.version ' + from_sql + ' ORDER BY m.updated_at DESC, m.lineup_id DESC',
        'SELECT COUNT(*) AS c ' + from_sql, params, parse_page(args), parse_page_size(args, default=10),
        serializer=moderation_payload,
    )
    counts = get_db().execute(
        'SELECT m.notice_state, COUNT(*) AS c FROM lineup_moderation m JOIN lineups l ON l.id=m.lineup_id WHERE l.user_id=? GROUP BY m.notice_state',
        (user['id'],),
    ).fetchall()
    result['counts'] = {r['notice_state']: r['c'] for r in counts}
    return result, None, 200


def update_notification(user, lineup_id, data):
    if not isinstance(data, dict) or data.get('status') not in {'unread', 'read'} or type(data.get('revision')) is not int:
        return None, '通知状态或版本无效', 400
    cursor = get_db().execute(
        '''UPDATE lineup_moderation SET notice_state=? WHERE lineup_id=? AND revision=?
           AND EXISTS (SELECT 1 FROM lineups WHERE id=? AND user_id=?)''',
        (data['status'], lineup_id, data['revision'], lineup_id, user['id']),
    )
    if not cursor.rowcount:
        return _conflict()
    get_db().commit()
    return {'ok': True}, None, 200


def attach_admin_moderation(payload):
    ids = [row['id'] for row in payload['items']]
    records = {}
    if ids:
        records = {row['lineup_id']: moderation_payload(row) for row in get_db().execute(
            'SELECT * FROM lineup_moderation WHERE lineup_id IN (' + ','.join('?' for _ in ids) + ')', ids,
        ).fetchall()}
    for row in payload['items']:
        row['moderation'] = records.get(row['id'])
    return payload
