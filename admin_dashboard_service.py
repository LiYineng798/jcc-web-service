from datetime import datetime, timedelta

from analytics import growth_summary
from visits import daily_new_returning_visitors, daily_uv_count, last_7_days_uv


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
          AND le.created_at LIKE ?
          AND u.role != 'admin'
        ''',
        (f'{today}%',),
    ).fetchone()['c']


def _today_lineup_copy_count(db, today):
    return db.execute(
        "SELECT COUNT(*) AS c FROM copy_events WHERE counted = 1 AND created_at LIKE ?",
        (f'{today}%',),
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
        "SELECT COUNT(*) AS c FROM users WHERE role != 'admin' AND created_at LIKE ?",
        (f'{today}%',),
    ).fetchone()['c']
    today_logins = _today_login_count(db, today)
    today_lineup_copy_count = _today_lineup_copy_count(db, today)
    today_live_comp_copy_count = _today_live_comp_copy_count(db, today)
    hourly = db.execute(
        "SELECT substr(created_at, 12, 2) AS hour, COUNT(*) AS count FROM users WHERE created_at LIKE ? GROUP BY hour",
        (f'{today}%',),
    ).fetchall()
    return {
        'total_users': total,
        'today_users': today_users,
        'today_logins': today_logins,
        'today_uv': daily_uv_count(today),
        'today_lineup_copy_count': today_lineup_copy_count,
        'today_live_comp_copy_count': today_live_comp_copy_count,
        'today_total_copy_count': today_lineup_copy_count + today_live_comp_copy_count,
        'yesterday_uv': daily_uv_count(yesterday),
        'today_new_visitors': today_visitor_mix['new_visitors'],
        'today_returning_visitors': today_visitor_mix['returning_visitors'],
        'yesterday_new_visitors': yesterday_visitor_mix['new_visitors'],
        'yesterday_returning_visitors': yesterday_visitor_mix['returning_visitors'],
        'last_7_days_uv': last_7_days_uv(),
        'hourly_registrations': [dict(row) for row in hourly],
    }


def build_admin_overview_payload(db):
    today, yesterday = _today_and_yesterday()
    today_visitor_mix = daily_new_returning_visitors(today)
    counts = db.execute(
        '''
        SELECT
          (SELECT COUNT(*) FROM users WHERE role != 'admin') AS total_users,
          (SELECT COUNT(*) FROM users WHERE role != 'admin' AND created_at LIKE ?) AS today_users,
          (SELECT COUNT(DISTINCT le.user_id)
             FROM login_events le JOIN users u ON u.id = le.user_id
            WHERE le.success = 1 AND le.created_at LIKE ? AND u.role != 'admin') AS today_logins,
          (SELECT COUNT(*) FROM copy_events WHERE counted = 1 AND created_at LIKE ?) AS today_lineup_copy_count,
          (SELECT COALESCE(copy_count, 0) FROM live_comp_global_daily_stats WHERE copy_date = ?) AS today_live_comp_copy_count,
          (SELECT COUNT(*) FROM reports WHERE status = 'pending') AS pending_reports_count,
          (SELECT COUNT(*) FROM lineups WHERE status = 'hidden') AS hidden_lineups_count,
          (SELECT COUNT(*) FROM audit_logs WHERE created_at LIKE ?) AS recent_audit_count
        ''',
        (f'{today}%', f'{today}%', f'{today}%', today, f'{today}%'),
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
