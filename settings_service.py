from audit import write_audit
from db import now_text


def get_settings(db):
    rows = db.execute('SELECT setting_key, setting_value FROM app_settings').fetchall()
    return {row['setting_key']: row['setting_value'] for row in rows}


def get_setting(db, key, default='true'):
    row = db.execute(
        'SELECT setting_value FROM app_settings WHERE setting_key = ?', (key,)
    ).fetchone()
    return row['setting_value'] if row else default


def save_settings(db, actor_user_id, data):
    if not isinstance(data, dict) or not data:
        return None, '没有可保存的设置', 400

    now = now_text()
    for key, value in data.items():
        value_str = str(value).strip().lower()
        if value_str not in ('true', 'false'):
            return None, f'{key} 的值必须为 true 或 false', 400

        before = db.execute(
            'SELECT setting_value FROM app_settings WHERE setting_key = ?', (key,)
        ).fetchone()

        db.execute(
            '''INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at)
               VALUES (?, ?, ?)''',
            (key, value_str, now),
        )

        write_audit(
            actor_user_id,
            'update_setting',
            'app_setting',
            before={'setting_key': key, 'setting_value': before['setting_value']} if before else None,
            after={'setting_key': key, 'setting_value': value_str},
        )

    db.commit()
    return {'ok': True}, None, 200
