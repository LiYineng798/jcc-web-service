"""Daily admin report generation and read APIs.

A daily report is a read-only snapshot of one calendar day's site activity,
stored as one row in ``daily_admin_reports`` (``payload_json`` holds the full
report; a few denormalized columns mirror the headline totals for cheap list
views). The report is generated shortly after midnight by the background
worker (``daily_report_worker``) and can be regenerated from the admin
console. Regenerating never mutates source event tables.

The payload is deliberately data-lover friendly:

- ``summary``: headline totals (UV, PV, new/returning visitors, registrations,
  logins, copies, new lineups, guestbook, reports, likes, favorites).
- ``deltas``: change versus the most recent earlier report, when one exists.
- ``hourly``: per-hour UV / PV / copy counts for the heatmap.
- ``top_pages`` and ``top_copied``: where traffic went and what got copied.
- ``season_copy_rank``: copies grouped by season/version.
- ``top_visitor_ips``: yesterday's most active client IPs (admin-only view).
- ``summary.returning_3d / returning_7d``: yesterday's visitors that also
  visited within the previous 3 / 7 days.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from db import db_kind, get_db, now_text
from db_adapter import insert_ignore_sql
from visits import daily_new_returning_visitors

REPORT_DATE_FORMAT = '%Y-%m-%d'
MAX_TOP_COPIED = 20
MAX_TOP_PAGES = 12
MAX_SEASON_RANK = 12
MAX_VISITOR_IPS = 20

DELTA_KEYS = (
    'unique_visitors',
    'page_visits',
    'new_visitors',
    'returning_visitors',
    'returning_3d',
    'returning_7d',
    'new_registrations',
    'successful_logins',
    'lineup_copies',
    'live_comp_copies',
    'total_copies',
    'new_lineups',
    'guestbook_messages',
    'reports_submitted',
    'like_actions',
    'favorite_actions',
)

PAGE_KEY_LABELS = {
    'home': '首页',
    'auth': '登录/注册',
    'author': '作者主页',
    'me': '个人中心',
    'lineup_detail': '阵容详情',
    'lineup_editor': '阵容编辑',
    'admin': '管理后台',
    'patch_notes': '更新公告',
    'season_reference': '赛季资料',
    'season_champion_detail': '弈子详情',
    'lineup_simulator': '阵容模拟器',
    'special_mechanics': '特殊机制',
    'artifact_guide': '神器指南',
    'returning_equipment': '回归装备',
}


def _day_bounds(target_date):
    next_day = (datetime.strptime(target_date, REPORT_DATE_FORMAT) + timedelta(days=1)).strftime(REPORT_DATE_FORMAT)
    return target_date, next_day


def normalize_report_date(value):
    text = str(value or '').strip()
    if not text:
        return None
    try:
        datetime.strptime(text, REPORT_DATE_FORMAT)
    except ValueError:
        return None
    return text


def yesterday_date():
    return (datetime.now() - timedelta(days=1)).strftime(REPORT_DATE_FORMAT)


def _fetch_report_row(db, target_date):
    return db.execute(
        'SELECT * FROM daily_admin_reports WHERE report_date = ?',
        (target_date,),
    ).fetchone()


def _admin_excluded_visitor_scope():
    return "(ve.user_id IS NULL OR COALESCE(u.role, 'user') != 'admin')"


def _int(value):
    return int(value or 0)


def _delta(current, previous):
    if previous is None:
        return None
    return current - previous


def _top_pages(db, start, end, limit=MAX_TOP_PAGES):
    rows = db.execute(
        f'''
        SELECT ve.page_key, COUNT(*) AS visits, COUNT(DISTINCT ve.visitor_key) AS uv
        FROM visit_events ve
        LEFT JOIN users u ON u.id = ve.user_id
        WHERE ve.created_at >= ? AND ve.created_at < ?
          AND {_admin_excluded_visitor_scope()}
        GROUP BY ve.page_key
        ORDER BY visits DESC, uv DESC
        LIMIT ?
        ''',
        (start, end, limit),
    ).fetchall()
    return [
        {
            'page_key': row['page_key'],
            'label': PAGE_KEY_LABELS.get(row['page_key'], row['page_key']),
            'visits': _int(row['visits']),
            'uv': _int(row['uv']),
        }
        for row in rows
    ]


def _top_copied(db, start, end, limit=MAX_TOP_COPIED):
    """Top copied targets (regular lineups + live comps) for one day."""
    from live_comps_helpers import find_live_comp, load_live_comps_manifest, read_live_comps_payload_for_season

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
            'copies': _int(row['copies']),
            'unique_visitors': _int(row['unique_visitors']),
            'title': None,
            'tier': None,
            'lineup_id': None,
            'code': None,
            'status': None,
        }
        if row['target_type'] == 'lineup':
            lineup = lineups_by_id.get(int(row['target_id']))
            if lineup:
                item['title'] = lineup['name']
                item['lineup_id'] = lineup['id']
                item['code'] = lineup['code']
                item['status'] = lineup['status']
                item['season_id'] = item['season_id'] or lineup['season_id']
                item['season_name'] = season_names.get(item['season_id'], item['season_id'] or '')
            else:
                item['title'] = f"已删除阵容 #{row['target_id']}"
        else:
            season_key = row['season_id'] or ''
            try:
                if season_key not in live_payload_cache:
                    payload, _, _, _, _ = read_live_comps_payload_for_season(season_key or None)
                    live_payload_cache[season_key] = payload
                live_item = find_live_comp(live_payload_cache[season_key], row['target_id'])
                if live_item:
                    item['title'] = live_item.get('title')
                    item['tier'] = live_item.get('tier')
                    item['code'] = live_item.get('resolvedJccCode') or live_item.get('jccCode')
                else:
                    item['title'] = f"未收录实时阵容 #{row['target_id']}"
            except Exception:
                item['title'] = f"实时阵容 #{row['target_id']}"
        items.append(item)
    return items


def _season_copy_rank(db, start, end, limit=MAX_SEASON_RANK):
    """Copy counts grouped by season id (the finest version dimension on the
    copy events today). ``share`` is the percentage of the day's successful
    copies that belong to this season."""
    from live_comps_helpers import load_live_comps_manifest

    total_row = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM copy_action_events
        WHERE created_at >= ? AND created_at < ?
          AND success = 1
        ''',
        (start, end),
    ).fetchone()
    total = _int(total_row['c'])

    rows = db.execute(
        '''
        SELECT season_id,
               COUNT(*) AS copies,
               COUNT(DISTINCT CASE
                   WHEN user_id IS NOT NULL THEN 'u:' || CAST(user_id AS TEXT)
                   WHEN COALESCE(visitor_token, '') != '' THEN 'v:' || visitor_token
                   ELSE 'ip:' || COALESCE(ip_address, '')
               END) AS unique_visitors
        FROM copy_action_events
        WHERE created_at >= ? AND created_at < ?
          AND success = 1
        GROUP BY season_id
        ORDER BY copies DESC, season_id
        LIMIT ?
        ''',
        (start, end, limit),
    ).fetchall()
    season_names = {
        season['id']: season.get('name') or season['id']
        for season in load_live_comps_manifest().get('seasons', [])
    }
    items = []
    for rank, row in enumerate(rows, start=1):
        season_id = row['season_id'] or ''
        copies = _int(row['copies'])
        items.append({
            'rank': rank,
            'season_id': season_id,
            'season_name': season_names.get(season_id, season_id or '未标注'),
            'copies': copies,
            'unique_visitors': _int(row['unique_visitors']),
            'share': round(copies / total * 100, 1) if total else 0.0,
        })
    return items


def _top_visitor_ips(db, start, end, limit=MAX_VISITOR_IPS):
    """Most active client IPs for the day (admin-only view).

    ``is_returning`` means the same IP produced at least one visit before the
    report date; ``copied`` means the IP also triggered a successful copy that
    day. IPs are approximate identities (NAT/shared networks), so this panel
    is for operational triage, not hard visitor counts.
    """
    rows = db.execute(
        f'''
        SELECT ve.ip_address,
               COUNT(*) AS visits,
               COUNT(DISTINCT ve.visitor_key) AS visitors,
               COUNT(DISTINCT ve.page_key) AS pages,
               CASE WHEN EXISTS (
                   SELECT 1 FROM visit_events prior
                   WHERE prior.ip_address = ve.ip_address
                     AND prior.visit_date < ?
               ) THEN 1 ELSE 0 END AS is_returning,
               CASE WHEN EXISTS (
                   SELECT 1 FROM copy_action_events c
                   WHERE c.ip_address = ve.ip_address
                     AND c.created_at >= ? AND c.created_at < ?
                     AND c.success = 1
               ) THEN 1 ELSE 0 END AS copied
        FROM visit_events ve
        LEFT JOIN users u ON u.id = ve.user_id
        WHERE ve.created_at >= ? AND ve.created_at < ?
          AND {_admin_excluded_visitor_scope()}
        GROUP BY ve.ip_address
        ORDER BY visits DESC, visitors DESC, ve.ip_address
        LIMIT ?
        ''',
        (start, start, end, start, end, limit),
    ).fetchall()
    return [
        {
            'ip': row['ip_address'] or '未知',
            'visits': _int(row['visits']),
            'visitors': _int(row['visitors']),
            'pages': _int(row['pages']),
            'is_returning': bool(row['is_returning']),
            'copied': bool(row['copied']),
        }
        for row in rows
    ]


def _returning_window_count(target_date, day):
    """Yesterday's visitors that also visited within the previous ``day`` days
    (half-open [target-day, target) window on visit_date)."""
    window_start = (datetime.strptime(target_date, REPORT_DATE_FORMAT) - timedelta(days=day)).strftime(REPORT_DATE_FORMAT)
    row = get_db().execute(
        f'''
        WITH today_visitors AS (
            SELECT DISTINCT ve.visitor_key
            FROM visit_events ve
            LEFT JOIN users u ON u.id = ve.user_id
            WHERE ve.visit_date = ?
              AND {_admin_excluded_visitor_scope()}
        )
        SELECT SUM(CASE WHEN EXISTS (
            SELECT 1 FROM visit_events prior
            WHERE prior.visitor_key = today_visitors.visitor_key
              AND prior.visit_date >= ?
              AND prior.visit_date < ?
        ) THEN 1 ELSE 0 END) AS returning_count
        FROM today_visitors
        ''',
        (target_date, window_start, target_date),
    ).fetchone()
    return int(row['returning_count'] or 0) if row else 0


def build_daily_report_payload(db, target_date):
    """Compute the full report payload for one date without persisting it."""
    start, end = _day_bounds(target_date)
    scope = _admin_excluded_visitor_scope()

    summary_row = db.execute(
        f'''
        SELECT COUNT(DISTINCT ve.visitor_key) AS uv, COUNT(*) AS pv
        FROM visit_events ve
        LEFT JOIN users u ON u.id = ve.user_id
        WHERE ve.created_at >= ? AND ve.created_at < ?
          AND {scope}
        ''',
        (start, end),
    ).fetchone()
    new_returning = daily_new_returning_visitors(target_date)

    registrations = db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role != 'admin' AND created_at >= ? AND created_at < ?",
        (start, end),
    ).fetchone()['c']
    successful_logins = db.execute(
        '''
        SELECT COUNT(DISTINCT le.user_id) AS c
        FROM login_events le
        JOIN users u ON u.id = le.user_id
        WHERE le.success = 1
          AND le.created_at >= ? AND le.created_at < ?
          AND u.role != 'admin'
        ''',
        (start, end),
    ).fetchone()['c']
    new_lineups = db.execute(
        'SELECT COUNT(*) AS c FROM lineups WHERE created_at >= ? AND created_at < ?',
        (start, end),
    ).fetchone()['c']
    guestbook_messages = db.execute(
        'SELECT COUNT(*) AS c FROM guestbook_messages WHERE created_at >= ? AND created_at < ?',
        (start, end),
    ).fetchone()['c']
    reports_submitted = db.execute(
        'SELECT COUNT(*) AS c FROM reports WHERE created_at >= ? AND created_at < ?',
        (start, end),
    ).fetchone()['c']
    like_actions = db.execute(
        'SELECT COUNT(*) AS c FROM likes WHERE created_at >= ? AND created_at < ?',
        (start, end),
    ).fetchone()['c']
    favorite_actions = db.execute(
        'SELECT COUNT(*) AS c FROM favorites WHERE created_at >= ? AND created_at < ?',
        (start, end),
    ).fetchone()['c']

    copies_row = db.execute(
        '''
        SELECT
          SUM(CASE WHEN target_type = 'lineup' THEN 1 ELSE 0 END) AS lineup_copies,
          SUM(CASE WHEN target_type = 'live_comp' THEN 1 ELSE 0 END) AS live_comp_copies,
          COUNT(*) AS total_copies
        FROM copy_action_events
        WHERE created_at >= ? AND created_at < ?
          AND success = 1
        ''',
        (start, end),
    ).fetchone()

    hourly = {'uv': [0] * 24, 'visits': [0] * 24, 'copies': [0] * 24}
    hourly_rows = db.execute(
        f'''
        SELECT substr(ve.created_at, 12, 2) AS hour,
               COUNT(*) AS visits,
               COUNT(DISTINCT ve.visitor_key) AS uv
        FROM visit_events ve
        LEFT JOIN users u ON u.id = ve.user_id
        WHERE ve.created_at >= ? AND ve.created_at < ?
          AND {scope}
        GROUP BY hour
        ''',
        (start, end),
    ).fetchall()
    copy_hour_rows = db.execute(
        '''
        SELECT substr(created_at, 12, 2) AS hour, COUNT(*) AS c
        FROM copy_action_events
        WHERE created_at >= ? AND created_at < ?
          AND success = 1
        GROUP BY hour
        ''',
        (start, end),
    ).fetchall()
    for row in hourly_rows:
        try:
            hour = int(row['hour'])
        except (TypeError, ValueError):
            continue
        if 0 <= hour <= 23:
            hourly['uv'][hour] = _int(row['uv'])
            hourly['visits'][hour] = _int(row['visits'])
    for row in copy_hour_rows:
        try:
            hour = int(row['hour'])
        except (TypeError, ValueError):
            continue
        if 0 <= hour <= 23:
            hourly['copies'][hour] = _int(row['c'])

    def _peak_hour(series):
        if not any(series):
            return None
        hour = max(range(24), key=lambda index: series[index])
        return {'hour': hour, 'value': series[hour]}

    summary = {
        'unique_visitors': _int(summary_row['uv']),
        'page_visits': _int(summary_row['pv']),
        'new_visitors': new_returning['new_visitors'],
        'returning_visitors': new_returning['returning_visitors'],
        'returning_3d': _returning_window_count(target_date, 3),
        'returning_7d': _returning_window_count(target_date, 7),
        'new_registrations': _int(registrations),
        'successful_logins': _int(successful_logins),
        'lineup_copies': _int(copies_row['lineup_copies']),
        'live_comp_copies': _int(copies_row['live_comp_copies']),
        'total_copies': _int(copies_row['total_copies']),
        'new_lineups': _int(new_lineups),
        'guestbook_messages': _int(guestbook_messages),
        'reports_submitted': _int(reports_submitted),
        'like_actions': _int(like_actions),
        'favorite_actions': _int(favorite_actions),
    }

    previous_date = None
    deltas = None
    previous_row = db.execute(
        '''
        SELECT report_date, payload_json
        FROM daily_admin_reports
        WHERE report_date < ? AND generated_at != ''
        ORDER BY report_date DESC
        LIMIT 1
        ''',
        (target_date,),
    ).fetchone()
    if previous_row:
        previous_date = previous_row['report_date']
        try:
            previous_summary = (json.loads(previous_row['payload_json'] or '{}') or {}).get('summary') or {}
        except (json.JSONDecodeError, TypeError):
            previous_summary = {}
        if previous_summary:
            deltas = {
                key: _delta(summary[key], previous_summary.get(key))
                for key in DELTA_KEYS
            }

    return {
        'summary': summary,
        'deltas': deltas,
        'previous_date': previous_date,
        'hourly': hourly,
        'peak_visit_hour': _peak_hour(hourly['uv']),
        'peak_copy_hour': _peak_hour(hourly['copies']),
        'top_pages': _top_pages(db, start, end),
        'top_copied': _top_copied(db, start, end),
        'season_copy_rank': _season_copy_rank(db, start, end),
        'top_visitor_ips': _top_visitor_ips(db, start, end),
    }


def get_daily_report(target_date):
    """Return the stored report dict, or None when it does not exist yet."""
    target_date = normalize_report_date(target_date)
    if target_date is None:
        return None
    row = _fetch_report_row(get_db(), target_date)
    if not row or not row['generated_at']:
        return None
    try:
        payload = json.loads(row['payload_json'] or '{}')
    except (json.JSONDecodeError, TypeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.update({
        'report_date': target_date,
        'generated_at': row['generated_at'],
        'updated_at': row['updated_at'],
    })
    return payload


def list_daily_reports(limit=30):
    """Recent completed reports, newest first, with headline totals only."""
    limit = max(1, min(int(limit or 30), 100))
    rows = get_db().execute(
        '''
        SELECT report_date, unique_visitors, page_visits, successful_copies, generated_at
        FROM daily_admin_reports
        WHERE generated_at != ''
        ORDER BY report_date DESC
        LIMIT ?
        ''',
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def ensure_daily_report(target_date=None, force=False):
    """Generate a report snapshot for ``target_date`` (default: yesterday).

    The row insert is guarded with INSERT OR IGNORE / ON CONFLICT DO NOTHING,
    so concurrent processes (gunicorn workers, the background thread, a manual
    CLI run) never create duplicate rows; a lost race simply returns the
    winner's already-completed snapshot. ``force=True`` recomputes and updates
    an existing snapshot in place.
    """
    target_date = normalize_report_date(target_date) or yesterday_date()
    db = get_db()
    row = _fetch_report_row(db, target_date)
    if row and row['generated_at'] and not force:
        return get_daily_report(target_date)

    payload = build_daily_report_payload(db, target_date)
    summary = payload['summary']
    now = now_text()
    values = (
        target_date,
        summary['unique_visitors'],
        summary['page_visits'],
        summary['total_copies'],
        json.dumps(payload, ensure_ascii=False),
        now,
        now,
    )
    if row is None:
        db.execute(
            insert_ignore_sql(
                'daily_admin_reports',
                [
                    'report_date',
                    'unique_visitors',
                    'page_visits',
                    'successful_copies',
                    'payload_json',
                    'generated_at',
                    'updated_at',
                ],
                ['report_date'],
                db_kind(),
            ),
            values,
        )
        db.commit()
        return get_daily_report(target_date)
    else:
        db.execute(
            '''
            UPDATE daily_admin_reports
            SET unique_visitors = ?, page_visits = ?, successful_copies = ?,
                payload_json = ?, generated_at = ?, updated_at = ?
            WHERE report_date = ?
            ''',
            values[1:] + (target_date,),
        )
        db.commit()
        return get_daily_report(target_date)
