from flask import has_request_context, request

from db import get_db, now_text
from visits import ensure_visitor_token
from device_type import request_device_type


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
            success, counted, created_at, device_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            request_device_type(),
        ),
    )


def record_deck_copy_action(db, deck, code_type, actor_key, action_id, rank_eligible, counted,
                            user=None, ip_address=None, source_page=''):
    """One successful deck copy gesture; the caller owns the transaction and the idempotency race."""
    token = request.cookies.get('visitor_token', '').strip()[:64] or None if has_request_context() else None
    db.execute(
        '''
        INSERT INTO copy_action_events (
            target_type, target_id, season_id, deck_id, code_type, actor_key, client_action_id, rank_eligible,
            user_id, visitor_token, ip_address, source_page, success, counted, created_at, device_type
        )
        VALUES ('orange_deck', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        ''',
        (str(deck['id']), deck['season_id'], deck['id'], code_type, actor_key, action_id, 1 if rank_eligible else 0,
         user['id'] if user else None, token, ip_address, clean_copy_source(source_page), 1 if counted else 0,
         now_text(), request_device_type() if has_request_context() else 'unknown'),
    )
