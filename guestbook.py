from flask import Blueprint, jsonify, request

from admin_pagination import parse_page, parse_page_size
from auth import admin_required, current_user, get_client_ip
from db import get_db
from guestbook_service import create_message, delete_message, list_messages
from route_response import respond_service_result

guestbook_bp = Blueprint('guestbook', __name__)


@guestbook_bp.post('/api/guestbook')
def post_message():
    user = current_user()
    ip = get_client_ip()
    result, service_error, status_code = create_message(user, request.get_json(silent=True) or {}, ip)
    return respond_service_result(result, service_error, status_code)


@guestbook_bp.get('/api/guestbook')
def get_messages():
    admin, error = admin_required()
    if error:
        return error
    page = parse_page(request.args)
    page_size = parse_page_size(request.args, default=20, maximum=100)
    return jsonify(list_messages(get_db(), page, page_size))


@guestbook_bp.delete('/api/guestbook/<int:message_id>')
def delete_single_message(message_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = delete_message(get_db(), message_id)
    return respond_service_result(result, service_error, status_code)
