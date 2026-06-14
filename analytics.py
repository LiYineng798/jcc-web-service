import json
from datetime import datetime

from db import get_db, now_text

ALLOWED_GROWTH_EVENTS = {
    'click_login_entry',
    'open_auth_page',
    'guest_click_like',
    'guest_click_favorite',
    'guest_click_report',
    'register_success',
    'login_success',
    'post_login_like',
    'post_login_favorite',
    'post_login_copy',
    'post_login_create_lineup',
}

ALLOWED_PAGE_KEYS = {'home', 'auth', 'author', 'me'}
POST_LOGIN_CORE_EVENTS = {
    'post_login_like',
    'post_login_favorite',
    'post_login_copy',
    'post_login_create_lineup',
}
AUTH_SUCCESS_EVENTS = {'register_success', 'login_success'}


def _safe_pct(numerator, denominator):
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _today_date():
    return datetime.now().strftime('%Y-%m-%d')


def _normalize_target_date(target_date=None):
    value = str(target_date or '').strip()
    if not value:
        return _today_date()
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return _today_date()
    return value


def _event_actor_key(alias):
    return f'''
        CASE
            WHEN {alias}.user_id IS NOT NULL THEN 'user:' || {alias}.user_id
            WHEN COALESCE({alias}.visitor_token, '') != '' THEN 'visitor:' || {alias}.visitor_token
            ELSE 'ip:' || COALESCE({alias}.ip_address, '0.0.0.0')
        END
    '''


def _count_event_visitors(target_date):
    rows = get_db().execute(
        f'''
        SELECT ge.event_name, COUNT(DISTINCT {_event_actor_key('ge')}) AS c
        FROM growth_events ge
        LEFT JOIN users u ON u.id = ge.user_id
        WHERE substr(ge.created_at, 1, 10) = ?
          AND (ge.user_id IS NULL OR COALESCE(u.role, 'user') != 'admin')
        GROUP BY ge.event_name
        ''',
        (target_date,),
    ).fetchall()
    return {row['event_name']: row['c'] for row in rows}


def _count_home_uv(target_date):
    row = get_db().execute(
        '''
        SELECT COUNT(DISTINCT ve.visitor_key) AS c
        FROM visit_events ve
        LEFT JOIN users u ON u.id = ve.user_id
        WHERE ve.visit_date = ?
          AND ve.page_key = 'home'
          AND (ve.user_id IS NULL OR COALESCE(u.role, 'user') != 'admin')
        ''',
        (target_date,),
    ).fetchone()
    return row['c'] if row else 0


def _count_auth_success_users(target_date):
    row = get_db().execute(
        '''
        SELECT COUNT(DISTINCT ge.user_id) AS c
        FROM growth_events ge
        JOIN users u ON u.id = ge.user_id
        WHERE substr(ge.created_at, 1, 10) = ?
          AND ge.event_name IN ('register_success', 'login_success')
          AND u.role != 'admin'
        ''',
        (target_date,),
    ).fetchone()
    return row['c'] if row else 0


def _count_post_login_action_users(target_date, action_event_name):
    row = get_db().execute(
        '''
        SELECT COUNT(DISTINCT auth.user_id) AS c
        FROM growth_events auth
        JOIN users u ON u.id = auth.user_id
        WHERE substr(auth.created_at, 1, 10) = ?
          AND auth.event_name IN ('register_success', 'login_success')
          AND u.role != 'admin'
          AND EXISTS (
              SELECT 1
              FROM growth_events action
              WHERE action.user_id = auth.user_id
                AND action.event_name = ?
                AND action.created_at >= auth.created_at
                AND action.created_at <= datetime(auth.created_at, '+10 minutes')
          )
        ''',
        (target_date, action_event_name),
    ).fetchone()
    return row['c'] if row else 0


def sanitize_growth_payload(data):
    data = data or {}
    event_name = str(data.get('event_name') or '').strip()
    page_key = str(data.get('page_key') or '').strip()
    ref_lineup_id = data.get('ref_lineup_id')
    if event_name not in ALLOWED_GROWTH_EVENTS:
        return None, '不支持的事件'
    if page_key not in ALLOWED_PAGE_KEYS:
        return None, '页面标识无效'
    if ref_lineup_id in ('', None):
        ref_lineup_id = None
    else:
        try:
            ref_lineup_id = int(ref_lineup_id)
        except (TypeError, ValueError):
            return None, '关联阵容无效'
    payload = data.get('payload')
    if not isinstance(payload, dict):
        payload = {}
    return {
        'event_name': event_name,
        'page_key': page_key,
        'ref_lineup_id': ref_lineup_id,
        'payload': payload,
    }, None


def record_growth_event(
    event_name,
    user_id=None,
    visitor_token=None,
    ip_address=None,
    ref_lineup_id=None,
    page_key=None,
    payload=None,
    created_at=None,
):
    if event_name not in ALLOWED_GROWTH_EVENTS:
        raise ValueError('unsupported growth event')
    if page_key and page_key not in ALLOWED_PAGE_KEYS:
        raise ValueError('unsupported page key')
    get_db().execute(
        '''
        INSERT INTO growth_events (
            event_name, user_id, visitor_token, ip_address, ref_lineup_id, page_key, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            event_name,
            user_id,
            visitor_token,
            ip_address,
            ref_lineup_id,
            page_key,
            json.dumps(payload or {}, ensure_ascii=False),
            created_at or now_text(),
        ),
    )
    get_db().commit()


def growth_summary(target_date=None):
    target_date = _normalize_target_date(target_date)
    event_counts = _count_event_visitors(target_date)
    home_uv = _count_home_uv(target_date)
    auth_success_users = _count_auth_success_users(target_date)
    post_login_like_users = _count_post_login_action_users(target_date, 'post_login_like')
    post_login_favorite_users = _count_post_login_action_users(target_date, 'post_login_favorite')
    post_login_create_lineup_users = _count_post_login_action_users(target_date, 'post_login_create_lineup')

    login_entry_visitors = event_counts.get('click_login_entry', 0)
    auth_page_visitors = event_counts.get('open_auth_page', 0)
    successful_registrations = event_counts.get('register_success', 0)
    successful_logins = event_counts.get('login_success', 0)

    return {
        'date': target_date,
        'home_uv': home_uv,
        'login_entry_visitors': login_entry_visitors,
        'auth_page_visitors': auth_page_visitors,
        'successful_registrations': successful_registrations,
        'successful_logins': successful_logins,
        'guest_like_visitors': event_counts.get('guest_click_like', 0),
        'guest_favorite_visitors': event_counts.get('guest_click_favorite', 0),
        'post_login_like_users': post_login_like_users,
        'post_login_favorite_users': post_login_favorite_users,
        'post_login_create_lineup_users': post_login_create_lineup_users,
        'conversion_rates': {
            'entry_to_auth_page_pct': _safe_pct(auth_page_visitors, login_entry_visitors),
            'auth_page_to_auth_success_pct': _safe_pct(auth_success_users, auth_page_visitors),
            'auth_success_to_like_pct': _safe_pct(post_login_like_users, auth_success_users),
            'auth_success_to_favorite_pct': _safe_pct(post_login_favorite_users, auth_success_users),
            'auth_success_to_create_lineup_pct': _safe_pct(post_login_create_lineup_users, auth_success_users),
        },
    }
