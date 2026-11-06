"""Deck library routes: identity, parameters and responses; rules live in orange_deck_service."""
from flask import Blueprint, abort, jsonify, redirect, request

from auth import admin_required, current_user, get_client_ip, login_required
from db import get_db
from lineups_utils import parse_positive_int
from orange_creator_service import creator_config
from orange_deck_service import (
    LIMITS,
    DeckError,
    admin_list,
    admin_moderate,
    create_deck,
    delete_deck,
    export_payload,
    favorite,
    fork_deck,
    get_visible,
    like,
    list_decks,
    record_copy,
    resolve_formation,
    serialize,
    update_deck,
)
from settings_service import get_setting
from seo import breadcrumb_json_ld, make_seo, truncate_text, webpage_json_ld
from visits import tracked_template_response

orange_decks_bp = Blueprint('orange_decks', __name__)


@orange_decks_bp.errorhandler(DeckError)
def deck_error(error):
    get_db().rollback()
    return jsonify({'error': str(error)}), error.status


def _private(response, status=200):
    response.headers['Cache-Control'] = 'private, no-store'
    return response, status


@orange_decks_bp.get('/api/orange-decks')
def list_api():
    payload = list_decks(current_user(), request.args.get('tab', 'latest'), request.args.get('q', ''),
                         request.args.get('portal', ''), parse_positive_int(request.args.get('page'), 1),
                         parse_positive_int(request.args.get('page_size'), 10), share_base=request.url_root.rstrip('/'))
    return _private(jsonify(payload))


@orange_decks_bp.get('/api/orange-decks/<int:deck_id>')
def detail_api(deck_id):
    user = current_user()
    row = get_visible(deck_id, user)
    return _private(jsonify(serialize(row, user, detail=True, share_base=request.url_root.rstrip('/'))))


@orange_decks_bp.get('/api/orange-decks/<int:deck_id>/formation')
def formation_api(deck_id):
    # Loaded on demand when a list entry expands its board; no simulator or iframe per row.
    row = get_visible(deck_id, current_user())
    return _private(jsonify({'formation': resolve_formation(row)}))


@orange_decks_bp.get('/api/orange-decks/<int:deck_id>/export')
def export_api(deck_id):
    return _private(jsonify(export_payload(deck_id, current_user())))


@orange_decks_bp.post('/api/orange-decks')
def create_api():
    user, error = login_required()
    if error:
        return error
    return _private(jsonify(create_deck(user, request.get_json(silent=True))), 201)


@orange_decks_bp.put('/api/orange-decks/<int:deck_id>')
def update_api(deck_id):
    user, error = login_required()
    if error:
        return error
    return _private(jsonify(update_deck(user, deck_id, request.get_json(silent=True))))


@orange_decks_bp.delete('/api/orange-decks/<int:deck_id>')
def delete_api(deck_id):
    user, error = login_required()
    if error:
        return error
    delete_deck(user, deck_id)
    return '', 204


@orange_decks_bp.route('/api/orange-decks/<int:deck_id>/favorite', methods=['POST', 'DELETE'])
def favorite_api(deck_id):
    user, error = login_required()
    if error:
        return error
    return _private(jsonify(favorite(user, deck_id, request.method == 'POST')))


@orange_decks_bp.post('/api/orange-decks/<int:deck_id>/like')
def like_api(deck_id):
    user, error = login_required()
    if error:
        return error
    return _private(jsonify(like(user, deck_id)), 201)


@orange_decks_bp.post('/api/orange-decks/<int:deck_id>/fork')
def fork_api(deck_id):
    user, error = login_required()
    if error:
        return error
    return _private(jsonify(fork_deck(user, deck_id)), 201)


@orange_decks_bp.post('/api/orange-decks/<int:deck_id>/copy')
def copy_api(deck_id):
    # A first-time guest also needs the token issued by /api/me.
    if not request.headers.get('X-CSRF-Token'):
        return _private(jsonify(error='CSRF 校验失败'), 403)
    return _private(jsonify(record_copy(current_user(), deck_id, get_client_ip(), request.args.get('code_type', 'plan'))))


@orange_decks_bp.get('/api/admin/orange-decks')
def admin_list_api():
    admin, error = admin_required()
    if error:
        return error
    return _private(jsonify(admin_list(admin, request.args.get('status', 'all'), request.args.get('q', ''),
                                       parse_positive_int(request.args.get('page'), 1),
                                       parse_positive_int(request.args.get('page_size'), 20))))


@orange_decks_bp.post('/api/admin/orange-decks/<int:deck_id>/<action>')
def admin_moderate_api(deck_id, action):
    admin, error = admin_required()
    if error:
        return error
    return _private(jsonify(admin_moderate(admin, deck_id, action, request.get_json(silent=True))))


@orange_decks_bp.get('/orange-decks/<int:deck_id>')
def detail_page(deck_id):
    user = current_user()
    try:
        row = get_visible(deck_id, user)
    except DeckError:
        abort(404)
    path = f'/orange-decks/{deck_id}'
    deck = serialize(row, user, detail=True, share_base=request.url_root.rstrip('/'))
    cards = '、'.join(card['name'] for card in deck['cards'] if card)
    description = truncate_text(f"{deck['name']}：{cards}，推荐{deck['portal']['name']}，能量 {deck['energy']}/{deck['energy_limit']}。"
                                f"{deck['note']}")
    title = f"{deck['name']} - 大橘大利卡组 - 金铲铲阵容库"
    seo = make_seo(title=title, description=description, path=path, noindex=row['status'] != 'published',
                   json_ld=[webpage_json_ld(deck['name'], description, path), breadcrumb_json_ld([
                       {'name': '首页', 'path': '/'}, {'name': '卡组库', 'path': '/?library=decks'}, {'name': deck['name'], 'path': path}])])
    response = tracked_template_response('orange_deck_detail.html', 'orange_deck_detail', deck=deck,
                                         formation=resolve_formation(row), seo=seo,
                                         simulator_enabled=get_setting(get_db(), 'simulator_enabled', 'true') == 'true')
    # Public HTML still contains viewer-specific favorites and owner actions.
    response.headers['Cache-Control'] = 'private, no-store'
    return response


def _editor_page(deck_id):
    user, error = login_required()
    if error:
        return redirect('/auth')
    try:
        row = get_visible(deck_id, user)
    except DeckError:
        abort(404)
    if row['user_id'] != user['id']:
        abort(403)
    response = tracked_template_response(
        'orange_deck_form.html', 'orange_deck_editor', deck_id=deck_id, creator_data=creator_config(), limits=LIMITS,
        seo=make_seo(title='编辑卡组 - 金铲铲阵容库', description='编辑大橘大利三卡组合。',
                     path=f'/orange-decks/{deck_id}/edit', noindex=True),
    )
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@orange_decks_bp.get('/orange-decks/new')
def create_page():
    # Publishing lives on the shared page; keep the poster-tool hand-off parameter.
    return redirect('/lineup/new?type=deck' + ('&from=creator' if request.args.get('from') == 'creator' else ''))


@orange_decks_bp.get('/orange-decks/<int:deck_id>/edit')
def edit_page(deck_id):
    return _editor_page(deck_id)
