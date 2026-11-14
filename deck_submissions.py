"""Deck submission routes: identity, parameters and private responses; rules live in deck_submission_service."""
from flask import Blueprint, abort, jsonify, redirect, request

from auth import admin_required, login_required
from db import get_db
from deck_submission_service import (
    LIMITS,
    SubmissionError,
    admin_act,
    admin_detail,
    admin_list,
    create_submission,
    detail_for_submitter,
    list_mine,
    publish,
    save_draft,
    update_by_submitter,
    withdraw,
)
from lineups_utils import parse_positive_int
from orange_deck_service import DeckError
from seo import make_seo
from visits import tracked_template_response

deck_submissions_bp = Blueprint('deck_submissions', __name__)


@deck_submissions_bp.errorhandler(DeckError)
def submission_error(error):
    get_db().rollback()
    return jsonify({'error': str(error), **getattr(error, 'data', {})}), error.status


@deck_submissions_bp.after_request
def private_response(response):
    # Submissions, histories and review notes are private to the submitter and admins.
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@deck_submissions_bp.post('/api/deck-submissions')
def create_api():
    user, error = login_required()
    if error:
        return error
    submission, replayed = create_submission(user, request.get_json(silent=True))
    return jsonify({**submission, 'replayed': replayed}), 200 if replayed else 201


@deck_submissions_bp.get('/api/me/deck-submissions')
def mine_api():
    user, error = login_required()
    if error:
        return error
    return jsonify(list_mine(user, request.args.get('status', 'all'), parse_positive_int(request.args.get('page'), 1),
                             parse_positive_int(request.args.get('page_size'), 10)))


@deck_submissions_bp.get('/api/me/deck-submissions/<int:submission_id>')
def detail_api(submission_id):
    user, error = login_required()
    if error:
        return error
    return jsonify(detail_for_submitter(user, submission_id))


@deck_submissions_bp.put('/api/me/deck-submissions/<int:submission_id>')
def update_api(submission_id):
    user, error = login_required()
    if error:
        return error
    return jsonify(update_by_submitter(user, submission_id, request.get_json(silent=True)))


@deck_submissions_bp.post('/api/me/deck-submissions/<int:submission_id>/withdraw')
def withdraw_api(submission_id):
    user, error = login_required()
    if error:
        return error
    return jsonify(withdraw(user, submission_id, request.get_json(silent=True)))


@deck_submissions_bp.get('/api/admin/deck-submissions')
def admin_list_api():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(admin_list(admin, request.args.get('status', 'pending'), request.args.get('q', ''),
                              parse_positive_int(request.args.get('page'), 1), parse_positive_int(request.args.get('page_size'), 20)))


@deck_submissions_bp.get('/api/admin/deck-submissions/<int:submission_id>')
def admin_detail_api(submission_id):
    admin, error = admin_required()
    if error:
        return error
    return jsonify(admin_detail(admin, submission_id))


@deck_submissions_bp.put('/api/admin/deck-submissions/<int:submission_id>/draft')
def draft_api(submission_id):
    admin, error = admin_required()
    if error:
        return error
    return jsonify(save_draft(admin, submission_id, request.get_json(silent=True)))


@deck_submissions_bp.post('/api/admin/deck-submissions/<int:submission_id>/publish')
def publish_api(submission_id):
    admin, error = admin_required()
    if error:
        return error
    return jsonify(publish(admin, submission_id, request.get_json(silent=True)))


@deck_submissions_bp.post('/api/admin/deck-submissions/<int:submission_id>/<action>')
def admin_action_api(submission_id, action):
    admin, error = admin_required()
    if error:
        return error
    return jsonify(admin_act(admin, submission_id, action, request.get_json(silent=True)))


def _page(template, page_key, title, **context):
    return tracked_template_response(template, page_key, limits=LIMITS,
                                     seo=make_seo(title=f'{title} - 金铲铲阵容库', description='卡组投稿进度。',
                                                  path=request.path, noindex=True), **context)


@deck_submissions_bp.get('/me/deck-submissions')
def mine_page():
    user, error = login_required()
    if error:
        return redirect('/auth')
    return _page('deck_submissions.html', 'deck_submissions', '我的卡组投稿', submission_id='')


@deck_submissions_bp.get('/me/deck-submissions/<int:submission_id>')
def detail_page(submission_id):
    user, error = login_required()
    if error:
        return redirect('/auth')
    try:
        detail_for_submitter(user, submission_id)
    except SubmissionError:
        abort(404)
    return _page('deck_submissions.html', 'deck_submissions', '卡组投稿进度', submission_id=submission_id)


@deck_submissions_bp.get('/admin/deck-submissions/<int:submission_id>/edit')
def editor_page(submission_id):
    from orange_creator_service import creator_config
    from orange_deck_service import LIMITS as DECK_LIMITS
    admin, error = admin_required()
    if error:
        return redirect('/auth')
    try:
        admin_detail(admin, submission_id)
    except SubmissionError:
        abort(404)
    return tracked_template_response(
        'orange_deck_form.html', 'orange_deck_editor', deck_id='', submission_id=submission_id, creator_data=creator_config(),
        limits=DECK_LIMITS, seo=make_seo(title='完善投稿卡组 - 金铲铲阵容库', description='完善用户投稿的卡组。',
                                         path=request.path, noindex=True))
