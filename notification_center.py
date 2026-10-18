from flask import Blueprint, jsonify, request, render_template
from auth import admin_required, login_required
from db import get_db
from feedback_service import feedback_detail, feedback_for_source, update_feedback
from notification_service import list_inbox, mark_notice
from route_response import respond_service_result
from seo import make_seo

notification_center_bp = Blueprint('notification_center', __name__)


@notification_center_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@notification_center_bp.get('/api/me/notifications')
def inbox():
    user, error = login_required()
    return error or respond_service_result(*list_inbox(user, request.args))


@notification_center_bp.put('/api/me/notifications/<key>')
def mark(key):
    user, error = login_required()
    return error or respond_service_result(*mark_notice(user, key, request.get_json(silent=True)))


@notification_center_bp.get('/api/me/feedback/<int:feedback_id>')
def feedback(feedback_id):
    user, error = login_required()
    return error or respond_service_result(*feedback_detail(user, feedback_id))


@notification_center_bp.get('/api/admin/feedback/<source>/<int:source_id>')
def admin_feedback(source, source_id):
    user, error = admin_required()
    return error or respond_service_result(*feedback_for_source(user, source, source_id))


@notification_center_bp.post('/api/admin/feedback/<int:feedback_id>/reply')
def reply(feedback_id):
    user, error = admin_required()
    return error or respond_service_result(*update_feedback(get_db(), user, feedback_id, request.get_json(silent=True)))


@notification_center_bp.get('/me/feedback/<int:feedback_id>')
def feedback_page(feedback_id):
    user, error = login_required()
    if error:
        return error
    _, denied, code = feedback_detail(user, feedback_id)
    if denied:
        return jsonify({'error': denied}), code
    return render_template('feedback_detail.html', feedback_id=feedback_id,
                           seo=make_seo(title='反馈进度', description='查看反馈进度与站内回复', path=request.path, noindex=True))
