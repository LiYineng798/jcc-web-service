"""Deck submissions: users send two game codes, an admin completes and publishes the deck.

Every state change is one optimistic update (``WHERE id = ? AND version = ?``) plus exactly one
history event with the new version, in the same transaction as any deck write, notification and
audit row. Nothing here trusts the client for identity, status, assignee or ranking fields.
"""
import base64
import hashlib
import json
import uuid

from audit import write_audit
from avatar_service import avatar_config
from db import db_kind, get_db, now_text
from db_adapter import INTEGRITY_ERRORS, insert_returning_id_sql, last_insert_id
from lineup_code import LINEUP_CODE_MESSAGE, extract_lineup_code
from notification_service import publish_notification
from orange_deck_service import (
    DeckError,
    apply_deck_update,
    card_season_id,
    card_version,
    deck_row,
    deck_season_choices,
    insert_deck,
    record_activity,
    serialize,
    _fields,
    validate_plan_code,
)
from rate_limit import hit_limit

ACTIVE = ('pending', 'processing', 'needs_info')
RESOLVED = ('published', 'rejected', 'duplicate', 'withdrawn')
TRANSITIONS = {
    'pending': {'processing', 'withdrawn'},
    'processing': {'pending', 'needs_info', 'published', 'rejected', 'duplicate'},
    'needs_info': {'pending', 'withdrawn'},
}
STATUS_LABELS = {'pending': '待处理', 'processing': '处理中', 'needs_info': '待补充', 'published': '已发布',
                 'rejected': '未采纳', 'duplicate': '已有相同卡组', 'withdrawn': '已撤回'}
ACTION_LABELS = {'submit': '提交投稿', 'update': '修改投稿', 'claim': '开始处理', 'release': '放回队列', 'assign': '转派处理人',
                 'save_draft': '保存完善草稿', 'request_info': '请求补充', 'resubmit': '补充后重新提交', 'publish': '完善并发布',
                 'reject': '未采纳', 'mark_duplicate': '判定重复', 'withdraw': '撤回投稿'}
# Only decisions that change what the submitter can expect produce a notification.
NOTIFY = {'processing': '管理员已开始完善你的卡组。', 'needs_info': '管理员需要你补充信息，补充后会继续处理。',
          'published': '你的卡组已完善并公开发布。', 'rejected': '这次投稿未被采纳，可以查看处理说明。',
          'duplicate': '卡组库中已有相同的卡组，可以查看对应卡组。'}
LIMITS = {'name': 24, 'note': 300, 'plan_code': 512, 'lineup_code': 20000, 'review_note': 1000}
ADMIN_FILTERS = {
    'pending': "s.status = 'pending'", 'processing': "s.status = 'processing'", 'needs_info': "s.status = 'needs_info'",
    'mine': "s.status = 'processing' AND s.assigned_admin_id = ?",
    'resolved': "s.status IN ('published', 'rejected', 'duplicate', 'withdrawn')", 'all': '1 = 1',
}
ADMIN_ORDER = {'pending': 's.created_at ASC, s.id ASC', 'needs_info': 's.updated_at ASC, s.id ASC',
               'processing': 's.updated_at ASC, s.id ASC', 'mine': 's.updated_at ASC, s.id ASC',
               'resolved': 's.resolved_at DESC, s.id DESC', 'all': 's.updated_at DESC, s.id DESC'}
SELECT = '''SELECT s.*, su.nickname AS submitter_nickname, su.username AS submitter_username,
    su.avatar_color AS submitter_avatar_color, su.avatar_preset AS submitter_avatar_preset,
    su.avatar_expression AS submitter_avatar_expression, au.nickname AS assignee_nickname,
    d.name AS deck_name, d.status AS deck_status, d.version AS deck_version,
    dd.name AS duplicate_name, dd.status AS duplicate_status
FROM orange_deck_submissions s JOIN users su ON su.id = s.submitter_user_id
LEFT JOIN users au ON au.id = s.assigned_admin_id
LEFT JOIN orange_decks d ON d.id = s.deck_id
LEFT JOIN orange_decks dd ON dd.id = s.duplicate_of_deck_id'''


