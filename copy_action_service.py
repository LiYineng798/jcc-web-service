from flask import has_request_context

from db import get_db, now_text
from visits import ensure_visitor_token


def clean_copy_source(value):
    source = str(value or '').strip().lower()
    safe = ''.join(char for char in source if char.isalnum() or char in {'-', '_'})
    return safe[:40]


def record_copy_action(
    target_type,
    target_id,
    user=None,
    ip_address=None,
    source_page='',
    success=True,
    counted=False,
    season_id=None,
):
    visitor_token = None
    if has_request_context():
        visitor_token, _ = ensure_visitor_token()
    lineup_id = int(target_id) if target_type == 'lineup' else None
    live_comp_id = str(target_id) if target_type == 'live_comp' else None
    get_db().execute(
        '''
        INSERT INTO copy_action_events (
            target_type, target_id, season_id, lineup_id, live_comp_id,
            user_id, visitor_token, ip_address, source_page,
            success, counted, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            str(target_type),
            str(target_id),
            season_id,
            lineup_id,
            live_comp_id,
            user['id'] if user else None,
            visitor_token,
            ip_address,
            clean_copy_source(source_page),
            1 if success else 0,
            1 if counted else 0,
            now_text(),
        ),
    )
