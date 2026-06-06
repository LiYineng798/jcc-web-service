from analytics import record_growth_event, sanitize_growth_payload
from auth import get_client_ip
from history import list_recent_copies, list_recent_views, record_recent_copy, record_recent_view, sync_recent_history
from lineups_utils import lineup_is_visible_to_user, lineup_row
from visits import ensure_visitor_token


def record_authenticated_growth_event(user, event_name, ref_lineup_id=None, payload=None, page_key=None):
    if not user or user['role'] == 'admin':
        return None
    visitor_token, _ = ensure_visitor_token()
    record_growth_event(
        event_name=event_name,
        user_id=user['id'],
        visitor_token=visitor_token,
        ip_address=get_client_ip(),
        ref_lineup_id=ref_lineup_id,
        page_key=page_key,
        payload=payload or {},
    )
    return visitor_token


def record_lineup_view_payload(user, lineup_id):
    row = lineup_row(lineup_id)
    if not lineup_is_visible_to_user(row, user):
        return None, '阵容不存在', 404
    record_recent_view(user['id'], lineup_id)
    return {'ok': True}, None, 201


def list_recent_views_payload(user, limit=20):
    return list_recent_views(user['id'], limit=limit, user=user)


def list_recent_copies_payload(user, limit=20):
    return list_recent_copies(user['id'], limit=limit, user=user)


def record_recent_copy_payload(user, lineup_id):
    record_recent_copy(user['id'], lineup_id)
    return {'ok': True}, None, 200


def sync_recent_history_payload(user, data):
    payload = data or {}
    sync_recent_history(user['id'], payload.get('views', []), payload.get('copies', []))
    return {'ok': True}, None, 200


def ingest_growth_event_payload(data, user, ip_address):
    payload, error = sanitize_growth_payload(data or {})
    if error:
        return None, None, error, 400
    visitor_token, created = ensure_visitor_token()
    if not (user and user['role'] == 'admin'):
        record_growth_event(
            event_name=payload['event_name'],
            user_id=user['id'] if user else None,
            visitor_token=visitor_token,
            ip_address=ip_address,
            ref_lineup_id=payload['ref_lineup_id'],
            page_key=payload['page_key'],
            payload=payload['payload'],
        )
    return {'ok': True}, {'visitor_token': visitor_token, 'created': created}, None, 201
