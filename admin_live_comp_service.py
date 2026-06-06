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


def update_admin_live_comps_season(admin_id, season_id, data):
    manifest = load_live_comps_manifest()
    seasons = []
    found = False
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
    default_season_id = str((data or {}).get('default_season_id') or manifest.get('default_season_id') or season_id)
    if not any(str(season.get('id')) == default_season_id for season in seasons):
        default_season_id = season_id
    updated_manifest = save_live_comps_manifest({
        'default_season_id': default_season_id,
        'seasons': seasons,
    })
    write_audit(admin_id, 'update_live_comps_season', 'live_comp_season', season_id, before=manifest, after=updated_manifest)
    return updated_manifest, None, 200
