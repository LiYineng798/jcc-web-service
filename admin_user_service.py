from __future__ import annotations

from werkzeug.security import generate_password_hash

from avatar_service import avatar_color, avatar_config, random_avatar_config
from audit import write_audit
from auth import validate_password
from db import db_kind, now_text
from db_adapter import insert_returning_id_sql, last_insert_id


def build_user_list_query(query):
    query = str(query or '').strip()
    params = []
    from_sql = "FROM users WHERE NOT EXISTS (SELECT 1 FROM automation_accounts a WHERE a.user_id=users.id AND a.deleted_at IS NOT NULL)"
    if query:
        from_sql += ' AND (username LIKE ? OR email LIKE ? OR nickname LIKE ?)'
        params = [f'%{query}%', f'%{query}%', f'%{query}%']
    base_sql = 'SELECT id, username, email, nickname, role, status, created_at, updated_at, last_login_at, avatar_color, avatar_preset, avatar_expression ' + from_sql + ' ORDER BY id DESC'
    count_sql = 'SELECT COUNT(*) AS c ' + from_sql
    return base_sql, count_sql, params


def serialize_admin_user(row):
    return {**dict(row), 'avatar_color': avatar_color(row), 'avatar_config': avatar_config(row)}


def prepare_user_create_payload(data):
    if data.get('role') not in (None, 'user', 'admin'):
        return None, '自动化账号必须通过专用管理入口创建'
    password = str(data.get('password') or '')
    if not validate_password(password):
        return None, '密码需大于5位且包含字母和数字'
    username = str(data.get('username', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    nickname = str(data.get('nickname') or username).strip()
    role = data.get('role') if data.get('role') in {'user', 'admin'} else 'user'
    now = now_text()
    return {
        'username': username,
        'email': email,
        'nickname': nickname,
        'role': role,
        'password_hash': generate_password_hash(password),
        'created_at': now,
        'updated_at': now,
    }, None


def create_user(db, admin_id, data):
    payload, error = prepare_user_create_payload(data)
    if error:
        return None, error, 400
    avatar = random_avatar_config()
    try:
        cursor = db.execute(
            insert_returning_id_sql(
                '''INSERT INTO users (username, email, nickname, password_hash, role, status, created_at, updated_at, avatar_color, avatar_preset, avatar_expression)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)''',
                db_kind(),
            ),
            (
                payload['username'],
                payload['email'],
                payload['nickname'],
                payload['password_hash'],
                payload['role'],
                payload['created_at'],
                payload['updated_at'],
                avatar['color'],
                avatar['preset'],
                avatar['expression'],
            ),
        )
        user_id = last_insert_id(cursor, db_kind())
        write_audit(
            admin_id,
            'create_user',
            'user',
            user_id,
            after={'username': payload['username'], 'email': payload['email'], 'role': payload['role']},
        )
        db.commit()
    except Exception:
        db.rollback()
        return None, '用户名或邮箱已存在', 400
    return {'id': user_id}, None, 201


def prepare_user_update_fields(data):
    fields = []
    params = []
    for key in ['username', 'email', 'nickname', 'role', 'status']:
        if key in data:
            fields.append(f'{key} = ?')
            params.append(str(data[key]).strip())
    return fields, params


def update_user(db, admin_id, user_id, data):
    before = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not before:
        return None, '用户不存在', 404
    if before['role'] == 'automation' or data.get('role') not in (None, 'user', 'admin'):
        return None, '请通过自动化账号专用入口管理，不能转换账号类型', 403
    fields, params = prepare_user_update_fields(data)
    if data.get('password'):
        if not validate_password(data['password']):
            return None, '密码需大于5位且包含字母和数字', 400
        fields.append('password_hash = ?')
        params.append(generate_password_hash(data['password']))
    if not fields:
        return None, '没有可更新字段', 400
    fields.append('updated_at = ?')
    params.extend([now_text(), user_id])
    try:
        db.execute(f'UPDATE users SET {", ".join(fields)} WHERE id = ?', params)
        write_audit(admin_id, 'update_user', 'user', user_id, before=dict(before), after=data)
        db.commit()
    except Exception:
        db.rollback()
        return None, '用户名或邮箱已存在', 400
    return {'ok': True}, None, 200


def disable_user(db, admin_id, user_id):
    row = db.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
    if row and row['role'] == 'automation':
        from automation_service import change_account
        change_account(db, admin_id, user_id, {'status': 'disabled'})
        return
    db.execute("UPDATE users SET status = 'disabled', updated_at = ? WHERE id = ?", (now_text(), user_id))
    write_audit(admin_id, 'disable_user', 'user', user_id)
    db.commit()
