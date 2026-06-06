import json

from audit import write_audit
from db import now_text


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


def get_notice(db):
    """Return notice content regardless of enabled state (used by admin)."""
    data = _load_notice_data(db)
    return {
        'title': str(data.get('title', '')),
        'message': str(data.get('message', '')),
        'link_url': str(data.get('link_url', '')),
        'link_text': str(data.get('link_text', '')),
    }


def get_active_notice(db):
    """Return notice content only when enabled (used by public site)."""
    if not _is_notice_enabled(db):
        return None
    data = _load_notice_data(db)
    if not data.get('title') or not data.get('message'):
        return None
    return {
        'title': str(data['title']),
        'message': str(data['message']),
        'link_url': str(data.get('link_url', '')),
        'link_text': str(data.get('link_text', '')),
    }


def save_notice(db, actor_user_id, data):
    if not isinstance(data, dict):
        return None, '无效的请求数据', 400

    now = now_text()
    has_enabled = 'enabled' in data
    has_content = any(k in data for k in ['title', 'message', 'link_url', 'link_text'])

    before_enabled = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'notice_enabled'"
    ).fetchone()
    before_data = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'notice_data'"
    ).fetchone()
    before_state = {
        'enabled': before_enabled['setting_value'] if before_enabled else 'false',
        'data': before_data['setting_value'] if before_data else '{}',
    }

    if has_enabled:
        enabled = str(data.get('enabled', False)).strip().lower() == 'true'
        db.execute(
            "INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
            ('notice_enabled', 'true' if enabled else 'false', now),
        )

    if has_content:
        existing = _load_notice_data(db)
        title = str(data.get('title', existing.get('title', ''))).strip()
        message = str(data.get('message', existing.get('message', ''))).strip()
        link_url = str(data.get('link_url', existing.get('link_url', ''))).strip()
        link_text = str(data.get('link_text', existing.get('link_text', ''))).strip()

        if not title:
            return None, '标题不能为空', 400
        if not message:
            return None, '内容不能为空', 400

        notice_data = json.dumps({
            'title': title,
            'message': message,
            'link_url': link_url,
            'link_text': link_text,
        }, ensure_ascii=False)

        db.execute(
            "INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
            ('notice_data', notice_data, now),
        )

    after_enabled = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'notice_enabled'"
    ).fetchone()
    after_data = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'notice_data'"
    ).fetchone()

    write_audit(
        actor_user_id,
        'update_notice',
        'app_setting',
        before=before_state,
        after={
            'enabled': after_enabled['setting_value'] if after_enabled else 'false',
            'data': after_data['setting_value'] if after_data else '{}',
        },
    )

    db.commit()
    return {'ok': True}, None, 200
