import base64

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from auth import current_user, get_client_ip
from copy_action_service import record_copy_action
from db import get_db
from live_comps_helpers import (
    ALLOWED_IMAGE_EXTENSIONS,
    CONTENT_TYPE_EXTENSIONS,
    DEFAULT_LIVE_COMPS_SEASON_ID,
    LIVE_COMP_ASSET_ROUTE,
    TIER_ORDER,
    build_admin_live_comp_stats_payload,
    build_live_comps_summary,
    cache_live_comp_image,
    cache_live_comps_payload_images,
    default_season_file_exists,
    download_live_comp_image,
    empty_live_comps_manifest,
    empty_live_comps_payload,
    ensure_live_comps_season,
    find_live_comp,
    flatten_live_comps,
    get_combined_live_comps_page,
    get_live_comps_page,
    get_live_comps_season,
    get_missing_live_comps_page,
    image_extension_for_url,
    increment_live_comp_global_copy_count,
    is_local_live_comp_asset_url,
    is_remote_image_url,
    live_comp_asset_filename,
    load_live_comp_global_stats,
    load_live_comps_manifest,
    manifest_path,
    manual_code_dir,
    normalize_live_comps_manifest,
    normalize_live_comps_payload,
    parse_positive_int,
    public_live_comps_manifest,
    read_live_comps_payload,
    read_live_comps_payload_for_season,
    read_raw_live_comps_payload_for_season,
    require_live_comps_upload_token,
    save_live_comps_manifest,
    season_data_filename,
    season_data_path,
    season_dir,
    validate_live_comp_asset_filename,
    validate_live_comps_payload,
    write_live_comp_asset,
    write_live_comps_payload,
    write_live_comps_payload_for_season,
)
from seasons import canonical_season_id

live_comps_bp = Blueprint('live_comps', __name__)


@live_comps_bp.get(f'{LIVE_COMP_ASSET_ROUTE}/<path:filename>')
def live_comp_asset(filename):
    return send_from_directory(current_app.config['LIVE_COMPS_ASSET_DIR'], filename)


@live_comps_bp.post('/api/live-comps/assets/upload')
def upload_live_comp_asset():
    auth_error = require_live_comps_upload_token()
    if auth_error:
        return auth_error
    data = request.get_json(silent=True) or {}
    try:
        filename = validate_live_comp_asset_filename(data.get('filename'))
        raw_data = base64.b64decode(str(data.get('content_base64') or ''), validate=True)
        if not raw_data:
            return jsonify({'error': '图片内容为空'}), 400
        url = write_live_comp_asset(filename, raw_data)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'ok': True, 'url': url, 'filename': filename})


@live_comps_bp.get('/api/live-comps/seasons')
def live_comps_seasons():
    manifest = load_live_comps_manifest()
    return jsonify(public_live_comps_manifest(manifest))


@live_comps_bp.get('/api/live-comps/summary')
def live_comps_summary():
    season_id = request.args.get('season')
    payload, updated_at, is_valid, manifest, season = read_live_comps_payload_for_season(season_id)
    return jsonify(build_live_comps_summary(payload, updated_at, is_valid, season=season, manifest=manifest))


@live_comps_bp.get('/api/live-comps')
def live_comps_list():
    page = parse_positive_int(request.args.get('page'), 1)
    page_size = int(current_app.config['LIVE_COMPS_PAGE_SIZE'])
    season_id = request.args.get('season')
    payload, _, _, _, _ = read_live_comps_payload_for_season(season_id)
    tier = request.args.get('tier')
    if tier:
        tier = tier.upper()
        if tier not in TIER_ORDER:
            return jsonify({'error': '无效段位'}), 400
        return jsonify(get_live_comps_page(payload, tier, page, page_size))
    return jsonify(get_combined_live_comps_page(payload, page, page_size))


@live_comps_bp.post('/api/live-comps/<live_comp_id>/copy')
def copy_live_comp(live_comp_id):
    season_id = request.args.get('season')
    payload, _, _, _, season = read_live_comps_payload_for_season(season_id)
    item = find_live_comp(payload, live_comp_id)
    if not item:
        return jsonify({'error': '实时阵容不存在'}), 404
    if not str(item.get('jccCode') or '').strip():
        return jsonify({'error': '当前阵容暂无可复制的阵容码'}), 400
    stat = increment_live_comp_global_copy_count()
    record_copy_action(
        target_type='live_comp',
        target_id=live_comp_id,
        user=current_user(),
        ip_address=get_client_ip(),
        source_page=request.args.get('source', ''),
        success=True,
        counted=True,
        season_id=season.get('id') if season else season_id,
    )
    get_db().commit()
    return jsonify({
        'ok': True,
        'live_comp_id': str(live_comp_id),
        'today_copy_count': int(stat.get('today_copy_count') or 0),
        'total_copy_count': int(stat.get('total_copy_count') or 0),
    })


@live_comps_bp.post('/api/live-comps/upload')
def upload_live_comps():
    auth_error = require_live_comps_upload_token()
    if auth_error:
        return auth_error
    raw_body = request.get_data(cache=True)
    if len(raw_body) > int(current_app.config['LIVE_COMPS_MAX_UPLOAD_BYTES']):
        return jsonify({'error': '上传文件过大'}), 413
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({'error': '请求体必须是 JSON'}), 400
    try:
        season_id = canonical_season_id(request.args.get('season') or (payload.get('season') if isinstance(payload, dict) else None))
        if season_id:
            write_live_comps_payload_for_season(season_id, payload)
        else:
            write_live_comps_payload(payload)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    counts = {tier: len(payload['tiers'].get(tier, [])) for tier in TIER_ORDER}
    return jsonify({'ok': True, 'tiers': counts, 'total': sum(counts.values())})
