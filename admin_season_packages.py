"""Authenticated upload/preview/publish API and guarded immutable resources."""

import json

from flask import Blueprint, abort, current_app, jsonify, request, send_file, send_from_directory

from auth import admin_required
from db import get_db
from season_data_repository import baseline_catalog, package_root, release_root, preview_suffix
from season_package_format import PackageError, safe_path, require
from season_package_service import (
    receive_package,
    release_payload,
    active_state,
    change_job,
    refresh_report,
    publish,
)

season_packages_bp = Blueprint('season_packages', __name__)


@season_packages_bp.before_request
def authenticate():
    if request.path.startswith('/api/admin/'):
        _, error = admin_required()
        if error:
            return error
        request.max_content_length = current_app.config['SEASON_PACKAGE_MAX_BYTES'] + 1024 * 1024


@season_packages_bp.errorhandler(PackageError)
def invalid_package(error):
    get_db().rollback()
    return jsonify(error=str(error)), 400


# Lifecycle group of a package, computed in SQL so lists can be filtered and counted per group.
GROUP_SQL = """CASE WHEN a.release_id = p.id THEN 'online'
    WHEN p.state IN ('queued','validating') THEN 'processing'
    WHEN p.state = 'ready' AND p.published_at IS NULL THEN 'pending'
    WHEN p.state = 'ready' THEN 'history'
    ELSE 'closed' END"""
PACKAGE_COLUMNS = """p.id,p.package_id,p.season_id,p.game_version,p.data_revision,p.filename,p.total_bytes,p.state,
    p.created_at,p.published_at,j.status AS job_status,j.stage,j.progress,j.message"""
PACKAGE_FROM = """FROM season_release_packages p JOIN season_import_jobs j ON j.release_id=p.id
    LEFT JOIN season_active_releases a ON a.season_id=p.season_id"""
PAGE_SIZE = 20


@season_packages_bp.get('/api/admin/season-packages')
def list_packages():
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        return jsonify(error='页码无效'), 400
    catalog = baseline_catalog()
    season_id = request.args.get('season_id') or ''
    if season_id and season_id not in {s['season_id'] for s in catalog}:
        return jsonify(error='赛季不存在'), 400
    group = request.args.get('group') or ''
    if group not in ('', 'history', 'closed'):
        return jsonify(error='分组无效'), 400
    scope, params = ('WHERE p.season_id=?', [season_id]) if season_id else ('WHERE 1=1', [])
    db = get_db()
    if group:
        # Settled packages are only loaded on demand, one page at a time.
        where = f'{scope} AND {GROUP_SQL}=?'
        rows = db.execute(
            f'SELECT {PACKAGE_COLUMNS},{GROUP_SQL} AS grp {PACKAGE_FROM} {where} '
            'ORDER BY p.created_at DESC,p.id DESC LIMIT ? OFFSET ?',
            (*params, group, PAGE_SIZE, (page - 1) * PAGE_SIZE),
        ).fetchall()
        total = db.execute(f'SELECT COUNT(*) AS n {PACKAGE_FROM} {where}', (*params, group)).fetchone()['n']
        return jsonify(items=[dict(r) for r in rows], total=total, page=page, group=group)

    # Packages that are live or still need attention are few, so they are always listed in full.
    rows = db.execute(
        f'SELECT {PACKAGE_COLUMNS},{GROUP_SQL} AS grp {PACKAGE_FROM} '
        f"{scope} AND {GROUP_SQL} IN ('online','processing','pending') "
        'ORDER BY p.created_at DESC,p.id DESC LIMIT 200',
        params,
    ).fetchall()
    counts = {row['grp']: row['n'] for row in db.execute(
        f'SELECT {GROUP_SQL} AS grp, COUNT(*) AS n {PACKAGE_FROM} {scope} GROUP BY {GROUP_SQL}', params).fetchall()}
    events = db.execute(
        f'''SELECT e.id,e.season_id,e.release_id,e.previous_release_id,e.action,e.status,e.detail_json,e.created_at,
        p.game_version,p.data_revision,q.game_version AS previous_game_version,q.data_revision AS previous_data_revision,
        u.nickname AS actor_name
        FROM season_release_events e
        LEFT JOIN season_release_packages p ON p.id=e.release_id
        LEFT JOIN season_release_packages q ON q.id=e.previous_release_id
        LEFT JOIN users u ON u.id=e.actor_id
        {'WHERE e.season_id=?' if season_id else ''}
        ORDER BY e.created_at DESC,e.id DESC LIMIT 30''',
        params,
    ).fetchall()
    # One query for every season's counters and one for every active release, instead of one per season.
    stats = {
        row['season_id']: dict(row)
        for row in db.execute(
            f'''SELECT p.season_id, COUNT(*) AS total,
            SUM(CASE WHEN {GROUP_SQL}='processing' THEN 1 ELSE 0 END) AS processing,
            SUM(CASE WHEN {GROUP_SQL}='pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN p.state='rejected' THEN 1 ELSE 0 END) AS rejected,
            MAX(p.created_at) AS latest_upload
            {PACKAGE_FROM} GROUP BY p.season_id'''
        ).fetchall()
    }
    actives = {
        row['season_id']: dict(row)
        for row in db.execute(
            '''SELECT a.*,p.package_id,p.game_version,p.data_revision FROM season_active_releases a
            LEFT JOIN season_release_packages p ON p.id=a.release_id'''
        ).fetchall()
    }
    empty = {'total': 0, 'processing': 0, 'pending': 0, 'rejected': 0, 'latest_upload': None}
    return jsonify(
        items=[dict(r) for r in rows],
        counts={key: counts.get(key, 0) for key in ('online', 'processing', 'pending', 'history', 'closed')},
        season_id=season_id or None,
        seasons=[{**s,
                  'active': actives.get(s['season_id']) or {'season_id': s['season_id'], 'release_id': None,
                                                           'previous_release_id': None, 'revision': 0},
                  'stats': {k: v for k, v in stats.get(s['season_id'], empty).items() if k != 'season_id'}}
                 for s in catalog],
        events=[_event_payload(r) for r in events],
        max_bytes=current_app.config['SEASON_PACKAGE_MAX_BYTES'],
    )


