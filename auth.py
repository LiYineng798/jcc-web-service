import re
import secrets

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from analytics import record_growth_event
from captcha import is_captcha_verified, lookup_answer_for_tests, verify_captcha_answer
from db import get_db, now_text
from rate_limit import hit_limit

auth_bp = Blueprint('auth', __name__)

USERNAME_RE = re.compile(r'^[A-Za-z0-9_\u4e00-\u9fff]{1,30}$')
EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,20}$')


def get_client_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return get_db().execute(
        'SELECT id, username, email, nickname, role, status, created_at, updated_at, last_login_at FROM users WHERE id = ?',
        (user_id,),
    ).fetchone()


def csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token


def require_csrf():
    if request.method in {'POST', 'PUT', 'DELETE'} and request.endpoint not in {
        'auth.login', 'auth.register', 'auth.logout', 'captcha.captcha_verify'
    }:
        if request.headers.get('X-CSRF-Token') != session.get('csrf_token'):
            return jsonify({'error': 'CSRF 校验失败'}), 403
    return None


def login_required():
    user = current_user()
    if user is None:
        return None, (jsonify({'error': '请先登录'}), 401)
    if user['status'] != 'active':
        return None, (jsonify({'error': '账号已禁用'}), 403)
    return user, None


def admin_required():
    user, error = login_required()
    if error:
        return None, error
    if user['role'] != 'admin':
        return None, (jsonify({'error': '需要管理员权限'}), 403)
    return user, None


def public_user_payload(user):
    if not user:
        return None
    return {
        'id': user['id'],
        'username': user['username'],
        'nickname': user['nickname'],
        'role': user['role'],
    }


def validate_password(password):
    password = str(password or '')
    return len(password) > 5 and any(ch.isalpha() for ch in password) and any(ch.isdigit() for ch in password)


def validate_register_payload(data):
    username = str(data.get('username', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    nickname = str(data.get('nickname') or username).strip()
    password = str(data.get('password', ''))
    if not USERNAME_RE.match(username):
        return None, '用户名需为 1-30 位中文、字母、数字或下划线'
    if not EMAIL_RE.match(email):
        return None, '请输入正确邮箱'
    if not nickname or len(nickname) > 30:
        return None, '昵称需为 1-30 位'
    if not validate_password(password):
        return None, '密码需大于5位且包含字母和数字'
    return {'username': username, 'email': email, 'nickname': nickname, 'password': password}, None


def _remove_admin_analytics_traces(db, user_id, visitor_token):
    today = now_text()[:10]
    db.execute('DELETE FROM growth_events WHERE user_id = ?', (user_id,))
    if visitor_token:
        db.execute(
            'DELETE FROM growth_events WHERE visitor_token = ? AND user_id IS NULL AND substr(created_at, 1, 10) = ?',
            (visitor_token, today),
        )
        db.execute(
            'DELETE FROM visit_events WHERE visitor_token = ? AND user_id IS NULL AND visit_date = ?',
            (visitor_token, today),
        )
    db.execute(
        'DELETE FROM visit_events WHERE user_id = ? AND visit_date = ?',
        (user_id, today),
    )
    db.commit()


@auth_bp.before_app_request
def csrf_guard():
    return require_csrf()


@auth_bp.get('/api/me')
def me():
    return jsonify({'user': public_user_payload(current_user()), 'csrf_token': csrf_token()})


@auth_bp.post('/api/register')
def register():
    from visits import ensure_visitor_token, maybe_set_visitor_cookie

    data = request.get_json(silent=True) or {}
    ip = get_client_ip()
    if hit_limit('register', ip, 5, 60):
        return jsonify({'error': '注册过于频繁，请稍后再试'}), 429
    token = data.get('captcha_token')
    answer = data.get('captcha_answer')
    if not (is_captcha_verified(token) or verify_captcha_answer(token, answer)):
        return jsonify({'error': '请先完成验证码'}), 400
    payload, error = validate_register_payload(data)
    if error:
        return jsonify({'error': error}), 400
    db = get_db()
    if db.execute('SELECT id FROM users WHERE username = ?', (payload['username'],)).fetchone():
        return jsonify({'error': '用户名已存在'}), 400
    if db.execute('SELECT id FROM users WHERE email = ?', (payload['email'],)).fetchone():
        return jsonify({'error': '邮箱已存在'}), 400
    now = now_text()
    cursor = db.execute(
        '''INSERT INTO users (username, email, nickname, password_hash, role, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'user', 'active', ?, ?)''',
        (payload['username'], payload['email'], payload['nickname'], generate_password_hash(payload['password']), now, now),
    )
    db.commit()
    session['user_id'] = cursor.lastrowid
    csrf_token()
    user = current_user()
    visitor_token, created = ensure_visitor_token()
    record_growth_event(
        'register_success',
        user_id=user['id'],
        visitor_token=visitor_token,
        ip_address=ip,
        page_key='auth',
        payload={'method': 'register'},
    )
    response = jsonify({'user': public_user_payload(user), 'csrf_token': session['csrf_token']})
    return maybe_set_visitor_cookie(response, visitor_token, created), 201


@auth_bp.post('/api/login')
def login():
    from visits import ensure_visitor_token, maybe_set_visitor_cookie

    data = request.get_json(silent=True) or {}
    account = str(data.get('account') or data.get('username') or '').strip()
    password = str(data.get('password') or '')
    ip = get_client_ip()
    limit_key = f'{ip}:{account.lower()}'
    if hit_limit('login', limit_key, 10, 15):
        return jsonify({'error': '登录过于频繁，请稍后再试'}), 429
    db = get_db()
    user = db.execute(
        'SELECT * FROM users WHERE username = ? OR email = ?',
        (account, account.lower()),
    ).fetchone()
    ok = bool(user and user['status'] == 'active' and check_password_hash(user['password_hash'], password))
    db.execute(
        'INSERT INTO login_events (user_id, ip_address, success, created_at) VALUES (?, ?, ?, ?)',
        (user['id'] if user else None, ip, 1 if ok else 0, now_text()),
    )
    if not ok:
        db.commit()
        return jsonify({'error': '账号或密码错误'}), 400
    now = now_text()
    db.execute('UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?', (now, now, user['id']))
    db.commit()
    session.clear()
    session['user_id'] = user['id']
    csrf_token()
    visitor_token, created = ensure_visitor_token()
    if user['role'] == 'admin':
        _remove_admin_analytics_traces(db, user['id'], visitor_token)
    else:
        record_growth_event(
            'login_success',
            user_id=user['id'],
            visitor_token=visitor_token,
            ip_address=ip,
            page_key='auth',
            payload={'method': 'login'},
        )
    response = jsonify({'user': public_user_payload(current_user()), 'csrf_token': session['csrf_token']})
    return maybe_set_visitor_cookie(response, visitor_token, created)


@auth_bp.post('/api/logout')
def logout():
    session.clear()
    return jsonify({'ok': True})


