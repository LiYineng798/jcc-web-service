"""Administrator-provisioned, scoped browser accounts."""
import json
import secrets
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from admin_lineup_service import bulk_import_lineups, preview_bulk_import_lineups
from audit import write_audit
from auth import USERNAME_RE
from db import db_kind, now_text
from db_adapter import insert_returning_id_sql, last_insert_id
from lineups_utils import season_choice_map


class AutomationError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def request_limited(db, account_id, write=False):
    """Atomic increment so concurrent clients cannot race the quota check."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    window = now.replace(minute=0) if write else now
    limit = 10 if write else 60
    row = db.execute('''
        INSERT INTO rate_limits (scope, key, window_start, attempts) VALUES (?, ?, ?, 1)
        ON CONFLICT (scope, key, window_start) DO UPDATE SET attempts=rate_limits.attempts+1
        WHERE rate_limits.attempts < ?
        RETURNING attempts
    ''', ('automation-write' if write else 'automation-read', str(account_id), window.isoformat(), limit)).fetchone()
    db.commit()
    return row is None



def session_account(db, user_id):
    row = db.execute("SELECT * FROM automation_accounts WHERE user_id=? AND deleted_at IS NULL", (user_id,)).fetchone()
    return dict(row) if row and row['expires_at'] > utc_now() else None


def permissions(data, existing=None):
    existing = existing or {}
    result = {}
    for flag, scope in (('can_import', 'allowed_seasons'), ('can_touch', 'touch_seasons')):
        enabled = data.get(flag, bool(existing.get(flag, False)))
        seasons = data.get(scope, existing.get(scope, []))
        if type(enabled) is not bool:
            raise AutomationError('操作权限必须为布尔值')
        if not isinstance(seasons, list) or len(seasons) > 30 or any(not isinstance(s, str) for s in seasons):
            raise AutomationError('请选择授权赛季')
        if enabled and (not seasons or any(s not in season_choice_map() for s in seasons)):
            raise AutomationError('开启操作权限必须选择有效的公开赛季')
        result[flag] = int(enabled)
        result[scope] = sorted(set(seasons)) if enabled else []
    return result


def expiry(data):
    days = data.get('expires_in_days', 30)
    if type(days) is not int or not 1 <= days <= 90:
        raise AutomationError('账号有效期须为 1–90 天')
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')


def password_hash(data):
    password = data.get('password')
    if not isinstance(password, str) or not 12 <= len(password) <= 128 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise AutomationError('密码须为 12–128 字符，包含字母和数字')
    return generate_password_hash(password)


def serialize_account(row):
    return {key: row[key] for key in ('user_id', 'username', 'nickname', 'status', 'expires_at', 'created_at', 'last_used_at')} | {
        'can_import': bool(row['can_import']), 'allowed_seasons': json.loads(row['allowed_seasons_json']),
        'can_touch': bool(row['can_touch']), 'touch_seasons': json.loads(row['touch_seasons_json'])}


def list_accounts(db):
    rows = db.execute("SELECT a.*, u.username, u.nickname, u.status, u.created_at FROM automation_accounts a JOIN users u ON u.id=a.user_id WHERE a.deleted_at IS NULL ORDER BY a.user_id DESC").fetchall()
    return {'items': [serialize_account(row) for row in rows]}


def create_account(db, admin_id, data):
    if set(data) - {'username', 'nickname', 'password', 'can_import', 'allowed_seasons', 'can_touch', 'touch_seasons', 'expires_in_days'}:
        raise AutomationError('不支持的账号字段')
    username = str(data.get('username') or '').strip()
    nickname = str(data.get('nickname') or username).strip()
    if not USERNAME_RE.fullmatch(username) or not 1 <= len(nickname) <= 30:
        raise AutomationError('用户名和名称须为 1–30 字；用户名只允许中文、字母、数字、下划线')
    scopes, expires, hashed = permissions(data), expiry(data), password_hash(data)
    if db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
        raise AutomationError('用户名已存在')
    now = now_text()
    cursor = db.execute(insert_returning_id_sql("""
        INSERT INTO users (username,email,nickname,password_hash,role,status,created_at,updated_at)
        VALUES (?,?,?,?,'automation','active',?,?)
    """, db_kind()), (username, f'{secrets.token_hex(16)}@automation.invalid', nickname, hashed, now, now))
    user_id = last_insert_id(cursor, db_kind())
    db.execute("""INSERT INTO automation_accounts
        (user_id,expires_at,can_import,allowed_seasons_json,can_touch,touch_seasons_json,created_by)
        VALUES (?,?,?,?,?,?,?)""", (user_id, expires, scopes['can_import'], json.dumps(scopes['allowed_seasons']),
                                  scopes['can_touch'], json.dumps(scopes['touch_seasons']), admin_id))
    write_audit(admin_id, 'create_automation_account', 'user', user_id, after={**scopes, 'username': username, 'expires_at': expires})
    db.commit()
    return {'user_id': user_id, 'username': username, 'expires_at': expires}


def change_account(db, admin_id, user_id, data, action='update'):
    db.execute('UPDATE automation_accounts SET session_version=session_version WHERE user_id=?', (user_id,))
    row = db.execute('SELECT * FROM automation_accounts WHERE user_id=? AND deleted_at IS NULL', (user_id,)).fetchone()
    if not row:
        raise AutomationError('自动化账号不存在', 404)
    if action == 'delete':
        db.execute("UPDATE users SET status='disabled',updated_at=? WHERE id=?", (now_text(), user_id))
        db.execute('UPDATE automation_accounts SET deleted_at=?,session_version=session_version+1 WHERE user_id=?', (utc_now(), user_id))
    else:
        if set(data) - {'status', 'password', 'expires_in_days', 'can_import', 'allowed_seasons', 'can_touch', 'touch_seasons'}:
            raise AutomationError('不支持的账号字段')
        scopes = permissions(data, {'can_import': row['can_import'], 'allowed_seasons': json.loads(row['allowed_seasons_json']),
                                    'can_touch': row['can_touch'], 'touch_seasons': json.loads(row['touch_seasons_json'])})
        db.execute('UPDATE automation_accounts SET can_import=?,allowed_seasons_json=?,can_touch=?,touch_seasons_json=? WHERE user_id=?',
                   (scopes['can_import'], json.dumps(scopes['allowed_seasons']), scopes['can_touch'], json.dumps(scopes['touch_seasons']), user_id))
        if 'expires_in_days' in data:
            db.execute('UPDATE automation_accounts SET expires_at=? WHERE user_id=?', (expiry(data), user_id))
        if 'password' in data:
            db.execute('UPDATE users SET password_hash=?,updated_at=? WHERE id=?', (password_hash(data), now_text(), user_id))
        if 'status' in data:
            if data['status'] not in ('active', 'disabled'):
                raise AutomationError('状态无效')
            db.execute('UPDATE users SET status=?,updated_at=? WHERE id=?', (data['status'], now_text(), user_id))
            db.execute('UPDATE automation_accounts SET session_version=session_version+1 WHERE user_id=?', (user_id,))
    write_audit(admin_id, f'{action}_automation_account', 'user', user_id,
                after={k: v for k, v in data.items() if k != 'password'} | ({'password_reset': True} if 'password' in data else {}))
    db.commit()
    return {'ok': True}


def require_scope(account, flag, scope, season):
    if not account[flag] or season not in json.loads(account[scope]) or season not in season_choice_map():
        raise AutomationError('该操作或赛季未获得授权', 403)


def lock_account(db, account):
    # Serialize writes with permission changes and concurrent imports by this account.
    db.execute('UPDATE automation_accounts SET session_version=session_version WHERE user_id=?', (account['user_id'],))
    fresh = session_account(db, account['user_id'])
    user = db.execute('SELECT role,status FROM users WHERE id=?', (account['user_id'],)).fetchone()
    if not fresh or user['role'] != 'automation' or user['status'] != 'active' or fresh['session_version'] != account['session_version']:
        raise AutomationError('账号权限已变更，请重新登录', 401)
    return fresh


def import_lineups(db, account, data, preview=False):
    account = lock_account(db, account)
    require_scope(account, 'can_import', 'allowed_seasons_json', data.get('season_id'))
    if set(data) - {'season_id', 'raw_text'}:
        raise AutomationError('只能导入普通赛季阵容，不能指定作者、状态或榜单内容')
    raw = data.get('raw_text')
    if not isinstance(raw, str) or len(raw) > 20000 or not 1 <= len([s for s in raw.splitlines() if s.strip()]) <= 50:
        raise AutomationError('每批限 1–50 行、最多 20000 字符')
    if preview:
        result, error, status = preview_bulk_import_lineups(db, data)
    else:
        result, error, status = bulk_import_lineups(db, account['user_id'], data)
    if error:
        raise AutomationError(error, status)
    return result
