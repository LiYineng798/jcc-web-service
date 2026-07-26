import secrets
from datetime import datetime, timedelta

from flask import current_app, make_response, render_template, request

from auth import current_user, get_client_ip
from db import db_kind, get_db, now_text
from db_adapter import insert_ignore_sql

VISITOR_COOKIE_NAME = 'visitor_token'
VISITOR_COOKIE_MAX_AGE = 180 * 24 * 60 * 60

# Requests whose User-Agent contains one of these markers never write visit
# rows: crawlers do not echo cookies, so every hit would insert a brand-new
# guest row (a full sitemap pass is 300+ writes).
BOT_UA_MARKERS = (
    'bot', 'spider', 'crawler', 'slurp', 'petalbot', 'headless',
    'python-requests', 'python-urllib', 'curl/', 'wget/',
)


def is_bot_request():
    user_agent = (request.user_agent.string or '').lower()
    return any(marker in user_agent for marker in BOT_UA_MARKERS)


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
        insert_ignore_sql(
            'visit_events',
            ['visit_date', 'visitor_key', 'visitor_kind', 'user_id', 'visitor_token', 'ip_address', 'page_key', 'created_at'],
            ['visit_date', 'visitor_key', 'page_key'],
            db_kind(),
        ),
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
    # Only count identities that can deduplicate: logged-in users, or guests
    # who echoed the visitor cookie back. A cookie-less client (crawler,
    # curl, cookie-blocked browser) would mint a fresh token every request
    # and insert an uncollapsible row per page view. The first page view of
    # a genuine new visitor is uncounted; they count from the next request.
    should_record = user is not None or not created
    if should_record and not is_bot_request():
        record_page_visit(page_key, user=user, visitor_token=visitor_token, ip_address=get_client_ip())
    response = make_response(render_template(template_name, **context))
    return maybe_set_visitor_cookie(response, visitor_token, created)



def daily_new_returning_visitors(target_date):
    # Per-visitor prior-existence probe instead of a MIN() GROUP BY over the
    # whole history: O(today's UV x index seek) with
    # idx_visit_events_visitor_date, no longer O(all rows ever).
    rows = get_db().execute(
        """
        WITH today_visitors AS (
            SELECT DISTINCT ve.visitor_key
            FROM visit_events ve
            LEFT JOIN users u ON u.id = ve.user_id
            WHERE ve.visit_date = ?
              AND (ve.user_id IS NULL OR COALESCE(u.role, 'user') != 'admin')
        )
        SELECT
            SUM(CASE WHEN NOT EXISTS (
                SELECT 1 FROM visit_events prior
                WHERE prior.visitor_key = today_visitors.visitor_key
                  AND prior.visit_date < ?
            ) THEN 1 ELSE 0 END) AS new_visitors,
            SUM(CASE WHEN EXISTS (
                SELECT 1 FROM visit_events prior
                WHERE prior.visitor_key = today_visitors.visitor_key
                  AND prior.visit_date < ?
            ) THEN 1 ELSE 0 END) AS returning_visitors
        FROM today_visitors
        """,
        (target_date, target_date, target_date),
    ).fetchone()
    return {
        'new_visitors': int(rows['new_visitors'] or 0) if rows else 0,
        'returning_visitors': int(rows['returning_visitors'] or 0) if rows else 0,
    }


def daily_uv_series(start_date, end_date):
    rows = get_db().execute(
        '''
        SELECT ve.visit_date, COUNT(DISTINCT ve.visitor_key) AS uv
        FROM visit_events ve
        LEFT JOIN users u ON u.id = ve.user_id
        WHERE ve.visit_date BETWEEN ? AND ?
          AND (ve.user_id IS NULL OR COALESCE(u.role, 'user') != 'admin')
        GROUP BY ve.visit_date
        ORDER BY ve.visit_date
        ''',
        (start_date, end_date),
    ).fetchall()
    return {row['visit_date']: int(row['uv'] or 0) for row in rows}


def last_7_days_uv():
    today = datetime.now().date()
    start_date = (today - timedelta(days=6)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    series = daily_uv_series(start_date, end_date)
    return [
        {
            'date': (today - timedelta(days=offset)).strftime('%Y-%m-%d'),
            'uv': series.get((today - timedelta(days=offset)).strftime('%Y-%m-%d'), 0),
        }
        for offset in range(6, -1, -1)
    ]
