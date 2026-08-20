from flask import Blueprint, jsonify, request

from admin_audit_service import list_admin_audit_logs
from admin_dashboard_service import (
    build_admin_copy_rank_payload,
    build_admin_growth_payload,
    build_admin_overview_payload,
    build_admin_stats_payload,
)
from admin_live_comp_service import (
    add_admin_live_comp_manual_code,
    build_admin_live_comps_payload,
    create_admin_live_comps_season,
    list_admin_live_comps_seasons,
    touch_admin_live_comps_season,
    update_admin_live_comps_season,
)
from admin_lineup_service import (
    adjust_admin_lineup_score,
    build_admin_lineups_query,
    bulk_import_lineups,
    preview_bulk_import_lineups,
    update_admin_lineup,
)
from admin_pagination import paginate_rows, parse_page, parse_page_size
from admin_report_service import build_report_list_query, resolve_report
from admin_user_service import build_user_list_query, create_user, disable_user, update_user
from audit import write_audit
from auth import admin_required
from db import get_db
from daily_report_service import (
    ensure_daily_report,
    get_daily_report,
    list_daily_reports,
    normalize_report_date,
)
from lineups_serialization import serialize_lineup_row
from route_response import respond_service_result
from seo import make_seo
from notice_service import (
    _is_notice_enabled,
    activate_notice,
    create_notice,
    delete_saved_notice,
    get_notice,
    list_notices,
    save_notice,
    update_saved_notice,
)
from patch_note_service import create_patch_note, hide_patch_note, list_admin_patch_notes, update_patch_note
from scoring import score_map
from settings_service import get_settings, save_settings
from visits import tracked_template_response
from season_visibility import admin_payload, default_season_id, update_season

admin_bp = Blueprint('admin', __name__)

@admin_bp.get('/api/admin/season-display/<kind>')
def admin_season_display(kind):
    admin, error = admin_required()
    if error:
        return error
    if kind not in ('simulator', 'library'):
        return jsonify({'error': '展示类型无效'}), 400
    return jsonify({
        'items': admin_payload(kind),
        'default_season_id': default_season_id(kind),
    })


