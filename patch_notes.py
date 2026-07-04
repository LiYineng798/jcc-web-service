from flask import Blueprint, abort, jsonify

from patch_note_service import get_public_patch_note, list_public_patch_notes
from route_response import respond_service_result
from seo import article_json_ld, make_seo, truncate_text
from visits import tracked_template_response

patch_notes_bp = Blueprint('patch_notes', __name__)


@patch_notes_bp.get('/patch-notes')
def patch_notes_page():
    return tracked_template_response(
        'patch_notes.html',
        'patch_notes',
        seo=make_seo(title='金铲铲更新公告 - 金铲铲阵容库', description='查看金铲铲之战版本更新重点、公告摘要和官方原文归档。', path='/patch-notes'),
    )


@patch_notes_bp.get('/patch-notes/<int:patch_note_id>')
def patch_note_detail_page(patch_note_id):
    payload, service_error, status_code = get_public_patch_note(patch_note_id)
    if service_error:
        abort(status_code)
    title = f"{payload['title']} - 金铲铲更新公告"
    description = truncate_text(payload.get('summary_markdown') or payload['title'])
    path = f'/patch-notes/{patch_note_id}'
    seo = make_seo(
        title=title,
        description=description,
        path=path,
        og_type='article',
        json_ld=[article_json_ld(payload, path)],
    )
    return tracked_template_response(
        'patch_note_detail.html',
        'patch_note_detail',
        patch_note_id=patch_note_id,
        patch_note=payload,
        seo=seo,
    )


@patch_notes_bp.get('/api/patch-notes')
def public_patch_notes():
    return jsonify(list_public_patch_notes())


@patch_notes_bp.get('/api/patch-notes/<int:patch_note_id>')
def public_patch_note_detail(patch_note_id):
    payload, service_error, status_code = get_public_patch_note(patch_note_id)
    return respond_service_result(payload, service_error, status_code)