class SubmissionError(DeckError):
    def __init__(self, message, status=400, **data):
        super().__init__(message, status)
        self.data = data


# ---------------------------------------------------------------- validation

def _text(data, key, default=''):
    value = data.get(key, default)
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise SubmissionError('内容格式无效')
    value = value.strip()
    if len(value) > LIMITS[key]:
        raise SubmissionError(f'内容过长：最多 {LIMITS[key]} 字')
    return value


def normalize_codes(plan_raw, lineup_raw):
    """Return (plan_code, plan_payload, lineup_code); both codes are required for a submission."""
    if not plan_raw:
        raise SubmissionError('请粘贴游戏方案码')
    if not lineup_raw:
        raise SubmissionError('请粘贴游戏阵容码')
    plan_code = validate_plan_code(plan_raw)
    encoded = plan_code.rpartition('-大橘大利-')[2]
    # The name is not part of the code; the payload is re-encoded canonically after strict decoding.
    payload = base64.b64encode(base64.b64decode(encoded, validate=True)).decode('ascii')
    lineup_code = extract_lineup_code(lineup_raw)
    if not lineup_code:
        raise SubmissionError(LINEUP_CODE_MESSAGE)
    return plan_code, payload, lineup_code


def fingerprint(season_id, plan_payload, lineup_code):
    value = json.dumps([season_id, plan_payload, lineup_code], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _request_key(value):
    try:
        return str(uuid.UUID(str(value or '')))
    except ValueError:
        raise SubmissionError('提交标识无效，请刷新页面后重试')


def _user_fields(data, existing=None):
    data = data if isinstance(data, dict) else {}
    keep = lambda key: existing[key] if existing is not None else ''
    name = _text(data, 'name', keep('name'))
    note = _text(data, 'note', keep('note'))
    plan_code, payload, lineup_code = normalize_codes(_text(data, 'plan_code', keep('plan_code')),
                                                       _text(data, 'lineup_code', keep('lineup_code')))
    return {'name': name, 'note': note, 'plan_code': plan_code, 'lineup_code': lineup_code}, payload


def _season():
    season_id = card_season_id()
    if season_id not in deck_season_choices():
        raise SubmissionError('当前赛季暂未开放卡组投稿', 409)
    return season_id


# ---------------------------------------------------------------- serialization

def _row(submission_id):
    return get_db().execute(f'{SELECT} WHERE s.id = ?', (submission_id,)).fetchone()


def _events(db, submission_id, admin_view):
    rows = db.execute('''SELECT e.*, u.nickname AS actor_nickname, u.role AS actor_role
        FROM orange_deck_submission_events e LEFT JOIN users u ON u.id = e.actor_user_id
        WHERE e.submission_id = ? ORDER BY e.submission_version, e.id''', (submission_id,)).fetchall()
    events = []
    for row in rows:
        by_admin = row['action'] not in ('submit', 'update', 'resubmit', 'withdraw')
        event = {'action': row['action'], 'label': ACTION_LABELS[row['action']], 'from_status': row['from_status'],
                 'to_status': row['to_status'], 'version': row['submission_version'], 'note': row['note'],
                 'created_at': row['created_at'], 'actor': ('管理员' if by_admin else '我')}
        if admin_view:
            event['actor'] = row['actor_nickname'] or '已删除账号'
            payload = json.loads(row['payload_json'] or '{}')
            event['payload'] = {key: payload[key] for key in ('deck_id', 'deck_version', 'assigned_admin_id', 'duplicate_of_deck_id', 'changed') if key in payload}
        events.append(event)
    return events


def serialize_submission(row, viewer, admin_view=False):
    owner = viewer and row['submitter_user_id'] == viewer['id']
    editable = bool(owner) and row['status'] in ('pending', 'needs_info')
    data = {
        'id': row['id'], 'name': row['name'], 'title': row['name'] or f"卡组投稿 #{row['id']}",
        'plan_code': row['plan_code'], 'lineup_code': row['lineup_code'], 'note': row['note'],
        'season_id': row['season_id'], 'status': row['status'], 'status_label': STATUS_LABELS[row['status']],
        'review_note': row['review_note'] if row['status'] in ('needs_info', 'rejected', 'duplicate', 'published') else '',
        'version': row['version'], 'created_at': row['created_at'], 'updated_at': row['updated_at'], 'resolved_at': row['resolved_at'],
        'can_edit': editable, 'can_withdraw': editable, 'url': f"/me/deck-submissions/{row['id']}",
        'deck': None, 'duplicate_of': None,
    }
    # The public result, once accepted; a later hidden/deleted deck keeps the accepted history.
    if row['status'] == 'published' and row['deck_id']:
        data['deck'] = {'id': row['deck_id'], 'name': row['deck_name'], 'status': row['deck_status'],
                        'detail_url': f"/orange-decks/{row['deck_id']}" if row['deck_status'] == 'published' else None}
    if row['status'] == 'duplicate':
        data['duplicate_of'] = {'id': row['duplicate_of_deck_id'], 'name': row['duplicate_name'],
                                'detail_url': f"/orange-decks/{row['duplicate_of_deck_id']}" if row['duplicate_status'] == 'published' else None}
    if admin_view:
        data.update({
            'review_note': row['review_note'],
            'submitter': {'id': row['submitter_user_id'], 'nickname': row['submitter_nickname'], 'username': row['submitter_username'],
                          'avatar_config': avatar_config({'id': row['submitter_user_id'], 'avatar_color': row['submitter_avatar_color'],
                                                          'avatar_preset': row['submitter_avatar_preset'],
                                                          'avatar_expression': row['submitter_avatar_expression']})},
            'assignee': {'id': row['assigned_admin_id'], 'nickname': row['assignee_nickname']} if row['assigned_admin_id'] else None,
            'draft': {'id': row['deck_id'], 'name': row['deck_name'], 'status': row['deck_status'], 'version': row['deck_version']} if row['deck_id'] else None,
            'mine': bool(viewer and row['assigned_admin_id'] == viewer['id']),
            'editor_url': f"/admin/deck-submissions/{row['id']}/edit",
        })
    return data


# ---------------------------------------------------------------- write helpers

def _event(db, submission_id, actor_id, action, from_status, to_status, version, note='', payload=None):
    db.execute('''INSERT INTO orange_deck_submission_events
        (submission_id, actor_user_id, action, from_status, to_status, submission_version, note, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (submission_id, actor_id, action, from_status, to_status, version, note,
         json.dumps(payload or {}, ensure_ascii=False, separators=(',', ':')), now_text()))


def _transition(db, row, actor, action, to_status, changes=None, note='', payload=None):
    """Apply one versioned state change and its event; raises 409 when someone else got there first."""
    if to_status != row['status'] and to_status not in TRANSITIONS.get(row['status'], set()):
        raise SubmissionError(f"投稿当前为「{STATUS_LABELS[row['status']]}」，不能执行该操作", 409)
    now = now_text()
    fields = {'status': to_status, 'updated_at': now, 'version': row['version'] + 1,
              'resolved_at': now if to_status in RESOLVED else None, **(changes or {})}
    cursor = db.execute(f"UPDATE orange_deck_submissions SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ? AND version = ?",
                        [*fields.values(), row['id'], row['version']])
    if not cursor.rowcount:
        raise SubmissionError('投稿已被更新，请刷新后再操作', 409)
    _event(db, row['id'], actor['id'], action, row['status'], to_status, fields['version'], note, payload)
    if to_status != row['status'] and to_status in NOTIFY and actor['id'] != row['submitter_user_id']:
        title = row['name'] or f"卡组投稿 #{row['id']}"
        publish_notification(db, row['submitter_user_id'], 'deck_submission', f"deck_submission:{row['id']}",
                             title, NOTIFY[to_status], deck_submission_id=row['id'])
    return fields['version']


def _check_version(row, data):
    if not isinstance(data, dict) or type(data.get('version')) is not int:
        raise SubmissionError('缺少投稿版本，请刷新后再操作')
    if data['version'] != row['version']:
        raise SubmissionError('投稿已被更新，请刷新后再操作', 409, current_version=row['version'])


def _run(work):
    db = get_db()
    try:
        result = work(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------- submitter

def _same_content(row, fields, season_id, code_fingerprint):
    return (row['season_id'], row['code_fingerprint'], row['name'], row['note']) == (season_id, code_fingerprint, fields['name'], fields['note'])


def _existing_for_request(db, user, request_key, fields, season_id, code_fingerprint):
    row = db.execute(f'{SELECT} WHERE s.submitter_user_id = ? AND s.request_key = ?', (user['id'], request_key)).fetchone()
    if row is None:
        return None
    if not _same_content(row, fields, season_id, code_fingerprint):
        raise SubmissionError('这个提交标识已用于另一份内容，请刷新页面后重新提交', 409, submission_id=row['id'])
    return row


def _active_duplicate(db, user_id, season_id, code_fingerprint, exclude=None):
    row = db.execute(f"""SELECT id FROM orange_deck_submissions WHERE submitter_user_id = ? AND season_id = ?
        AND code_fingerprint = ? AND status IN ('pending', 'processing', 'needs_info') AND id <> ?""",
        (user_id, season_id, code_fingerprint, exclude or 0)).fetchone()
    if row:
        raise SubmissionError('你已经提交过相同的方案码和阵容码，正在处理中', 409, submission_id=row['id'])


def create_submission(user, data):
    """Idempotent per request key: a retried request returns the original submission (replayed=True)."""
    data = data if isinstance(data, dict) else {}
    request_key = _request_key(data.get('request_key'))
    season_id = _season()
    fields, payload = _user_fields(data)
    code_fingerprint = fingerprint(season_id, payload, fields['lineup_code'])
    db = get_db()
    existing = _existing_for_request(db, user, request_key, fields, season_id, code_fingerprint)
    if existing:
        return serialize_submission(existing, user), True
    _active_duplicate(db, user['id'], season_id, code_fingerprint)
    if hit_limit('deck_submission_create', str(user['id']), 10, 60):
        raise SubmissionError('提交过于频繁，请稍后再试', 429)
    now = now_text()
    try:
        cursor = db.execute(insert_returning_id_sql('''INSERT INTO orange_deck_submissions
            (submitter_user_id, season_id, name, plan_code, lineup_code, note, code_fingerprint, request_key, status, version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1, ?, ?)''', db_kind()),
            (user['id'], season_id, fields['name'], fields['plan_code'], fields['lineup_code'], fields['note'],
             code_fingerprint, request_key, now, now))
        submission_id = last_insert_id(cursor, db_kind())
        _event(db, submission_id, user['id'], 'submit', None, 'pending', 1, payload=fields)
        db.commit()
    except INTEGRITY_ERRORS:
        # A concurrent retry or an identical active submission won the unique key.
        db.rollback()
        existing = _existing_for_request(db, user, request_key, fields, season_id, code_fingerprint)
        if existing:
            return serialize_submission(existing, user), True
        _active_duplicate(db, user['id'], season_id, code_fingerprint)
        raise
    return serialize_submission(_row(submission_id), user), False


def _own(user, submission_id):
    row = _row(submission_id)
    if row is None or row['submitter_user_id'] != user['id']:
        raise SubmissionError('投稿不存在', 404)
    return row


def list_mine(user, status='all', page=1, page_size=10):
    scopes = {'all': '1 = 1', 'active': "s.status IN ('pending', 'processing', 'needs_info')",
              'resolved': "s.status IN ('published', 'rejected', 'duplicate', 'withdrawn')"}
    if status not in scopes:
        raise SubmissionError('筛选条件无效')
    page_size, page = max(1, min(int(page_size), 30)), max(1, int(page))
    db = get_db()
    where = f'WHERE s.submitter_user_id = ? AND {scopes[status]}'
    total = db.execute(f'SELECT COUNT(*) AS c FROM orange_deck_submissions s {where}', (user['id'],)).fetchone()['c']
    rows = db.execute(f'{SELECT} {where} ORDER BY s.updated_at DESC, s.id DESC LIMIT ? OFFSET ?',
                      (user['id'], page_size, (page - 1) * page_size)).fetchall()
    counts = {row['status']: row['c'] for row in db.execute(
        'SELECT status, COUNT(*) AS c FROM orange_deck_submissions WHERE submitter_user_id = ? GROUP BY status', (user['id'],)).fetchall()}
    return {'items': [serialize_submission(row, user) for row in rows], 'total': total, 'page': page, 'page_size': page_size,
            'total_pages': max(1, -(-total // page_size)), 'counts': counts}


def detail_for_submitter(user, submission_id):
    row = _own(user, submission_id)
    db = get_db()
    notice = db.execute('''SELECT id, revision, notice_state FROM user_notifications
        WHERE user_id = ? AND kind = 'deck_submission' AND deck_submission_id = ?''', (user['id'], submission_id)).fetchone()
    return {**serialize_submission(row, user), 'events': _events(db, submission_id, False),
            'notification': {'id': f"notice:{notice['id']}", 'revision': notice['revision'], 'notice_state': notice['notice_state']} if notice else None}


def update_by_submitter(user, submission_id, data):
    row = _own(user, submission_id)
    _check_version(row, data)
    if row['status'] not in ('pending', 'needs_info'):
        raise SubmissionError('管理员正在处理或投稿已结束，暂时不能修改', 409)
    fields, payload = _user_fields(data, existing=row)
    code_fingerprint = fingerprint(row['season_id'], payload, fields['lineup_code'])
    changed = [key for key in fields if fields[key] != row[key]]
    resubmit = row['status'] == 'needs_info'
    if not changed and not resubmit:
        return serialize_submission(row, user)

    def work(db):
        _active_duplicate(db, user['id'], row['season_id'], code_fingerprint, exclude=row['id'])
        _transition(db, row, user, 'resubmit' if resubmit else 'update', 'pending',
                    changes={**fields, 'code_fingerprint': code_fingerprint},
                    payload={'changed': changed, **{key: fields[key] for key in changed}})
    try:
        _run(work)
    except INTEGRITY_ERRORS:
        _active_duplicate(get_db(), user['id'], row['season_id'], code_fingerprint, exclude=row['id'])
        raise
    return serialize_submission(_row(submission_id), user)


def withdraw(user, submission_id, data):
    row = _own(user, submission_id)
    _check_version(row, data)
    if row['status'] not in ('pending', 'needs_info'):
        raise SubmissionError('管理员正在处理或投稿已结束，暂时不能撤回', 409)
    # Any completion draft stays private; it is never published from a withdrawn submission.
    _run(lambda db: _transition(db, row, user, 'withdraw', 'withdrawn'))
    return serialize_submission(_row(submission_id), user)


# ---------------------------------------------------------------- admin

def admin_list(admin, status='pending', query='', page=1, page_size=20):
    if status not in ADMIN_FILTERS:
        raise SubmissionError('筛选条件无效')
    clauses, params = [ADMIN_FILTERS[status]], [admin['id']] if status == 'mine' else []
    query = str(query or '').strip()[:40]
    if query:
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_').lower()
        like = "LIKE ? ESCAPE '\\'"
        clauses.append(f'(LOWER(s.name) {like} OR LOWER(su.nickname) {like} OR LOWER(su.username) {like} OR CAST(s.id AS TEXT) = ?)')
        params += [f'%{escaped}%'] * 3 + [query.lstrip('#')]
    page_size, page = max(1, min(int(page_size), 50)), max(1, int(page))
    db = get_db()
    where = f"WHERE {' AND '.join(clauses)}"
    total = db.execute(f'SELECT COUNT(*) AS c FROM orange_deck_submissions s JOIN users su ON su.id = s.submitter_user_id {where}',
                       params).fetchone()['c']
    rows = db.execute(f'{SELECT} {where} ORDER BY {ADMIN_ORDER[status]} LIMIT ? OFFSET ?',
                      params + [page_size, (page - 1) * page_size]).fetchall()
    counts = {row['status']: row['c'] for row in db.execute(
        'SELECT status, COUNT(*) AS c FROM orange_deck_submissions GROUP BY status').fetchall()}
    counts['mine'] = db.execute("SELECT COUNT(*) AS c FROM orange_deck_submissions WHERE status = 'processing' AND assigned_admin_id = ?",
                                (admin['id'],)).fetchone()['c']
    counts['resolved'] = sum(counts.get(key, 0) for key in RESOLVED)
    return {'items': [serialize_submission(row, admin, admin_view=True) for row in rows], 'total': total, 'page': page,
            'page_size': page_size, 'total_pages': max(1, -(-total // page_size)), 'counts': counts}


def _admin_row(submission_id):
    row = _row(submission_id)
    if row is None:
        raise SubmissionError('投稿不存在', 404)
    return row


def _possible_duplicates(db, row):
    """Same codes elsewhere; attribution is never moved automatically, an admin decides."""
    others = db.execute(f"""{SELECT} WHERE s.season_id = ? AND s.code_fingerprint = ? AND s.id <> ?
        ORDER BY s.created_at, s.id LIMIT 10""", (row['season_id'], row['code_fingerprint'], row['id'])).fetchall()
    encoded = row['plan_code'].rpartition('-大橘大利-')[2]
    decks = db.execute("""SELECT id, name, status FROM orange_decks WHERE season_id = ? AND status IN ('published', 'hidden')
        AND (lineup_code = ? OR plan_code LIKE ?) AND (? IS NULL OR id <> ?) ORDER BY published_at DESC, id DESC LIMIT 10""",
        (row['season_id'], row['lineup_code'], '%-大橘大利-' + encoded, row['deck_id'], row['deck_id'] or 0)).fetchall()
    return {
        'submissions': [{'id': o['id'], 'title': o['name'] or f"卡组投稿 #{o['id']}", 'status': o['status'],
                         'status_label': STATUS_LABELS[o['status']], 'submitter': o['submitter_nickname'],
                         'same_submitter': o['submitter_user_id'] == row['submitter_user_id']} for o in others],
        'decks': [{'id': d['id'], 'name': d['name'], 'status': d['status'], 'detail_url': f"/orange-decks/{d['id']}"} for d in decks],
    }


def admin_detail(admin, submission_id):
    row = _admin_row(submission_id)
    db = get_db()
    draft = None
    if row['deck_id']:
        deck = deck_row(row['deck_id'], admin)
        draft = serialize(deck, admin, detail=True) if deck is not None else None
    admins = [{'id': a['id'], 'nickname': a['nickname']} for a in db.execute(
        "SELECT id, nickname FROM users WHERE role = 'admin' AND status = 'active' ORDER BY id").fetchall()]
    return {**serialize_submission(row, admin, admin_view=True), 'events': _events(db, submission_id, True),
            'deck_detail': draft, 'possible_duplicates': _possible_duplicates(db, row), 'admins': admins,
            'current_season_id': card_season_id()}


def _require_assignee(row, admin):
    if row['status'] != 'processing':
        raise SubmissionError(f"投稿当前为「{STATUS_LABELS[row['status']]}」，请先认领", 409)
    if row['assigned_admin_id'] != admin['id']:
        raise SubmissionError(f"该投稿正由{row['assignee_nickname'] or '其他管理员'}处理，请先转派给自己", 409)


def _note(data, required, label, key='note'):
    note = str((data or {}).get(key) or '').strip()
    if len(note) > LIMITS['review_note']:
        raise SubmissionError(f"说明最多 {LIMITS['review_note']} 字")
    if required and len(note) < 2:
        raise SubmissionError(f'请填写{label}（2–1000 字，投稿人可见）')
    return note


def admin_act(admin, submission_id, action, data):
    data = data if isinstance(data, dict) else {}
    row = _admin_row(submission_id)
    _check_version(row, data)

    def work(db):
        audit = {}
        if action == 'claim':
            if row['status'] != 'pending':
                raise SubmissionError('只有待处理的投稿可以认领', 409)
            _transition(db, row, admin, 'claim', 'processing', changes={'assigned_admin_id': admin['id']})
        elif action == 'release':
            _require_assignee(row, admin)
            _transition(db, row, admin, 'release', 'pending', changes={'assigned_admin_id': None}, note=_note(data, False, ''))
        elif action == 'assign':
            target = data.get('admin_id')
            target_row = db.execute("SELECT id FROM users WHERE id = ? AND role = 'admin' AND status = 'active'",
                                    (target if type(target) is int else -1,)).fetchone()
            if target_row is None:
                raise SubmissionError('请选择有效的管理员')
            if row['status'] not in ('pending', 'processing'):
                raise SubmissionError('只有待处理或处理中的投稿可以转派', 409)
            if row['status'] == 'processing' and row['assigned_admin_id'] == target:
                raise SubmissionError('该投稿已由这位管理员处理', 409)
            _transition(db, row, admin, 'assign', 'processing', changes={'assigned_admin_id': target},
                        payload={'assigned_admin_id': target, 'previous_admin_id': row['assigned_admin_id']})
            audit = {'assigned_admin_id': target}
        elif action == 'request_info':
            _require_assignee(row, admin)
            note = _note(data, True, '需要补充的内容')
            _transition(db, row, admin, 'request_info', 'needs_info', changes={'review_note': note}, note=note)
        elif action == 'reject':
            _require_assignee(row, admin)
            note = _note(data, True, '未采纳原因')
            _transition(db, row, admin, 'reject', 'rejected', changes={'review_note': note}, note=note)
        elif action == 'duplicate':
            _require_assignee(row, admin)
            target = data.get('duplicate_of_deck_id')
            deck = db.execute('SELECT id, status, season_id FROM orange_decks WHERE id = ?',
                              (target if type(target) is int else -1,)).fetchone()
            if deck is None or deck['status'] != 'published' or deck['season_id'] != row['season_id'] or deck['id'] == row['deck_id']:
                raise SubmissionError('重复对象必须是同赛季、当前公开的另一套卡组')
            note = _note(data, False, '')
            _transition(db, row, admin, 'mark_duplicate', 'duplicate', changes={'duplicate_of_deck_id': deck['id'], 'review_note': note},
                        note=note, payload={'duplicate_of_deck_id': deck['id']})
            audit = {'duplicate_of_deck_id': deck['id']}
        else:
            raise SubmissionError('操作无效', 404)
        write_audit(admin['id'], f'deck_submission.{action}', 'deck_submission', target_id=row['id'],
                    before={'status': row['status'], 'assigned_admin_id': row['assigned_admin_id']},
                    after={'status': db.execute('SELECT status FROM orange_deck_submissions WHERE id = ?', (row['id'],)).fetchone()['status'], **audit})
    _run(work)
    return admin_detail(admin, submission_id)


def _deck_payload(data):
    """Editor fields only; ownership, attribution, status and review fields are always set here."""
    allowed = ('name', 'cards', 'portal', 'plan_code', 'lineup_code', 'note', 'key_rounds', 'alternatives', 'formation')
    return {key: data[key] for key in allowed if key in data}


def _write_deck(db, row, admin, data, publish):
    if row['season_id'] != card_season_id():
        raise SubmissionError('投稿所属赛季已不是当前时间卡片赛季，无法继续完善', 409)
    # A first save starts from what the submitter sent; the editor normally sends every field.
    fields_in = {'name': row['name'], 'note': row['note'], 'plan_code': row['plan_code'], 'lineup_code': row['lineup_code'],
                 **_deck_payload(data)} if row['deck_id'] is None else _deck_payload(data)
    now = now_text()
    if row['deck_id'] is None:
        status = 'published' if publish else 'draft'
        fields = _fields(fields_in, status)
        fields.update(user_id=admin['id'], origin_type='submission', provided_by_user_id=row['submitter_user_id'],
                      status=status, created_at=now, updated_at=now, forked_from_id=None,
                      published_at=now if publish else None)
        if publish:
            fields.update(published_by_user_id=admin['id'], reviewed_card_version=card_version(), reviewed_at=now)
        deck_id = insert_deck(db, fields)
        if publish:
            record_activity(db, deck_id, 'published', admin['id'])
        return deck_id, 1
    deck = deck_row(row['deck_id'], admin)
    if deck is None or deck['status'] != 'draft':
        raise SubmissionError('完善草稿状态异常，请刷新后再操作', 409)
    if data.get('deck_version') != deck['version']:
        raise SubmissionError('完善草稿已在其他页面保存，请刷新后再编辑', 409)
    extra = {'published_by_user_id': deck['published_by_user_id'] or admin['id'], 'reviewed_card_version': card_version(),
             'reviewed_at': now} if publish else None
    # Publishing re-validates the full public rules against current card data.
    version = apply_deck_update(db, deck, admin, fields_in, 'published' if publish else 'draft', extra=extra)
    return deck['id'], version


def save_draft(admin, submission_id, data):
    data = data if isinstance(data, dict) else {}
    row = _admin_row(submission_id)
    _check_version(row, data)
    _require_assignee(row, admin)

    def work(db):
        deck_id, deck_version = _write_deck(db, row, admin, data, publish=False)
        # The version lock means two first saves cannot both attach a new draft.
        _transition(db, row, admin, 'save_draft', 'processing', changes={'deck_id': deck_id},
                    payload={'deck_id': deck_id, 'deck_version': deck_version})
    _run(work)
    return admin_detail(admin, submission_id)


def publish(admin, submission_id, data):
    data = data if isinstance(data, dict) else {}
    row = _admin_row(submission_id)
    _check_version(row, data)
    _require_assignee(row, admin)
    # ``note`` is the deck's own description here; the message to the submitter is ``review_note``.
    note = _note(data, False, '', key='review_note')

    def work(db):
        deck_id, deck_version = _write_deck(db, row, admin, data, publish=True)
        _transition(db, row, admin, 'publish', 'published', changes={'deck_id': deck_id, 'review_note': note}, note=note,
                    payload={'deck_id': deck_id, 'deck_version': deck_version})
        write_audit(admin['id'], 'deck_submission.publish', 'deck_submission', target_id=row['id'],
                    before={'status': row['status']}, after={'status': 'published', 'deck_id': deck_id,
                                                             'provided_by_user_id': row['submitter_user_id']})
        return deck_id
    deck_id = _run(work)
    return {**admin_detail(admin, submission_id), 'published_deck_url': f'/orange-decks/{deck_id}'}


def queue_counts():
    rows = get_db().execute("""SELECT status, COUNT(*) AS c FROM orange_deck_submissions
        WHERE status IN ('pending', 'processing', 'needs_info') GROUP BY status""").fetchall()
    return {row['status']: row['c'] for row in rows}
