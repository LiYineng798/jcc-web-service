import json

from audit import write_audit
from db import db_kind, now_text
from db_adapter import insert_returning_id_sql, last_insert_id, upsert_setting_sql


NOTICE_FIELDS = ['title', 'message', 'link_url', 'link_text', 'jump_season_id', 'jump_tab', 'marquee_enabled']

VALID_JUMP_TABS = {'', 'live', 'latest', 'hot', 'rising', 'recommended', 'ss'}


def _load_notice_data(db):
    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'notice_data'"
    ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row['setting_value'])
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _is_notice_enabled(db):
    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'notice_enabled'"
    ).fetchone()
    return row['setting_value'] == 'true' if row else False


def _serialize_notice(row):
    return {
        'id': row['id'],
        'title': row['title'],
        'message': row['message'],
        'link_url': row['link_url'],
        'link_text': row['link_text'],
        'jump_season_id': row['jump_season_id'] if 'jump_season_id' in row.keys() else '',
        'jump_tab': row['jump_tab'] if 'jump_tab' in row.keys() else '',
        'marquee_enabled': bool(row['marquee_enabled']) if 'marquee_enabled' in row.keys() else True,
        'is_active': bool(row['is_active']),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def _active_notice_row(db):
    return db.execute(
        '''
        SELECT id, title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at
        FROM site_notices
        WHERE is_active = 1
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        '''
    ).fetchone()


def _set_notice_enabled(db, enabled, now):
    db.execute(
        upsert_setting_sql(db_kind()),
        ('notice_enabled', 'true' if enabled else 'false', now),
    )


def _validate_notice_payload(data, existing=None):
    if not isinstance(data, dict):
        return None, '无效的请求数据'

    existing = existing or {}
    values = {}
    for field in NOTICE_FIELDS:
        values[field] = str(data.get(field, existing.get(field, ''))).strip()

    if not values['title']:
        return None, '标题不能为空'
    if not values['message']:
        return None, '内容不能为空'
    if values['jump_tab'] not in VALID_JUMP_TABS:
        return None, '无效的跳转目标'
    return values, None


def _write_notice_data_setting(db, notice, now):
    notice_data = json.dumps({
        'title': notice['title'],
        'message': notice['message'],
        'link_url': notice.get('link_url', ''),
        'link_text': notice.get('link_text', ''),
        'jump_season_id': notice.get('jump_season_id', ''),
        'jump_tab': notice.get('jump_tab', ''),
        'marquee_enabled': notice.get('marquee_enabled', True),
    }, ensure_ascii=False)
    db.execute(upsert_setting_sql(db_kind()), ('notice_data', notice_data, now))


def get_notice(db):
    """Return active notice content regardless of enabled state (used by admin)."""
    row = _active_notice_row(db)
    if row:
        return _serialize_notice(row)
    data = _load_notice_data(db)
    return {
        'id': None,
        'title': str(data.get('title', '')),
        'message': str(data.get('message', '')),
        'link_url': str(data.get('link_url', '')),
        'link_text': str(data.get('link_text', '')),
        'jump_season_id': '',
        'jump_tab': '',
        'marquee_enabled': True,
        'is_active': False,
        'created_at': '',
        'updated_at': '',
    }


def list_notices(db):
    rows = db.execute(
        '''
        SELECT id, title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at
        FROM site_notices
        ORDER BY updated_at DESC, id DESC
        '''
    ).fetchall()
    return [_serialize_notice(row) for row in rows]


def get_active_notice(db):
    """Return notice content only when enabled (used by public site)."""
    if not _is_notice_enabled(db):
        return None
    row = _active_notice_row(db)
    if not row:
        return None
    notice = _serialize_notice(row)
    if not notice['title'] or not notice['message']:
        return None
    return {
        'title': notice['title'],
        'message': notice['message'],
        'link_url': notice['link_url'],
        'link_text': notice['link_text'],
        'jump_season_id': notice['jump_season_id'],
        'jump_tab': notice['jump_tab'],
        'marquee_enabled': notice['marquee_enabled'],
    }


def create_notice(db, actor_user_id, data):
    values, error = _validate_notice_payload(data)
    if error:
        return None, error, 400

    now = now_text()
    marquee = 1 if values.get('marquee_enabled', 'true') not in ('false', '0', '') else 0
    cursor = db.execute(
        insert_returning_id_sql(
            '''
            INSERT INTO site_notices (title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ''',
            db_kind(),
        ),
        (values['title'], values['message'], values['link_url'], values['link_text'],
         values['jump_season_id'], values['jump_tab'], marquee, now, now),
    )
    notice_id = last_insert_id(cursor, db_kind())
    row = db.execute(
        '''
        SELECT id, title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at
        FROM site_notices
        WHERE id = ?
        ''',
        (notice_id,),
    ).fetchone()
    notice = _serialize_notice(row)
    write_audit(actor_user_id, 'create_notice', 'site_notice', notice_id, after=notice)
    db.commit()
    return notice, None, 201


def update_saved_notice(db, actor_user_id, notice_id, data):
    row = db.execute(
        'SELECT id, title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at FROM site_notices WHERE id = ?',
        (notice_id,),
    ).fetchone()
    if not row:
        return None, '通知不存在', 404
    before = _serialize_notice(row)
    values, error = _validate_notice_payload(data, before)
    if error:
        return None, error, 400

    now = now_text()
    marquee = 1 if values.get('marquee_enabled', 'true') not in ('false', '0', '') else 0
    db.execute(
        '''
        UPDATE site_notices
        SET title = ?, message = ?, link_url = ?, link_text = ?, jump_season_id = ?, jump_tab = ?, marquee_enabled = ?, updated_at = ?
        WHERE id = ?
        ''',
        (values['title'], values['message'], values['link_url'], values['link_text'],
         values['jump_season_id'], values['jump_tab'], marquee, now, notice_id),
    )
    row = db.execute(
        'SELECT id, title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at FROM site_notices WHERE id = ?',
        (notice_id,),
    ).fetchone()
    after = _serialize_notice(row)
    if after['is_active']:
        _write_notice_data_setting(db, after, now)
    write_audit(actor_user_id, 'update_saved_notice', 'site_notice', notice_id, before=before, after=after)
    db.commit()
    return after, None, 200


def delete_saved_notice(db, actor_user_id, notice_id):
    row = db.execute(
        'SELECT id, title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at FROM site_notices WHERE id = ?',
        (notice_id,),
    ).fetchone()
    if not row:
        return None, '通知不存在', 404
    before = _serialize_notice(row)
    now = now_text()
    db.execute('DELETE FROM site_notices WHERE id = ?', (notice_id,))
    if before['is_active']:
        _set_notice_enabled(db, False, now)
    write_audit(actor_user_id, 'delete_saved_notice', 'site_notice', notice_id, before=before)
    db.commit()
    return {'ok': True}, None, 200


def activate_notice(db, actor_user_id, notice_id):
    row = db.execute(
        'SELECT id, title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at FROM site_notices WHERE id = ?',
        (notice_id,),
    ).fetchone()
    if not row:
        return None, '通知不存在', 404

    before_items = list_notices(db)
    now = now_text()
    db.execute('UPDATE site_notices SET is_active = 0 WHERE is_active = 1')
    db.execute('UPDATE site_notices SET is_active = 1, updated_at = ? WHERE id = ?', (now, notice_id))
    _set_notice_enabled(db, True, now)
    after_row = db.execute(
        'SELECT id, title, message, link_url, link_text, jump_season_id, jump_tab, marquee_enabled, is_active, created_at, updated_at FROM site_notices WHERE id = ?',
        (notice_id,),
    ).fetchone()
    after = _serialize_notice(after_row)
    _write_notice_data_setting(db, after, now)
    write_audit(actor_user_id, 'activate_notice', 'site_notice', notice_id, before=before_items, after=after)
    db.commit()
    return after, None, 200


def save_notice(db, actor_user_id, data):
    if not isinstance(data, dict):
        return None, '无效的请求数据', 400

    now = now_text()
    has_enabled = 'enabled' in data
    has_content = any(k in data for k in NOTICE_FIELDS)
    before_state = {
        'enabled': _is_notice_enabled(db),
        'active': get_notice(db),
        'items': list_notices(db),
    }

    if has_enabled:
        enabled = str(data.get('enabled', False)).strip().lower() == 'true'
        _set_notice_enabled(db, enabled, now)

    if has_content:
        active = _active_notice_row(db)
        if active:
            result, error, status = update_saved_notice(db, actor_user_id, active['id'], data)
            if error:
                return result, error, status
        else:
            result, error, status = create_notice(db, actor_user_id, data)
            if error:
                return result, error, status
            activate_result, error, status = activate_notice(db, actor_user_id, result['id'])
            if error:
                return activate_result, error, status
        active_notice = get_notice(db)
        _write_notice_data_setting(db, active_notice, now)

    after_state = {
        'enabled': _is_notice_enabled(db),
        'active': get_notice(db),
        'items': list_notices(db),
    }
    write_audit(actor_user_id, 'update_notice', 'app_setting', before=before_state, after=after_state)
    db.commit()
    return {'ok': True}, None, 200
