from datetime import datetime, timedelta

from analytics import growth_summary, _day_bounds
from visits import daily_new_returning_visitors, last_7_days_uv


def _today_and_yesterday():
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    return today, yesterday


def _today_login_count(db, today):
    return db.execute(
        '''
        SELECT COUNT(DISTINCT le.user_id) AS c
        FROM login_events le
        JOIN users u ON u.id = le.user_id
        WHERE le.success = 1
          AND le.created_at >= ? AND le.created_at < ?
          AND u.role != 'admin'
        ''',
        _day_bounds(today),
    ).fetchone()['c']


def _today_lineup_copy_count(db, today):
    return db.execute(
        "SELECT COUNT(*) AS c FROM copy_events WHERE counted = 1 AND created_at >= ? AND created_at < ?",
        _day_bounds(today),
    ).fetchone()['c']


def _today_live_comp_copy_count(db, today):
    row = db.execute(
        'SELECT copy_count FROM live_comp_global_daily_stats WHERE copy_date = ?',
        (today,),
    ).fetchone()
    return int(row['copy_count']) if row else 0


def build_admin_stats_payload(db):
    today, yesterday = _today_and_yesterday()
    total = db.execute("SELECT COUNT(*) AS c FROM users WHERE role != 'admin'").fetchone()['c']
    today_visitor_mix = daily_new_returning_visitors(today)
    yesterday_visitor_mix = daily_new_returning_visitors(yesterday)
    today_users = db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role != 'admin' AND created_at >= ? AND created_at < ?",
        _day_bounds(today),
    ).fetchone()['c']
    today_logins = _today_login_count(db, today)
    today_lineup_copy_count = _today_lineup_copy_count(db, today)
    today_live_comp_copy_count = _today_live_comp_copy_count(db, today)
    traffic_7d = last_7_days_uv()
    traffic_by_date = {item['date']: item['uv'] for item in traffic_7d}
    hourly = db.execute(
        "SELECT substr(created_at, 12, 2) AS hour, COUNT(*) AS count FROM users WHERE created_at >= ? AND created_at < ? GROUP BY hour",
        _day_bounds(today),
    ).fetchall()
    return {
        'total_users': total,
        'today_users': today_users,
        'today_logins': today_logins,
        'today_uv': traffic_by_date.get(today, 0),
        'today_lineup_copy_count': today_lineup_copy_count,
        'today_live_comp_copy_count': today_live_comp_copy_count,
        'today_total_copy_count': today_lineup_copy_count + today_live_comp_copy_count,
        'yesterday_uv': traffic_by_date.get(yesterday, 0),
        'today_new_visitors': today_visitor_mix['new_visitors'],
        'today_returning_visitors': today_visitor_mix['returning_visitors'],
        'yesterday_new_visitors': yesterday_visitor_mix['new_visitors'],
        'yesterday_returning_visitors': yesterday_visitor_mix['returning_visitors'],
        'last_7_days_uv': traffic_7d,
        'hourly_registrations': [dict(row) for row in hourly],
    }


def build_admin_overview_payload(db):
    today, yesterday = _today_and_yesterday()
    today_visitor_mix = daily_new_returning_visitors(today)
    counts = db.execute(
        '''
        SELECT
          (SELECT COUNT(*) FROM users WHERE role != 'admin') AS total_users,
          (SELECT COUNT(*) FROM users WHERE role != 'admin' AND created_at >= ? AND created_at < ?) AS today_users,
          (SELECT COUNT(DISTINCT le.user_id)
             FROM login_events le JOIN users u ON u.id = le.user_id
            WHERE le.success = 1 AND le.created_at >= ? AND le.created_at < ? AND u.role != 'admin') AS today_logins,
          (SELECT COUNT(*) FROM copy_events WHERE counted = 1 AND created_at >= ? AND created_at < ?) AS today_lineup_copy_count,
          (SELECT COALESCE(copy_count, 0) FROM live_comp_global_daily_stats WHERE copy_date = ?) AS today_live_comp_copy_count,
          (SELECT COUNT(*) FROM reports WHERE status = 'pending') AS pending_reports_count,
          (SELECT COUNT(*) FROM lineups WHERE status = 'hidden') AS hidden_lineups_count,
          (SELECT COUNT(*) FROM audit_logs WHERE created_at >= ? AND created_at < ?) AS recent_audit_count
        ''',
        (*_day_bounds(today), *_day_bounds(today), *_day_bounds(today), today, *_day_bounds(today)),
    ).fetchone()
    counts = dict(counts)
    total_users = int(counts['total_users'] or 0)
    today_users = int(counts['today_users'] or 0)
    today_logins = int(counts['today_logins'] or 0)
    today_lineup_copy_count = int(counts['today_lineup_copy_count'] or 0)
    today_live_comp_copy_count = int(counts['today_live_comp_copy_count'] or 0)
    pending_reports_count = int(counts['pending_reports_count'] or 0)
    hidden_lineups_count = int(counts['hidden_lineups_count'] or 0)
    recent_audit_count = int(counts['recent_audit_count'] or 0)
    traffic_7d = last_7_days_uv()
    traffic_by_date = {item['date']: item['uv'] for item in traffic_7d}
    return {
        'stats': {
            'today_uv': traffic_by_date.get(today, 0),
            'yesterday_uv': traffic_by_date.get(yesterday, 0),
            'today_new_visitors': today_visitor_mix['new_visitors'],
            'today_returning_visitors': today_visitor_mix['returning_visitors'],
            'today_users': today_users,
            'today_logins': today_logins,
            'today_lineup_copy_count': today_lineup_copy_count,
            'today_live_comp_copy_count': today_live_comp_copy_count,
            'today_total_copy_count': today_lineup_copy_count + today_live_comp_copy_count,
            'total_users': total_users,
            'pending_reports_count': pending_reports_count,
        },
        'traffic_7d': traffic_7d,
        'todos': {
            'pending_reports_count': pending_reports_count,
            'hidden_lineups_count': hidden_lineups_count,
            'recent_audit_count': recent_audit_count,
        },
    }


