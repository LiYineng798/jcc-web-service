from flask import Blueprint, jsonify

from patch_note_service import get_public_patch_note, list_public_patch_notes
from route_response import respond_service_result
from visits import tracked_template_response

patch_notes_bp = Blueprint('patch_notes', __name__)


@patch_notes_bp.get('/patch-notes')
def patch_notes_page():
    return tracked_template_response('patch_notes.html', 'patch_notes')


@patch_notes_bp.get('/patch-notes/<int:patch_note_id>')
def patch_note_detail_page(patch_note_id):
    return tracked_template_response('patch_note_detail.html', 'patch_note_detail', patch_note_id=patch_note_id)


@patch_notes_bp.get('/api/patch-notes')
def public_patch_notes():
    return jsonify(list_public_patch_notes())


@patch_notes_bp.get('/api/patch-notes/<int:patch_note_id>')
def public_patch_note_detail(patch_note_id):
    payload, service_error, status_code = get_public_patch_note(patch_note_id)
    return respond_service_result(payload, service_error, status_code)
