from flask import Blueprint, jsonify, request
from auth import admin_required, current_user
from experience_service import experience_summary, record_search_result

experience_bp = Blueprint('experience', __name__)


@experience_bp.post('/api/search-events')
def search_events():
    # The global guard compares against the session token; explicitly require
    # a header here even before the first /api/me has created a token.
    if not request.headers.get('X-CSRF-Token'):
        return jsonify(error='CSRF 校验失败'), 403
    try:
        limited = record_search_result(request.get_json(silent=True), current_user())
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return ('', 429 if limited else 204)


@experience_bp.get('/api/admin/experience')
def experience():
    _, error = admin_required()
    if error:
        return error
    try:
        payload = experience_summary(request.args.get('start'), request.args.get('end'), request.args.get('refresh')=='1')
    except ValueError as error:
        return jsonify(error=str(error)), 400
    response = jsonify(payload)
    response.headers['Cache-Control'] = 'private, no-store'
    return response
