"""Restricted machine identities: no sessions, no general admin privileges."""
import hashlib
import hmac
import json
import re
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


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


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


def issue_token(user_id):
    token = f'jcc_ai_{user_id}_{secrets.token_urlsafe(32)}'
    return token, digest(token), f'jcc_ai_{user_id}_…'


def permissions(data, existing=None):
    existing = existing or {}
    can_import = data.get('can_import', bool(existing.get('can_import', False)))
    if type(can_import) is not bool:
        raise AutomationError('导入权限必须为布尔值')
    seasons = data.get('allowed_seasons', existing.get('allowed_seasons', []))
    if not isinstance(seasons, list) or len(seasons) > 30 or any(not isinstance(s, str) for s in seasons):
        raise AutomationError('请选择允许导入的赛季')
    choices = season_choice_map()
    if can_import and (not seasons or any(s not in choices for s in seasons)):
        raise AutomationError('启用导入必须选择有效的普通阵容赛季')
    return int(can_import), json.dumps(sorted(set(seasons if can_import else [])))


def expiry(data):
    days = data.get('expires_in_days', 30)
    if type(days) is not int or not 1 <= days <= 90:
        raise AutomationError('有效期须为 1–90 天')
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')


def serialize_account(row):
    return {
        key: row[key] for key in ('user_id', 'username', 'nickname', 'status', 'expires_at',
                                  'token_prefix', 'created_at', 'last_used_at')
    } | {'can_import': bool(row['can_import']), 'allowed_seasons': json.loads(row['allowed_seasons_json'])}


def list_accounts(db):
    rows = db.execute('''
        SELECT a.*, u.username, u.nickname, u.status, u.created_at
        FROM automation_accounts a JOIN users u ON u.id=a.user_id
        WHERE a.deleted_at IS NULL ORDER BY a.user_id DESC
    ''').fetchall()
    return {'items': [serialize_account(row) for row in rows]}


