import secrets
from datetime import datetime, timedelta

from flask import current_app, make_response, render_template, request

from auth import current_user, get_client_ip
from db import get_db, now_text

VISITOR_COOKIE_NAME = 'visitor_token'
VISITOR_COOKIE_MAX_AGE = 180 * 24 * 60 * 60


def resolve_visitor_identity(user, visitor_token, ip_address):
    if user:
        return 'user', f'user:{user["id"]}'
    if visitor_token:
        return 'guest_token', f'guest:{visitor_token}'
    return 'ip_fallback', f'ip:{ip_address or "0.0.0.0"}'


def ensure_visitor_token():
    token = request.cookies.get(VISITOR_COOKIE_NAME, '').strip()
    if token:
        return token, False
    return secrets.token_urlsafe(18), True


def maybe_set_visitor_cookie(response, visitor_token, created):
    if not created:
        return response
    response.set_cookie(
        VISITOR_COOKIE_NAME,
        visitor_token,
        max_age=VISITOR_COOKIE_MAX_AGE,
        httponly=True,
        samesite='Lax',
        secure=not current_app.config.get('TESTING', False),
        path='/',
    )
    return response


def record_page_visit(page_key, user=None, visitor_token=None, ip_address=None):
    user = user or current_user()
    ip_address = ip_address or get_client_ip()
    visitor_kind, visitor_key = resolve_visitor_identity(user, visitor_token, ip_address)
    visit_date = datetime.now().strftime('%Y-%m-%d')
    get_db().execute(
        '''INSERT OR IGNORE INTO visit_events (
               visit_date, visitor_key, visitor_kind, user_id, visitor_token, ip_address, page_key, created_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            visit_date,
            visitor_key,
            visitor_kind,
            user['id'] if user else None,
            visitor_token,
            ip_address,
            page_key,
            now_text(),
        ),
    )
    get_db().commit()


def tracked_template_response(template_name, page_key, **context):
    user = current_user()
    visitor_token, created = ensure_visitor_token()
    record_page_visit(page_key, user=user, visitor_token=visitor_token, ip_address=get_client_ip())
    response = make_response(render_template(template_name, **context))
    return maybe_set_visitor_cookie(response, visitor_token, created)


def daily_uv_count(target_date):
    row = get_db().execute(
        '''
        SELECT COUNT(DISTINCT ve.visitor_key) AS c
        FROM visit_events ve
        LEFT JOIN users u ON u.id = ve.user_id
        WHERE ve.visit_date = ?
          AND (ve.user_id IS NULL OR COALESCE(u.role, 'user') != 'admin')
        ''',
        (target_date,),
    ).fetchone()
    return row['c'] if row else 0


def daily_new_returning_visitors(target_date):
    rows = get_db().execute(
        """
        WITH non_admin_visits AS (
            SELECT ve.visitor_key, ve.visit_date
            FROM visit_events ve
            LEFT JOIN users u ON u.id = ve.user_id
            WHERE ve.user_id IS NULL OR COALESCE(u.role, 'user') != 'admin'
        ), first_seen AS (
            SELECT visitor_key, MIN(visit_date) AS first_visit_date
            FROM non_admin_visits
            GROUP BY visitor_key
        ), today_visitors AS (
            SELECT DISTINCT visitor_key
            FROM non_admin_visits
            WHERE visit_date = ?
        )
        SELECT
            SUM(CASE WHEN first_seen.first_visit_date = ? THEN 1 ELSE 0 END) AS new_visitors,
            SUM(CASE WHEN first_seen.first_visit_date < ? THEN 1 ELSE 0 END) AS returning_visitors
        FROM today_visitors
        JOIN first_seen ON first_seen.visitor_key = today_visitors.visitor_key
        """,
        (target_date, target_date, target_date),
    ).fetchone()
    return {
        'new_visitors': int(rows['new_visitors'] or 0) if rows else 0,
        'returning_visitors': int(rows['returning_visitors'] or 0) if rows else 0,
    }


def last_7_days_uv():
    today = datetime.now().date()
    values = []
    for offset in range(6, -1, -1):
        date_value = (today - timedelta(days=offset)).strftime('%Y-%m-%d')
        values.append({'date': date_value, 'uv': daily_uv_count(date_value)})
    return values
