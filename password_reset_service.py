import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from flask import current_app

from db import db_kind, get_db, now_text
from db_adapter import insert_returning_id_sql, last_insert_id
from rate_limit import hit_limit


def _hash_code(code):
    secret = str(current_app.secret_key).encode('utf-8')
    return hmac.new(secret, code.encode('utf-8'), hashlib.sha256).hexdigest()


def _valid_code(code, expected):
    return hmac.compare_digest(_hash_code(code), expected or '')


def _send_email(email, code, request_id):
    api_key = current_app.config.get('RESEND_API_KEY', '')
    if not api_key:
        raise RuntimeError('RESEND_API_KEY 未配置')
    import resend
    from resend.exceptions import ResendError

    resend.api_key = api_key
    params = {
        'from': current_app.config['RESEND_FROM_EMAIL'],
        'to': [email],
        'subject': '金铲铲阵容库密码重置验证码',
        'html': (
            '<div style="font-family:Arial,sans-serif;line-height:1.7;color:#20242b">'
            '<h2>金铲铲阵容库</h2>'
            '<p>你的密码重置验证码是：</p>'
            f'<p style="font-size:30px;letter-spacing:8px;font-weight:700">{code}</p>'
            f'<p>验证码 {current_app.config["PASSWORD_RESET_CODE_TTL_MINUTES"]} 分钟内有效，仅可使用一次。</p>'
            '<p>如果不是你本人操作，请忽略此邮件。</p></div>'
        ),
        'text': f'金铲铲阵容库密码重置验证码：{code}。验证码 {current_app.config["PASSWORD_RESET_CODE_TTL_MINUTES"]} 分钟内有效，仅可使用一次。',
    }
    options = {'idempotency_key': f'password-reset/{request_id}'}
    try:
        return resend.Emails.send(params, options), ResendError
    except ResendError:
        raise


def request_reset(email, ip_address):
    email = str(email or '').strip().lower()
    generic = {'ok': True, 'message': '如果该邮箱已注册，验证码将在几分钟内发送。'}
    if hit_limit('password_reset_ip', ip_address, 5, 60) or hit_limit('password_reset_email', email or 'invalid', 3, 60):
        return generic, None, 200

    db = get_db()
    now = datetime.now()
    cooldown_seconds = int(current_app.config.get('PASSWORD_RESET_COOLDOWN_SECONDS', 60))
    latest_sent = db.execute(
        '''SELECT created_at FROM password_reset_requests
           WHERE email = ? AND status IN ('pending', 'sent')
           ORDER BY id DESC LIMIT 1''',
        (email,),
    ).fetchone() if email else None
    if latest_sent:
        try:
            sent_at = datetime.strptime(latest_sent['created_at'], '%Y-%m-%d %H:%M:%S')
            if (now - sent_at).total_seconds() < cooldown_seconds:
                return generic, None, 200
        except (TypeError, ValueError):
            pass
    user = db.execute('SELECT id FROM users WHERE email = ? AND status = \'active\'', (email,)).fetchone() if email else None
    if not user:
        return generic, None, 200

    now_value = now.strftime('%Y-%m-%d %H:%M:%S')
    expires_value = (now + timedelta(minutes=current_app.config['PASSWORD_RESET_CODE_TTL_MINUTES'])).strftime('%Y-%m-%d %H:%M:%S')
    code = f'{secrets.randbelow(1000000):06d}'
    cursor = db.execute(
        insert_returning_id_sql(
            '''INSERT INTO password_reset_requests
               (user_id, email, code_hash, expires_at, ip_address, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')''',
            db_kind(),
        ),
        (user['id'], email, _hash_code(code), expires_value, ip_address, now_value),
    )
    request_id = last_insert_id(cursor, db_kind())
    db.commit()
    try:
        result, _ = _send_email(email, code, request_id)
    except Exception as exc:
        db.execute('UPDATE password_reset_requests SET status = ?, provider_id = ? WHERE id = ?', ('failed', str(exc)[:500], request_id))
        db.commit()
        return None, '邮件发送失败，请稍后再试', 503

    provider_id = str(result.get('id', '') if isinstance(result, dict) else getattr(result, 'id', ''))
    db.execute("UPDATE password_reset_requests SET provider_id = ?, status = 'sent' WHERE id = ?", (provider_id, request_id))
    db.commit()
    return generic, None, 200


def confirm_reset(email, code, password):
    email = str(email or '').strip().lower()
    code = str(code or '').strip()
    db = get_db()
    request_row = db.execute(
        '''SELECT * FROM password_reset_requests
           WHERE email = ? AND status = 'sent' AND consumed_at IS NULL
           ORDER BY id DESC LIMIT 1''',
        (email,),
    ).fetchone()
    now = datetime.now()
    if not request_row or datetime.strptime(request_row['expires_at'], '%Y-%m-%d %H:%M:%S') < now:
        return None, '验证码无效或已过期，请重新获取', 400
    if request_row['attempts'] >= 5:
        return None, '验证码尝试次数过多，请重新获取', 400
    db.execute('UPDATE password_reset_requests SET attempts = attempts + 1 WHERE id = ?', (request_row['id'],))
    if not _valid_code(code, request_row['code_hash']):
        db.commit()
        return None, '验证码错误，请检查后重试', 400
    if len(str(password or '')) < 6 or not any(ch.isalpha() for ch in str(password)) or not any(ch.isdigit() for ch in str(password)):
        db.commit()
        return None, '密码需大于5位且包含字母和数字', 400
    now_value = now_text()
    db.execute('UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?', (_password_hash(password), now_value, request_row['user_id']))
    db.execute("UPDATE password_reset_requests SET consumed_at = ?, status = 'consumed' WHERE id = ?", (now_value, request_row['id']))
    db.commit()
    return {'ok': True}, None, 200


def _password_hash(password):
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)


def list_today_requests(db):
    today = now_text()[:10]
    rows = db.execute(
        '''SELECT id, created_at, email, '密码找回' AS purpose, status, provider_id
           FROM password_reset_requests WHERE substr(created_at, 1, 10) = ?
           ORDER BY id DESC''',
        (today,),
    ).fetchall()
    return {'date': today, 'items': [dict(row) for row in rows], 'total': len(rows)}
