"""Session-protected data for the restricted browser workspace."""
import json

from flask import Blueprint, g, jsonify, request

from admin_dashboard_service import build_admin_copy_rank_payload, build_admin_overview_payload
from audit import write_audit
from auth import admin_required, login_required
from automation_service import (
    AutomationError, session_account, require_scope, lock_account, change_account, create_account, import_lineups,
    list_accounts, request_limited, utc_now,
)
from daily_report_service import get_daily_report, list_daily_reports, normalize_report_date
from db import get_db
from lineups_utils import season_choice_map

automation_bp = Blueprint('automation', __name__)
COPY_FIELDS = ('rank', 'target_type', 'target_id', 'season_id', 'season_name', 'copies',
               'unique_visitors', 'title', 'tier', 'lineup_id', 'uploader', 'uploader_attribution')


def project(item, keys):
    return {key: item[key] for key in keys if key in item}


def json_body():
    if request.content_length is None:
        raise AutomationError('请提供 Content-Length', 411)
    if request.content_length > 100000:
        raise AutomationError('请求内容过大', 413)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AutomationError('请求必须是 JSON 对象')
    return data


@automation_bp.errorhandler(AutomationError)
def handle_error(error):
    get_db().rollback()
    return jsonify(error=str(error)), error.status


@automation_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Robots-Tag'] = 'noindex'
    return response


@automation_bp.before_request
def authorize():
    if request.path.startswith('/api/admin/automation-accounts'):
        admin, error = admin_required()
        if error:
            return error
        g.automation_admin = admin
        return None
    user, error = login_required()
    if error:
        return error
    if user['role'] != 'automation':
        raise AutomationError('需要受限后台账号', 403)
    if request_limited(get_db(), user['id'], write=request.method == 'POST'):
        raise AutomationError('操作过于频繁，请稍后重试', 429)
    account = session_account(get_db(), user['id'])
    if not account:
        raise AutomationError('账号已过期或停用', 401)
    g.automation_account = account
    # Record the endpoint only: no credentials, search text or request body.
    db = get_db()
    db.execute('UPDATE automation_accounts SET last_used_at=? WHERE user_id=?', (utc_now(), account['user_id']))
    write_audit(account['user_id'], 'automation_request', 'automation_workspace',
                after={'endpoint': request.endpoint, 'method': request.method})
    db.commit()


@automation_bp.route('/api/admin/automation-accounts', methods=['GET', 'POST'])
def accounts():
    db = get_db()
    if request.method == 'GET':
        return jsonify(list_accounts(db))
    return jsonify(create_account(db, g.automation_admin['id'], json_body())), 201


@automation_bp.route('/api/admin/automation-accounts/<int:user_id>', methods=['PUT', 'DELETE'])
def account(user_id):
    action = 'delete' if request.method == 'DELETE' else 'update'
    return jsonify(change_account(get_db(), g.automation_admin['id'], user_id,
                                  {} if action == 'delete' else json_body(), action))


@automation_bp.get('/api/admin/assistant/me')
def me():
    account = g.automation_account
    return jsonify(expires_at=account['expires_at'], can_touch=bool(account['can_touch']),
                   touch_seasons=json.loads(account['touch_seasons_json']),
                   can_import=bool(account['can_import']),
                   allowed_seasons=json.loads(account['allowed_seasons_json']),
                   limits={'rows_per_import': 50, 'write_requests_per_hour': 10, 'read_requests_per_minute': 60})


@automation_bp.get('/api/admin/assistant/overview')
def overview():
    data = build_admin_overview_payload(get_db())
    # Only aggregate metrics; future top-level backend fields stay private.
    return jsonify({
        'stats': {key: value for key, value in data.get('stats', {}).items() if type(value) in (int, float)},
        'traffic_7d': [project(row, ('date', 'uv', 'pv', 'label')) for row in data.get('traffic_7d', [])],
    })


def date_argument(value):
    date = normalize_report_date(value)
    if not date:
        raise AutomationError('日期应为 YYYY-MM-DD')
    return date


