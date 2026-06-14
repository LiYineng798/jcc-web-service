from flask import Blueprint, jsonify, request

from auth import current_user, get_client_ip, login_required
from lineup_account_service import build_author_profile_payload, build_my_dashboard_payload, list_my_reports_payload
from lineup_bridge_service import (
    ingest_growth_event_payload,
    list_recent_copies_payload,
    list_recent_views_payload,
    record_authenticated_growth_event,
    record_recent_copy_payload,
    record_lineup_view_payload,
    sync_recent_history_payload,
)
from lineup_interaction_service import (
    copy_lineup_record,
    favorite_lineup_record,
    like_lineup_record,
    report_lineup_record,
    unfavorite_lineup_record,
)
from lineup_read_service import build_lineup_detail_payload, build_lineups_list_payload
from lineup_write_service import create_lineup_record, delete_lineup_record, hide_lineup_record, update_lineup_record
from lineups_utils import lineup_season_manifest, parse_positive_int
from route_response import respond_service_result
from scoring import score_map
from visits import maybe_set_visitor_cookie

lineups_bp = Blueprint('lineups', __name__)


@lineups_bp.get('/api/lineup-seasons')
def lineup_seasons():
    return jsonify(lineup_season_manifest())


@lineups_bp.get('/api/lineups')
def list_lineups():
    user = current_user()
    wants_page = 'page' in request.args or 'page_size' in request.args
    page_size = parse_positive_int(request.args.get('page_size'), 10) if wants_page else None
    page = parse_positive_int(request.args.get('page'), 1) if wants_page else None
    return jsonify(build_lineups_list_payload(
        user=user,
        view=request.args.get('view', 'all'),
        sort=request.args.get('sort', 'latest'),
        query=request.args.get('q', '').strip(),
        season_id=request.args.get('season'),
        wants_page=wants_page,
        page=page,
        page_size=page_size,
    ))


@lineups_bp.get('/api/lineups/<int:lineup_id>')
def get_lineup(lineup_id):
    payload, service_error, status_code = build_lineup_detail_payload(lineup_id, current_user())
    return respond_service_result(payload, service_error, status_code)


@lineups_bp.get('/api/authors/<username>')
def author_profile(username):
    payload, service_error, status_code = build_author_profile_payload(username, current_user(), score_map())
    return respond_service_result(payload, service_error, status_code)


@lineups_bp.post('/api/lineups/<int:lineup_id>/view')
def record_lineup_view(lineup_id):
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = record_lineup_view_payload(user, lineup_id)
    return respond_service_result(result, service_error, status_code)


@lineups_bp.get('/api/me/recent-views')
def my_recent_views():
    user, error = login_required()
    if error:
        return error
    return jsonify(list_recent_views_payload(user, limit=20))


@lineups_bp.get('/api/me/recent-copies')
def my_recent_copies():
    user, error = login_required()
    if error:
        return error
    return jsonify(list_recent_copies_payload(user, limit=20))


@lineups_bp.post('/api/me/history/sync')
def sync_my_history():
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = sync_recent_history_payload(user, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@lineups_bp.get('/api/me/dashboard')
def my_dashboard():
    user, error = login_required()
    if error:
        return error
    return jsonify(build_my_dashboard_payload(user['id']))


@lineups_bp.get('/api/me/reports')
def my_reports():
    user, error = login_required()
    if error:
        return error
    return jsonify(list_my_reports_payload(user['id']))


@lineups_bp.post('/api/growth-events')
def ingest_growth_event():
    payload, cookie_meta, service_error, status_code = ingest_growth_event_payload(
        request.get_json(silent=True) or {},
        current_user(),
        get_client_ip(),
    )
    if service_error:
        return jsonify({'error': service_error}), status_code
    response = jsonify(payload)
    return maybe_set_visitor_cookie(response, cookie_meta['visitor_token'], cookie_meta['created']), status_code


@lineups_bp.post('/api/lineups')
def create_lineup():
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = create_lineup_record(user=user, data=request.get_json(silent=True) or {})
    if service_error:
        return respond_service_result(result, service_error, status_code)
    record_authenticated_growth_event(user, 'post_login_create_lineup', ref_lineup_id=result['id'], payload={'status': result['status']})
    return respond_service_result(result, service_error, status_code)


@lineups_bp.put('/api/lineups/<int:lineup_id>')
def update_lineup(lineup_id):
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = update_lineup_record(user=user, lineup_id=lineup_id, data=request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@lineups_bp.delete('/api/lineups/<int:lineup_id>')
def delete_lineup(lineup_id):
    user, error = login_required()
    if error:
        return error
    _, service_error, status_code = delete_lineup_record(user=user, lineup_id=lineup_id)
    return respond_service_result(None, service_error, status_code)


@lineups_bp.post('/api/lineups/<int:lineup_id>/hide')
def hide_lineup(lineup_id):
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = hide_lineup_record(user=user, lineup_id=lineup_id)
    return respond_service_result(result, service_error, status_code)


@lineups_bp.post('/api/lineups/<int:lineup_id>/like')
def like_lineup(lineup_id):
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = like_lineup_record(user, lineup_id)
    if service_error:
        return respond_service_result(result, service_error, status_code)
    record_authenticated_growth_event(user, 'post_login_like', ref_lineup_id=lineup_id)
    return respond_service_result(result, service_error, status_code)


@lineups_bp.post('/api/lineups/<int:lineup_id>/copy')
def copy_lineup(lineup_id):
    user = current_user()
    result, service_error, status_code = copy_lineup_record(user, lineup_id, get_client_ip(), source_page=request.args.get('source', ''))
    if service_error:
        return respond_service_result(result, service_error, status_code)
    if user:
        record_recent_copy_payload(user, lineup_id)
        record_authenticated_growth_event(user, 'post_login_copy', ref_lineup_id=lineup_id, payload={'counted': result['counted']})
    return respond_service_result(result, service_error, status_code)


@lineups_bp.post('/api/lineups/<int:lineup_id>/favorite')
def favorite_lineup(lineup_id):
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = favorite_lineup_record(user, lineup_id)
    if service_error:
        return respond_service_result(result, service_error, status_code)
    if result['created']:
        record_authenticated_growth_event(user, 'post_login_favorite', ref_lineup_id=lineup_id)
    return respond_service_result({'ok': True}, None, status_code)


@lineups_bp.delete('/api/lineups/<int:lineup_id>/favorite')
def unfavorite_lineup(lineup_id):
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = unfavorite_lineup_record(user, lineup_id)
    return respond_service_result(result, service_error, status_code)


@lineups_bp.post('/api/lineups/<int:lineup_id>/report')
def report_lineup(lineup_id):
    user, error = login_required()
    if error:
        return error
    result, service_error, status_code = report_lineup_record(
        user,
        lineup_id,
        (request.get_json(silent=True) or {}).get('reason', ''),
    )
    return respond_service_result(result, service_error, status_code)
