import json
from copy import deepcopy
from pathlib import Path

from lineup_code import extract_lineup_code

TIER_ORDER = ('S', 'A', 'B', 'C', 'D')


def manual_code_overlay_path(base_dir, season_id):
    return Path(base_dir) / f'{season_id}.json'


def empty_manual_code_overlay(season_id):
    return {
        'season': str(season_id),
        'updated_at': None,
        'items': {},
    }


def load_manual_code_overlay(base_dir, season_id):
    path = manual_code_overlay_path(base_dir, season_id)
    if not path.exists():
        return empty_manual_code_overlay(season_id)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return empty_manual_code_overlay(season_id)
    items = data.get('items') if isinstance(data.get('items'), dict) else {}
    normalized_items = {}
    for live_comp_id, meta in items.items():
        if not isinstance(meta, dict):
            continue
        normalized_code = extract_lineup_code(meta.get('jccCode'))
        if not normalized_code:
            continue
        normalized_items[str(live_comp_id)] = {
            'jccCode': normalized_code,
            'updated_at': meta.get('updated_at'),
            'updated_by': meta.get('updated_by'),
        }
    return {
        'season': str(data.get('season') or season_id),
        'updated_at': data.get('updated_at'),
        'items': normalized_items,
    }


def save_manual_code_overlay(base_dir, season_id, overlay):
    path = manual_code_overlay_path(base_dir, season_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'season': str(overlay.get('season') or season_id),
        'updated_at': overlay.get('updated_at'),
        'items': dict(overlay.get('items') or {}),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def set_manual_code_overlay_value(base_dir, season_id, live_comp_id, code, admin_id, now_value):
    normalized = extract_lineup_code(code)
    if not normalized:
        raise ValueError('阵容码格式无法识别')
    overlay = load_manual_code_overlay(base_dir, season_id)
    overlay['updated_at'] = now_value
    overlay['items'][str(live_comp_id)] = {
        'jccCode': normalized,
        'updated_at': now_value,
        'updated_by': int(admin_id),
    }
    return save_manual_code_overlay(base_dir, season_id, overlay)


def merge_manual_codes_into_payload(payload, overlay):
    merged = deepcopy(payload)
    overlay_items = dict((overlay or {}).get('items') or {})
    for tier in TIER_ORDER:
        normalized_items = []
        for item in merged.get('tiers', {}).get(tier, []):
            row = dict(item)
            original_code = extract_lineup_code(row.get('jccCode')) or ''
            manual_entry = overlay_items.get(str(row.get('id'))) or {}
            manual_code = extract_lineup_code(manual_entry.get('jccCode')) or ''
            resolved_code = original_code or manual_code
            row['originalJccCode'] = original_code
            row['resolvedJccCode'] = resolved_code
            row['jccCode'] = resolved_code
            row['hasCode'] = bool(resolved_code)
            row['codeSource'] = 'original' if original_code else ('manual' if manual_code else 'none')
            normalized_items.append(row)
        merged['tiers'][tier] = normalized_items
    return merged


def prune_manual_codes_for_payload(base_dir, season_id, payload):
    overlay = load_manual_code_overlay(base_dir, season_id)
    live_comp_map = {}
    for tier in TIER_ORDER:
        for item in payload.get('tiers', {}).get(tier, []):
            live_comp_map[str(item.get('id'))] = item
    kept_items = {}
    for live_comp_id, meta in overlay['items'].items():
        candidate = live_comp_map.get(str(live_comp_id))
        original_code = extract_lineup_code((candidate or {}).get('jccCode')) or ''
        if candidate and not original_code:
            kept_items[str(live_comp_id)] = meta
    overlay['items'] = kept_items
    return save_manual_code_overlay(base_dir, season_id, overlay)