@automation_bp.get('/api/admin/assistant/copy-rank')
def copy_rank():
    date = date_argument(request.args['date']) if 'date' in request.args else None
    data = build_admin_copy_rank_payload(get_db(), date, limit=50, include_details=False)
    return jsonify(date=data['date'], items=[project(item, COPY_FIELDS) for item in data['items']])


@automation_bp.get('/api/admin/assistant/daily-reports')
def reports():
    return jsonify(items=list_daily_reports(limit=30))


@automation_bp.get('/api/admin/assistant/daily-reports/<date>')
def report(date):
    data = get_daily_report(date_argument(date))
    if data is None:
        raise AutomationError('日报尚未生成', 404)
    return jsonify({
        **project(data, ('report_date', 'generated_at', 'updated_at', 'previous_date')),
        'summary': {key: value for key, value in data.get('summary', {}).items() if type(value) in (int, float)},
        'hourly': {key: values for key, values in data.get('hourly', {}).items()
                   if key in ('uv', 'visits', 'copies') and isinstance(values, list)
                   and all(type(value) in (int, float) for value in values)},
        'top_pages': [project(item, ('page_key', 'label', 'visits', 'uv')) for item in data.get('top_pages', [])],
        'season_copy_rank': [project(item, ('season_id', 'season_name', 'copies', 'unique_visitors')) for item in data.get('season_copy_rank', [])],
        'top_copied': [project(item, COPY_FIELDS) for item in data.get('top_copied', [])],
    })


@automation_bp.get('/api/admin/assistant/lineup-seasons')
def seasons():
    return jsonify(seasons=[{'id': key, 'name': value.get('name') or key} for key, value in season_choice_map().items()])


@automation_bp.get('/api/admin/assistant/lineups')
def lineups():
    try:
        page = max(1, min(int(request.args.get('page', '1')), 10000))
    except ValueError:
        raise AutomationError('页码无效')
    season = request.args.get('season_id', '')
    if season not in season_choice_map():
        raise AutomationError('请选择可用的普通阵容赛季')
    db = get_db()
    rows = db.execute('''
        SELECT l.id, l.name, l.code, l.season_id, l.created_at, u.username AS uploader
        FROM lineups l JOIN users u ON u.id=l.user_id
        WHERE l.status='normal' AND l.season_id=? ORDER BY l.id DESC LIMIT 50 OFFSET ?
    ''', (season, (page - 1) * 50)).fetchall()
    return jsonify(items=[dict(row) for row in rows], page=page, page_size=50)


@automation_bp.post('/api/admin/assistant/lineups/bulk-import/preview')
def import_preview():
    return jsonify(import_lineups(get_db(), g.automation_account, json_body(), preview=True))


@automation_bp.post('/api/admin/assistant/lineups/bulk-import')
def import_commit():
    return jsonify(import_lineups(get_db(), g.automation_account, json_body()))


@automation_bp.get('/api/admin/assistant/live-seasons')
def live_seasons():
    from live_comps_helpers import read_live_comps_payload_for_season
    account = g.automation_account
    permitted = json.loads(account['touch_seasons_json']) if account['can_touch'] else []
    return jsonify(seasons=[{'id': key, 'name': value.get('name') or key,
                             'updated_at': read_live_comps_payload_for_season(key)[1]}
                            for key, value in season_choice_map().items() if key in permitted])


@automation_bp.post('/api/admin/assistant/live-seasons/<season_id>/touch')
def touch(season_id):
    from admin_live_comp_service import touch_admin_live_comps_season
    from route_response import respond_service_result
    account = lock_account(get_db(), g.automation_account)
    require_scope(account, 'can_touch', 'touch_seasons_json', season_id)
    data = json_body()
    if data:
        raise AutomationError('仅能将更新时间设为当前时间')
    return respond_service_result(*touch_admin_live_comps_season(g.automation_account['user_id'], season_id))
