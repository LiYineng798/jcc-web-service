from __future__ import annotations

from datetime import datetime

from db import get_db
from live_comps_helpers import public_live_comps_manifest, load_live_comps_manifest
from seasons import DEFAULT_SEASON_ID, canonical_season_id, season_manifest

LINEUP_VISIBLE_STATUSES = {'normal', 'hidden'}
LINEUP_SEASON_PUBLIC_STATUSES = {'active', 'archived'}
DEFAULT_LINEUP_SEASON_ID = DEFAULT_SEASON_ID


def canonical_lineup_season_id(season_id):
    return canonical_season_id(season_id)


def lineup_season_manifest():
    base_manifest = season_manifest(DEFAULT_LINEUP_SEASON_ID)
    live_manifest = public_live_comps_manifest(load_live_comps_manifest())
    live_statuses = {
        season['id']: season.get('status')
        for season in live_manifest.get('seasons', [])
    }
    seasons = []
    for season in base_manifest['seasons']:
        live_status = live_statuses.get(season['id'])
        if live_status not in LINEUP_SEASON_PUBLIC_STATUSES:
            continue
        item = dict(season)
        item['status'] = live_status
        seasons.append(item)
    default_season_id = DEFAULT_LINEUP_SEASON_ID
    if not any(season['id'] == default_season_id for season in seasons) and seasons:
        default_season_id = seasons[0]['id']
    return {
        'default_season_id': default_season_id,
        'seasons': seasons,
    }


def bucket_start():
    now = datetime.now()
    minute = (now.minute // 10) * 10
    return now.replace(minute=minute, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')


def normalize_lineup_status(raw_status, default='normal'):
    status = str(raw_status or default).strip().lower()
    return status if status in LINEUP_VISIBLE_STATUSES else None


def season_choice_map():
    manifest = lineup_season_manifest()
    return {season['id']: season for season in manifest['seasons']}


def parse_positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def row_value(row, key, default=None):
    if hasattr(row, 'keys') and key in row.keys():
        return row[key]
    if isinstance(row, dict):
        return row.get(key, default)
    return default


def visibility_clause(user, alias='l'):
    if user and user['role'] == 'admin':
        return f"{alias}.status != 'deleted'", []
    if user:
        return f"({alias}.status = 'normal' OR ({alias}.status = 'hidden' AND {alias}.user_id = ?))", [user['id']]
    return f"{alias}.status = 'normal'", []


def lineup_is_visible_to_user(row, user):
    if not row or row['status'] == 'deleted':
        return False
    if row['status'] == 'normal':
        return True
    return bool(user and (user['role'] == 'admin' or user['id'] == row['user_id']))


def lineup_row(lineup_id):
    return get_db().execute('SELECT * FROM lineups WHERE id = ?', (lineup_id,)).fetchone()