def _event_payload(row):
    """Name the package versions and surface the reason, so the log reads without opening JSON."""
    event = {k: row[k] for k in row.keys() if k != 'detail_json'}
    try:
        detail = json.loads(row['detail_json'] or '{}')
    except ValueError:
        detail = {}
    event['detail'] = {
        'message': detail.get('message') or None,
        'warning_count': len(detail.get('warnings') or []),
        'auto_restored': detail.get('auto_restored'),
        'revision': detail.get('revision'),
    }
    return event


@season_packages_bp.post('/api/admin/season-packages')
def upload_package():
    actor, _ = admin_required()
    file = request.files.get('file')
    if not file or not file.filename or not file.filename.lower().endswith('.zip'):
        return jsonify(error='请选择一个 ZIP 赛季更新包'), 400
    payload, created = receive_package(file.stream, file.filename, actor['id'])
    return jsonify(package=payload, reused=not created), 202 if created else 200


@season_packages_bp.get('/api/admin/season-packages/<release_id>')
def get_package(release_id):
    value = release_payload(release_id)
    if not value:
        abort(404)
    # The file list is large and not needed by the UI.
    value['manifest'] = {k: v for k, v in value['manifest'].items() if k != 'files'}
    return jsonify(value)


@season_packages_bp.post('/api/admin/season-packages/<release_id>/<action>')
def package_action(release_id, action):
    actor, _ = admin_required()
    if action in ('cancel', 'retry'):
        return jsonify(change_job(release_id, action, actor['id']))
    if action == 'compare':
        return jsonify(refresh_report(release_id))
    if action != 'publish':
        abort(404)
    value = release_payload(release_id)
    if not value:
        abort(404)
    data = request.get_json(silent=True) or {}
    require(isinstance(data, dict), '请求内容必须是 JSON 对象')
    if (
        type(data.get('expected_revision')) is not int
        or data['expected_revision'] != active_state(value['season_id'])['revision']
    ):
        return jsonify(error='线上版本已变化，请重新比较'), 409
    state = publish(
        value['season_id'],
        release_id,
        data['expected_revision'],
        actor['id'],
        data.get('acknowledge_warnings') is True,
    )
    return jsonify(active=state, package=release_payload(release_id))


@season_packages_bp.post('/api/admin/seasons/<season_id>/rollback')
def rollback_package(season_id):
    actor, _ = admin_required()
    data = request.get_json(silent=True) or {}
    require(isinstance(data, dict), '请求内容必须是 JSON 对象')
    expected = data.get('expected_revision')
    state = active_state(season_id)
    if type(expected) is not int or expected != state['revision']:
        return jsonify(error='线上版本已变化，请刷新后重试'), 409
    if state['revision'] == 0:
        return jsonify(error='此赛季尚未发布过更新包'), 400
    target = data.get('release_id', state['previous_release_id'])
    if target:
        package = release_payload(target)
        if not package or not package['published_at']:
            return jsonify(error='只能回滚至历史已发布版本'), 400
    return jsonify(active=publish(season_id, target, expected, actor['id'], True, rollback=True))


@season_packages_bp.get('/api/admin/season-packages/<release_id>/download')
def download_package(release_id):
    package = release_payload(release_id)
    if not package:
        abort(404)
    return send_file(
        package_root() / 'uploads' / f'{release_id}.zip',
        as_attachment=True,
        download_name=package['filename'],
        max_age=0,
    )


@season_packages_bp.get('/season-assets/<release_id>/<path:filename>')
def package_asset(release_id, filename):
    root = release_root(release_id)
    package = (
        get_db()
        .execute(
            'SELECT * FROM season_release_packages WHERE id=? AND state=?', (release_id, 'ready')
        )
        .fetchone()
    )
    if not package:
        abort(404)
    from season_visibility import is_public_anywhere

    public = bool(package['published_at']) and is_public_anywhere(package['season_id'])
    if not public:
        _, error = admin_required()
        if error:
            abort(404)
    try:
        safe_path(filename)
    except PackageError:
        abort(404)
    manifest = json.loads(package['manifest_json'])
    if filename not in manifest['files'] or not filename.startswith(('data/', 'assets/')):
        abort(404)
    response = send_from_directory(root, filename, conditional=True)
    # Revalidate authorization/visibility even for old public assets.
    response.headers['Cache-Control'] = (
        'public, max-age=0, must-revalidate' if public else 'private, no-store'
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Vary'] = 'Cookie'
    return response


def register_preview_context(app):
    @app.before_request
    def check_preview():
        if request.args.get('preview_release'):
            if request.method not in ('GET', 'HEAD'):
                return jsonify(error='预览模式不能执行写入操作'), 400
            preview_suffix()  # Enforce authorization even before template render.

    @app.context_processor
    def preview_context():
        return {
            'season_preview_suffix': preview_suffix(),
            'season_preview_id': request.args.get('preview_release'),
        }

    @app.after_request
    def preview_headers(response):
        if request.args.get('preview_release'):
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        elif request.path == '/api/season-catalog':
            response.headers['Cache-Control'] = 'public, max-age=0, must-revalidate'
        return response
