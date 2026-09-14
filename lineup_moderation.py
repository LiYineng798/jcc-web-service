from flask import Blueprint, request, jsonify

from auth import admin_required, login_required
from lineup_moderation_service import (
    list_notifications, moderate_lineup, moderation_detail, submit_revision, update_notification,
)
from route_response import respond_service_result
from db import get_db

lineup_moderation_bp = Blueprint('lineup_moderation', __name__)


@lineup_moderation_bp.get('/api/admin/lineup-moderation-summary')
def summary():
    user, error = admin_required()
    if error:
        return error
    count = get_db().execute("SELECT COUNT(*) AS c FROM lineup_moderation WHERE state='pending'").fetchone()['c']
    return jsonify({'pending': count})


@lineup_moderation_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@lineup_moderation_bp.get('/api/lineups/<int:lineup_id>/moderation')
def detail(lineup_id):
    user, error = login_required()
    if error:
        return error
    return respond_service_result(*moderation_detail(user, lineup_id))


@lineup_moderation_bp.post('/api/admin/lineups/<int:lineup_id>/moderation/<action>')
def moderate(lineup_id, action):
    user, error = admin_required()
    if error:
        return error
    return respond_service_result(*moderate_lineup(user, lineup_id, action, request.get_json(silent=True)))


@lineup_moderation_bp.post('/api/lineups/<int:lineup_id>/revision')
def submit(lineup_id):
    user, error = login_required()
    if error:
        return error
    return respond_service_result(*submit_revision(user, lineup_id, request.get_json(silent=True)))


@lineup_moderation_bp.get('/api/me/lineup-notifications')
def notifications():
    user, error = login_required()
    if error:
        return error
    return respond_service_result(*list_notifications(user, request.args))


@lineup_moderation_bp.put('/api/me/lineup-notifications/<int:lineup_id>')
def notification_state(lineup_id):
    user, error = login_required()
    if error:
        return error
    return respond_service_result(*update_notification(user, lineup_id, request.get_json(silent=True)))
