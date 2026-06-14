from datetime import datetime, timedelta

from db import get_db, now_text


def _window_start(minutes):
    now = datetime.now()
    minute = (now.minute // minutes) * minutes
    return now.replace(minute=minute, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')


def hit_limit(scope, key, limit, window_minutes):
    db = get_db()
    window = _window_start(window_minutes)
    row = db.execute(
        'SELECT attempts FROM rate_limits WHERE scope = ? AND key = ? AND window_start = ?',
        (scope, key, window),
    ).fetchone()
    if row and row['attempts'] >= limit:
        return True
    if row:
        db.execute(
            'UPDATE rate_limits SET attempts = attempts + 1 WHERE scope = ? AND key = ? AND window_start = ?',
            (scope, key, window),
        )
    else:
        db.execute(
            'INSERT INTO rate_limits (scope, key, window_start, attempts) VALUES (?, ?, ?, 1)',
            (scope, key, window),
        )
    db.commit()
    return False
