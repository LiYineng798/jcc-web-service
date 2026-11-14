"""Deck activity collection: append-only events written inside the originating transaction.

Relationship tables (likes, favorites, five-minute copies) stay authoritative for current totals;
these rows only describe what happened and when. Nothing here commits.
"""
import re
from datetime import datetime

from flask import has_request_context, request

from db import now_text
from device_type import request_device_type

STARTED_KEY = 'deck_analytics_started_at'
ACTIVITY_ACTIONS = {'published', 'hidden', 'restored', 'deleted', 'reviewed', 'like', 'favorite_add', 'favorite_remove'}
ACTION_ID = re.compile(r'^[A-Za-z0-9-]{8,64}$')
VISITOR_COOKIE = 'visitor_token'


def mark_started(db):
    """Idempotently record when collection began, in the transaction of the event itself."""
    db.execute('INSERT INTO app_settings (setting_key, setting_value, updated_at) VALUES (?, ?, ?) '
               'ON CONFLICT (setting_key) DO NOTHING', (STARTED_KEY, now_text(), now_text()))


def started_at(db):
    row = db.execute('SELECT setting_value FROM app_settings WHERE setting_key = ?', (STARTED_KEY,)).fetchone()
    return row['setting_value'] if row else None


def record_activity(db, deck_id, action, user_id=None):
    if action not in ACTIVITY_ACTIONS:
        raise ValueError(f'unknown deck activity {action}')
    mark_started(db)
    db.execute('INSERT INTO orange_deck_activity_events (deck_id, user_id, action, created_at) VALUES (?, ?, ?, ?)',
               (deck_id, user_id, action, now_text()))


def actor_key(user, ip_address):
    """Server-side identity for copy signals; a freshly minted, unsent cookie never counts as a visitor."""
    if user:
        return f"user:{user['id']}"
    token = request.cookies.get(VISITOR_COOKIE, '').strip() if has_request_context() else ''
    if token:
        return f'visitor:{token[:64]}'
    return f"ip:{ip_address or '0.0.0.0'}"


def clean_action_id(value):
    if value in (None, ''):
        return None
    value = str(value).strip()
    return value if ACTION_ID.match(value) else False


def is_prefetch():
    if not has_request_context():
        return False
    purpose = (request.headers.get('Sec-Purpose') or request.headers.get('Purpose') or '').lower()
    return 'prefetch' in purpose or 'prerender' in purpose


def record_visit(db, surface, user, deck_id=None):
    """Daily distinct visit of a rendered library tab or public detail; never a pageview."""
    from visits import is_bot_request
    if surface not in ('library', 'detail') or (surface == 'detail') != (deck_id is not None):
        raise ValueError('invalid deck visit surface')
    if is_prefetch() or is_bot_request() or request.args.get('preview_release'):
        return False
    if user and user['role'] in ('admin', 'automation'):
        return False
    if user:
        visitor_key = f"user:{user['id']}"
    else:
        token = request.cookies.get(VISITOR_COOKIE, '').strip()
        if not token:
            return False  # Cookie-less clients cannot be deduplicated, as with page visits.
        visitor_key = f'guest:{token[:64]}'
    mark_started(db)
    conflict = 'visit_date, visitor_key' if surface == 'library' else 'visit_date, visitor_key, deck_id'
    # Explicit partial-index target: duplicates are expected, other constraint errors are not swallowed.
    cursor = db.execute(
        'INSERT INTO orange_deck_visit_events (visit_date, visitor_key, user_id, surface, deck_id, device_type, created_at) '
        f"VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT ({conflict}) WHERE surface = '{surface}' DO NOTHING",
        (datetime.now().strftime('%Y-%m-%d'), visitor_key, user['id'] if user else None, surface,
         deck_id, request_device_type(), now_text()))
    return bool(cursor.rowcount)
