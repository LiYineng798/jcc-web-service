import re

from flask import current_app

from audit import write_audit
from db import now_text
from live_comp_manual_codes import set_manual_code_overlay_value
from live_comps import (
    build_admin_live_comp_stats_payload,
    find_live_comp,
    load_live_comps_manifest,
    read_live_comps_payload_for_season,
    read_raw_live_comps_payload_for_season,
    save_live_comps_manifest,
)
from live_comps_helpers import touch_live_comps_season_data
from seasons import SEASON_ALIASES, canonical_season_id

SEASON_ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
SEASON_STATUSES = {'active', 'archived', 'hidden', 'disabled'}


def build_admin_live_comps_payload(season_id, page, page_size):
    payload, updated_at, is_valid, manifest, season = read_live_comps_payload_for_season(season_id)
    return build_admin_live_comp_stats_payload(
        payload,
        updated_at,
        is_valid,
        season=season,
        manifest=manifest,
        page=page,
        page_size=page_size,
    )


def add_admin_live_comp_manual_code(admin_id, season_id, live_comp_id, data):
    payload, _, _, _, season = read_raw_live_comps_payload_for_season(season_id)
    target = find_live_comp(payload, live_comp_id)
    if not target:
        return None, '实时阵容不存在', 404
    if str(target.get('jccCode') or '').strip():
        return None, '当前条目已有原始阵容码，无需补码', 400
    set_manual_code_overlay_value(
        current_app.config['LIVE_COMPS_MANUAL_CODE_DIR'],
        season['id'],
        live_comp_id,
        str((data or {}).get('code') or ''),
        admin_id=admin_id,
        now_value=now_text(),
    )
    merged_payload, _, _, _, _ = read_live_comps_payload_for_season(season['id'])
    merged_item = find_live_comp(merged_payload, live_comp_id)
    write_audit(
        admin_id,
        'admin_add_live_comp_manual_code',
        'live_comp',
        f'{season["id"]}:{live_comp_id}',
        before={'jccCode': '', 'resolvedJccCode': ''},
        after={
            'season_id': season['id'],
            'resolvedJccCode': merged_item.get('resolvedJccCode'),
        },
    )
    return merged_item, None, 200


def list_admin_live_comps_seasons():
    return load_live_comps_manifest()


def create_admin_live_comps_season(admin_id, data):
    data = data or {}
    season_id = str(data.get('id') or '').strip().lower()
    name = str(data.get('name') or '').strip()
    description = str(data.get('description') or '').strip()
    status = str(data.get('status') or 'active').strip()

    if not SEASON_ID_RE.match(season_id):
        return None, '赛季 ID 只能包含小写字母、数字和短横线（2-40 位，以字母或数字开头）', 400
    if season_id in SEASON_ALIASES or canonical_season_id(season_id) != season_id:
        return None, '该 ID 是保留别名，请换一个', 400
    if not name or len(name) > 60:
        return None, '赛季名称必填且不超过 60 字', 400
    if len(description) > 200:
        return None, '赛季说明不超过 200 字', 400
    if status not in SEASON_STATUSES:
        return None, '赛季状态无效', 400

    manifest = load_live_comps_manifest()
    if any(str(season.get('id')) == season_id for season in manifest['seasons']):
        return None, '该赛季 ID 已存在', 400

    seasons = list(manifest['seasons'])
    seasons.append({
        'id': season_id,
        'name': name,
        'status': status,
        'order': max([int(season.get('order') or 0) for season in seasons] or [0]) + 1,
        'description': description,
        'data_file': f'{season_id}.json',
    })
    updated_manifest = save_live_comps_manifest({
        'default_season_id': manifest.get('default_season_id'),
        'seasons': seasons,
    })
    write_audit(
        admin_id,
        'create_live_comps_season',
        'live_comp_season',
        season_id,
        before=None,
        after={'id': season_id, 'name': name, 'status': status, 'description': description},
    )
    return updated_manifest, None, 200


def touch_admin_live_comps_season(admin_id, season_id):
    updated_at, season, error = touch_live_comps_season_data(season_id)
    if error:
        return None, error, 404 if error == '赛季不存在' else 400
    write_audit(
        admin_id,
        'touch_live_comps_season_updated_at',
        'live_comp_season',
        season['id'],
        before=None,
        after={'updated_at': updated_at},
    )
    return {'season_id': season['id'], 'updated_at': updated_at}, None, 200


def _reorder_live_comps_seasons(seasons, target_season_id, target_order):
    ordered = sorted(seasons, key=lambda season: (int(season.get('order') or 0), str(season.get('id') or '')))
    target = next((season for season in ordered if str(season.get('id')) == str(target_season_id)), None)
    if target is None:
        return ordered
    ordered = [season for season in ordered if str(season.get('id')) != str(target_season_id)]
    try:
        next_index = int(target_order) - 1
    except (TypeError, ValueError):
        next_index = int(target.get('order') or len(ordered) + 1) - 1
    next_index = max(0, min(next_index, len(ordered)))
    ordered.insert(next_index, target)
    for index, season in enumerate(ordered, start=1):
        season['order'] = index
    return ordered


def update_admin_live_comps_season(admin_id, season_id, data):
    manifest = load_live_comps_manifest()
    seasons = []
    found = False
    should_reorder = 'order' in (data or {})
    for season in manifest['seasons']:
        updated = dict(season)
        if str(updated.get('id')) == str(season_id):
            found = True
            for key in ['name', 'status', 'description', 'order']:
                if key in (data or {}):
                    updated[key] = data[key]
        seasons.append(updated)
    if not found:
        return None, '赛季不存在', 404
    if should_reorder:
        seasons = _reorder_live_comps_seasons(seasons, season_id, (data or {}).get('order'))
    default_season_id = str((data or {}).get('default_season_id') or manifest.get('default_season_id') or season_id)
    if not any(str(season.get('id')) == default_season_id for season in seasons):
        default_season_id = season_id
    updated_manifest = save_live_comps_manifest({
        'default_season_id': default_season_id,
        'seasons': seasons,
    })
    write_audit(admin_id, 'update_live_comps_season', 'live_comp_season', season_id, before=manifest, after=updated_manifest)
    return updated_manifest, None, 200