@admin_bp.put('/api/admin/season-display/<kind>/<season_id>')
def admin_update_season_display(kind, season_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = update_season(admin['id'], kind, season_id, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


def _parse_page():
    return parse_page(request.args)


def _parse_page_size(default=20, maximum=100):
    return parse_page_size(request.args, default=default, maximum=maximum)


def _paginate_rows(base_sql, count_sql, params, serializer=dict, default_page_size=20):
    page = _parse_page()
    page_size = _parse_page_size(default=default_page_size)
    return paginate_rows(get_db(), base_sql, count_sql, params, page, page_size, serializer=serializer)
@admin_bp.get('/admin')
def admin_page():
    admin, error = admin_required()
    if error:
        return error
    return tracked_template_response(
        'admin.html',
        'admin',
        seo=make_seo(title='金铲铲阵容库后台', description='金铲铲阵容库后台管理页面。', path='/admin', noindex=True),
    )


@admin_bp.get('/api/admin/users')
def admin_users():
    admin, error = admin_required()
    if error:
        return error
    base_sql, count_sql, params = build_user_list_query(request.args.get('q', ''))
    return jsonify(_paginate_rows(base_sql, count_sql, params, serializer=dict, default_page_size=20))


@admin_bp.post('/api/admin/users')
def admin_create_user():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = create_user(get_db(), admin['id'], request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.put('/api/admin/users/<int:user_id>')
def admin_update_user(user_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = update_user(get_db(), admin['id'], user_id, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.delete('/api/admin/users/<int:user_id>')
def admin_disable_user(user_id):
    admin, error = admin_required()
    if error:
        return error
    disable_user(get_db(), admin['id'], user_id)
    return '', 204


@admin_bp.get('/api/admin/lineups')
def admin_lineups():
    admin, error = admin_required()
    if error:
        return error
    base_sql, count_sql, params = build_admin_lineups_query(request.args.get('q', ''))
    scores = score_map()
    return jsonify(_paginate_rows(
        base_sql,
        count_sql,
        params,
        serializer=lambda row: serialize_lineup_row(row, scores, user=admin, admin=True),
        default_page_size=20,
    ))


@admin_bp.post('/api/admin/lineups/bulk-import')
def admin_bulk_import_lineups():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = bulk_import_lineups(get_db(), admin['id'], request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.post('/api/admin/lineups/bulk-import/preview')
def admin_preview_bulk_import_lineups():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = preview_bulk_import_lineups(get_db(), request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.get('/api/admin/patch-notes')
def admin_patch_notes():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(list_admin_patch_notes())


@admin_bp.post('/api/admin/patch-notes')
def admin_create_patch_note():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = create_patch_note(admin['id'], request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.put('/api/admin/patch-notes/<int:patch_note_id>')
def admin_update_patch_note(patch_note_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = update_patch_note(admin['id'], patch_note_id, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.delete('/api/admin/patch-notes/<int:patch_note_id>')
def admin_delete_patch_note(patch_note_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = hide_patch_note(admin['id'], patch_note_id)
    return respond_service_result(result, service_error, status_code)


@admin_bp.get('/api/admin/live-comps')
def admin_live_comps():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(build_admin_live_comps_payload(
        request.args.get('season'),
        page=_parse_page(),
        page_size=_parse_page_size(default=20, maximum=100),
    ))


@admin_bp.post('/api/admin/live-comps/<season_id>/<live_comp_id>/manual-code')
def admin_add_live_comp_manual_code(season_id, live_comp_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = add_admin_live_comp_manual_code(
        admin['id'],
        season_id,
        live_comp_id,
        request.get_json(silent=True) or {},
    )
    return respond_service_result(result, service_error, status_code)


@admin_bp.get('/api/admin/live-comps/seasons')
def admin_live_comps_seasons():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(list_admin_live_comps_seasons())


@admin_bp.post('/api/admin/live-comps/seasons')
def admin_create_live_comps_season():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = create_admin_live_comps_season(
        admin['id'],
        request.get_json(silent=True) or {},
    )
    return respond_service_result(result, service_error, status_code)


@admin_bp.put('/api/admin/live-comps/seasons/<season_id>')
def admin_update_live_comps_season(season_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = update_admin_live_comps_season(
        admin['id'],
        season_id,
        request.get_json(silent=True) or {},
    )
    return respond_service_result(result, service_error, status_code)


@admin_bp.post('/api/admin/live-comps/seasons/<season_id>/touch-updated-at')
def admin_touch_live_comps_season(season_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = touch_admin_live_comps_season(admin['id'], season_id)
    return respond_service_result(result, service_error, status_code)


@admin_bp.put('/api/admin/lineups/<int:lineup_id>')
def admin_update_lineup(lineup_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = update_admin_lineup(get_db(), admin['id'], lineup_id, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.post('/api/admin/lineups/<int:lineup_id>/adjust-score')
def admin_adjust_score(lineup_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = adjust_admin_lineup_score(get_db(), admin['id'], lineup_id, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.get('/api/admin/stats')
def admin_stats():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(build_admin_stats_payload(get_db()))


@admin_bp.get('/api/admin/overview')
def admin_overview():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(build_admin_overview_payload(get_db()))


@admin_bp.get('/api/admin/growth')
def admin_growth():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(build_admin_growth_payload(request.args.get('date')))


@admin_bp.get('/api/admin/copy-rank')
def admin_copy_rank():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(build_admin_copy_rank_payload(
        get_db(),
        request.args.get('date'),
        limit=_parse_page_size(default=10, maximum=50),
    ))


@admin_bp.get('/api/admin/daily-reports')
def admin_daily_reports():
    admin, error = admin_required()
    if error:
        return error
    return jsonify({'items': list_daily_reports(limit=_parse_page_size(default=30, maximum=100))})


@admin_bp.get('/api/admin/daily-reports/<date>')
def admin_daily_report_detail(date):
    admin, error = admin_required()
    if error:
        return error
    report = get_daily_report(date)
    if report is None:
        return jsonify({'error': '该日期还没有每日报告'}), 404
    return jsonify(report)


@admin_bp.post('/api/admin/daily-reports/<date>/generate')
def admin_generate_daily_report(date):
    admin, error = admin_required()
    if error:
        return error
    if normalize_report_date(date) is None:
        return jsonify({'error': '日期格式应为 YYYY-MM-DD'}), 400
    report = ensure_daily_report(date, force=True)
    if report is None:
        report = get_daily_report(date)
    if report is None:
        return jsonify({'error': '报告生成失败，请稍后重试'}), 500
    write_audit(
        admin['id'],
        'generate_daily_report',
        'daily_report',
        target_id=date,
        after={'report_date': report['report_date']},
    )
    return jsonify(report)


@admin_bp.get('/api/admin/audit-logs')
def admin_audit_logs():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(list_admin_audit_logs(get_db(), page=_parse_page(), page_size=_parse_page_size(default=30)))


@admin_bp.get('/api/admin/reports')
def admin_reports():
    admin, error = admin_required()
    if error:
        return error
    base_sql, count_sql, params = build_report_list_query(request.args.get('status', 'pending'))
    return jsonify(_paginate_rows(base_sql, count_sql, params, serializer=dict, default_page_size=20))


@admin_bp.post('/api/admin/reports/<int:report_id>/resolve')
def admin_resolve_report(report_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = resolve_report(get_db(), admin['id'], report_id, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.get('/api/admin/settings')
def admin_settings():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(get_settings(get_db()))


@admin_bp.put('/api/admin/settings')
def admin_update_settings():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = save_settings(get_db(), admin['id'], request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.get('/api/admin/notice')
def admin_get_notice():
    admin, error = admin_required()
    if error:
        return error
    db = get_db()
    notice = get_notice(db)
    return jsonify({
        'enabled': _is_notice_enabled(db),
        'active_id': notice.get('id'),
        'title': notice['title'],
        'message': notice['message'],
        'link_url': notice['link_url'],
        'link_text': notice['link_text'],
        'jump_season_id': notice.get('jump_season_id', ''),
        'jump_tab': notice.get('jump_tab', ''),
        'marquee_enabled': notice.get('marquee_enabled', True),
        'items': list_notices(db),
    })


@admin_bp.put('/api/admin/notice')
def admin_update_notice():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = save_notice(get_db(), admin['id'], request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.post('/api/admin/notices')
def admin_create_notice():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = create_notice(get_db(), admin['id'], request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.put('/api/admin/notices/<int:notice_id>')
def admin_update_saved_notice(notice_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = update_saved_notice(get_db(), admin['id'], notice_id, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.delete('/api/admin/notices/<int:notice_id>')
def admin_delete_saved_notice(notice_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = delete_saved_notice(get_db(), admin['id'], notice_id)
    return respond_service_result(result, service_error, status_code)


@admin_bp.post('/api/admin/notices/<int:notice_id>/activate')
def admin_activate_notice(notice_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = activate_notice(get_db(), admin['id'], notice_id)
    return respond_service_result(result, service_error, status_code)