def build_admin_growth_payload(target_date):
    return growth_summary(target_date=target_date)


def build_admin_copy_rank_payload(db, target_date, limit=10):
    """Top copied lineup codes (regular lineups + live comps) for one day."""
    from analytics import _normalize_target_date
    from live_comps_helpers import find_live_comp, load_live_comps_manifest, read_live_comps_payload_for_season

    target_date = _normalize_target_date(target_date)
    start, end = _day_bounds(target_date)
    limit = max(1, min(int(limit or 10), 50))
    rows = db.execute(
        '''
        SELECT target_type, target_id, season_id,
               COUNT(*) AS copies,
               COUNT(DISTINCT CASE
                   WHEN user_id IS NOT NULL THEN 'u:' || CAST(user_id AS TEXT)
                   WHEN COALESCE(visitor_token, '') != '' THEN 'v:' || visitor_token
                   ELSE 'ip:' || COALESCE(ip_address, '')
               END) AS unique_visitors
        FROM copy_action_events
        WHERE created_at >= ? AND created_at < ?
          AND success = 1
        GROUP BY target_type, target_id, season_id
        ORDER BY copies DESC, target_type, target_id
        LIMIT ?
        ''',
        (start, end, limit),
    ).fetchall()

    lineup_ids = [int(row['target_id']) for row in rows if row['target_type'] == 'lineup']
    lineups_by_id = {}
    if lineup_ids:
        placeholders = ', '.join('?' for _ in lineup_ids)
        lineups_by_id = {
            lineup['id']: lineup
            for lineup in db.execute(
                f'SELECT id, name, code, season_id, status FROM lineups WHERE id IN ({placeholders})',
                lineup_ids,
            ).fetchall()
        }

    season_names = {
        season['id']: season.get('name') or season['id']
        for season in load_live_comps_manifest().get('seasons', [])
    }
    live_payload_cache = {}

    items = []
    for rank, row in enumerate(rows, start=1):
        item = {
            'rank': rank,
            'target_type': row['target_type'],
            'target_id': str(row['target_id']),
            'season_id': row['season_id'],
            'season_name': season_names.get(row['season_id'], row['season_id'] or ''),
            'copies': int(row['copies'] or 0),
            'unique_visitors': int(row['unique_visitors'] or 0),
            'title': None,
            'tier': None,
            'lineup_id': None,
            'status': None,
        }
        if row['target_type'] == 'lineup':
            lineup = lineups_by_id.get(int(row['target_id']))
            if lineup:
                item['title'] = lineup['name']
                item['lineup_id'] = lineup['id']
                item['status'] = lineup['status']
                item['season_id'] = item['season_id'] or lineup['season_id']
                item['season_name'] = season_names.get(item['season_id'], item['season_id'] or '')
            else:
                item['title'] = f"已删除阵容 #{row['target_id']}"
        else:
            season_key = row['season_id'] or ''
            if season_key not in live_payload_cache:
                payload, _, _, _, _ = read_live_comps_payload_for_season(season_key or None)
                live_payload_cache[season_key] = payload
            live_item = find_live_comp(live_payload_cache[season_key], row['target_id'])
            if live_item:
                item['title'] = live_item.get('title')
                item['tier'] = live_item.get('tier')
            else:
                item['title'] = f"未收录实时阵容 #{row['target_id']}"
        items.append(item)
    return {'date': target_date, 'items': items}