def create_account(db, admin_id, data):
    if set(data) - {'username', 'nickname', 'can_import', 'allowed_seasons', 'expires_in_days'}:
        raise AutomationError('不支持的账号字段')
    username = str(data.get('username') or '').strip()
    nickname = str(data.get('nickname') or username).strip()
    if not USERNAME_RE.fullmatch(username) or not 1 <= len(nickname) <= 30:
        raise AutomationError('用户名和名称须为 1–30 字；用户名只允许中文、字母、数字、下划线')
    can_import, seasons = permissions(data)
    expires = expiry(data)
    if db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
        raise AutomationError('用户名已存在')
    now = now_text()
    try:
        cursor = db.execute(insert_returning_id_sql('''
            INSERT INTO users (username, email, nickname, password_hash, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'automation', 'active', ?, ?)
        ''', db_kind()), (username, f'{secrets.token_hex(16)}@automation.invalid', nickname,
                         generate_password_hash(secrets.token_urlsafe(48)), now, now))
        user_id = last_insert_id(cursor, db_kind())
        token, hashed, prefix = issue_token(user_id)
        db.execute('''
            INSERT INTO automation_accounts (user_id, token_hash, token_prefix, expires_at, can_import, allowed_seasons_json, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, hashed, prefix, expires, can_import, seasons, admin_id))
        write_audit(admin_id, 'create_automation_account', 'user', user_id,
                    after={'username': username, 'can_import': bool(can_import), 'allowed_seasons': json.loads(seasons), 'expires_at': expires})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'user_id': user_id, 'token': token, 'expires_at': expires}


def change_account(db, admin_id, user_id, data, action='update'):
    db.execute('UPDATE automation_accounts SET token_hash=token_hash WHERE user_id=?', (user_id,))
    row = db.execute('SELECT * FROM automation_accounts WHERE user_id=? AND deleted_at IS NULL', (user_id,)).fetchone()
    if not row:
        raise AutomationError('自动化账号不存在', 404)
    result = {'ok': True}
    if action == 'delete':
        db.execute("UPDATE users SET status='disabled', updated_at=? WHERE id=?", (now_text(), user_id))
        db.execute("UPDATE automation_accounts SET token_hash='', deleted_at=? WHERE user_id=?", (utc_now(), user_id))
    elif action == 'rotate':
        token, hashed, prefix = issue_token(user_id)
        expires = expiry(data)
        db.execute('UPDATE automation_accounts SET token_hash=?, token_prefix=?, expires_at=? WHERE user_id=?',
                   (hashed, prefix, expires, user_id))
        result.update(token=token, expires_at=expires)
    else:
        if set(data) - {'status', 'can_import', 'allowed_seasons'}:
            raise AutomationError('不支持的账号字段')
        can_import, seasons = row['can_import'], row['allowed_seasons_json']
        if 'can_import' in data or 'allowed_seasons' in data:
            can_import, seasons = permissions(data, {'can_import': row['can_import'], 'allowed_seasons': json.loads(row['allowed_seasons_json'])})
        if 'status' in data:
            if data['status'] not in ('active', 'disabled'):
                raise AutomationError('状态无效')
            db.execute('UPDATE users SET status=?, updated_at=? WHERE id=?', (data['status'], now_text(), user_id))
            if data['status'] == 'disabled':
                db.execute("UPDATE automation_accounts SET token_hash='' WHERE user_id=?", (user_id,))
        db.execute('UPDATE automation_accounts SET can_import=?, allowed_seasons_json=? WHERE user_id=?',
                   (can_import, seasons, user_id))
    # Never put credentials, token hashes or payload bodies into audit snapshots.
    write_audit(admin_id, f'{action}_automation_account', 'user', user_id,
                after={k: v for k, v in data.items() if k in ('status', 'can_import', 'allowed_seasons', 'expires_in_days')})
    db.commit()
    return result


def authenticate(db, authorization):
    match = re.fullmatch(r'Bearer (jcc_ai_(\d{1,18})_[A-Za-z0-9_-]{43})', authorization or '')
    if not match:
        raise AutomationError('需要有效的自动化 Bearer 令牌', 401)
    row = db.execute('''
        SELECT a.*, u.status, u.role, u.username FROM automation_accounts a
        JOIN users u ON u.id=a.user_id WHERE a.user_id=?
    ''', (int(match[2]),)).fetchone()
    if (not row or row['role'] != 'automation' or row['status'] != 'active' or row['deleted_at']
            or row['expires_at'] <= utc_now() or not hmac.compare_digest(row['token_hash'], digest(match[1]))):
        raise AutomationError('令牌无效、过期或账号已禁用', 401)
    return dict(row)


def import_lineups(db, account, data, request_key, preview=False):
    if not account['can_import']:
        raise AutomationError('此账号仅可读取运营数据', 403)
    if set(data) - {'season_id', 'raw_text'}:
        raise AutomationError('仅支持 season_id 和 raw_text；不能指定作者、状态或榜单数据')
    season = data.get('season_id')
    if season not in json.loads(account['allowed_seasons_json']) or season not in season_choice_map():
        raise AutomationError('该普通阵容赛季不在授权范围内或已隐藏', 403)
    raw = data.get('raw_text')
    if not isinstance(raw, str) or len(raw) > 20000 or not 1 <= len([s for s in raw.splitlines() if s.strip()]) <= 50:
        raise AutomationError('每批限 1–50 行、最多 20000 字符')
    if preview:
        result, error, status = preview_bulk_import_lineups(db, data)
        if error:
            raise AutomationError(error, status)
        return result
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', request_key or ''):
        raise AutomationError('导入须提供 8–100 位 Idempotency-Key（字母、数字、_ 或 -）')
    payload_hash = digest(json.dumps(data, sort_keys=True, ensure_ascii=False))
    # Row update serializes imports for this identity in both supported databases.
    # Import, attribution, audit and the retry receipt commit in one transaction.
    db.execute('UPDATE automation_accounts SET last_used_at=? WHERE user_id=?', (utc_now(), account['user_id']))
    fresh = db.execute('''
        SELECT a.*, u.status FROM automation_accounts a JOIN users u ON u.id=a.user_id
        WHERE a.user_id=?
    ''', (account['user_id'],)).fetchone()
    if (fresh['status'] != 'active' or fresh['deleted_at'] or fresh['expires_at'] <= utc_now()
            or not hmac.compare_digest(fresh['token_hash'], account['token_hash'])):
        raise AutomationError('账号权限已变更，请重新验证令牌', 401)
    if not fresh['can_import'] or season not in json.loads(fresh['allowed_seasons_json']):
        raise AutomationError('导入权限已撤销', 403)
    receipt = db.execute('SELECT * FROM automation_imports WHERE user_id=? AND request_key=?',
                         (account['user_id'], request_key)).fetchone()
    if receipt:
        if receipt['payload_hash'] != payload_hash:
            db.rollback()
            raise AutomationError('此 Idempotency-Key 已用于不同内容', 409)
        db.commit()
        return json.loads(receipt['result_json'])
    result, error, status = bulk_import_lineups(db, account['user_id'], data, commit=False)
    if error:
        db.rollback()
        raise AutomationError(error, status)
    db.execute('INSERT INTO automation_imports (user_id, request_key, payload_hash, result_json, created_at) VALUES (?, ?, ?, ?, ?)',
               (account['user_id'], request_key, payload_hash, json.dumps(result, ensure_ascii=False), utc_now()))
    db.commit()
    return result
