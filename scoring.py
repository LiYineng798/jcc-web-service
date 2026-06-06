from datetime import datetime, timedelta
from math import ceil

from db import get_db
from lineup_cache import (
    get_rising_cache,
    get_score_cache,
    rising_cache_key,
    score_cache_key,
    set_rising_cache,
    set_score_cache,
)


def score_cutoff(now=None):
    now = now or datetime.now()
    return (now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')


def compute_lineup_scores(db=None, now=None):
    db = db or get_db()
    cutoff = score_cutoff(now)
    rows = db.execute(
        '''
        SELECT l.id AS lineup_id,
               COALESCE(l.admin_like_adjustment, 0) AS admin_like_adjustment,
               COALESCE(l.admin_copy_adjustment, 0) AS admin_copy_adjustment,
               COALESCE(like_totals.like_count, 0) AS like_count,
               COALESCE(copy_totals.copy_count, 0) AS copy_count
        FROM lineups l
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS like_count
            FROM likes
            WHERE created_at >= ?
            GROUP BY lineup_id
        ) AS like_totals ON like_totals.lineup_id = l.id
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS copy_count
            FROM copy_events
            WHERE counted = 1 AND created_at >= ?
            GROUP BY lineup_id
        ) AS copy_totals ON copy_totals.lineup_id = l.id
        WHERE l.status != 'deleted'
        ''',
        (cutoff, cutoff),
    ).fetchall()
    result = []
    for row in rows:
        likes = row['like_count'] + row['admin_like_adjustment']
        copies = row['copy_count'] + row['admin_copy_adjustment']
        score = max(0, likes) * 5 + max(0, copies)
        result.append({
            'lineup_id': row['lineup_id'],
            'score': score,
            'like_count': max(0, likes),
            'copy_count': max(0, copies),
        })
    return result


def assign_levels(scores):
    positive = sorted([item for item in scores if item['score'] > 0], key=lambda item: (-item['score'], item['lineup_id']))
    levels = {item['lineup_id']: 'B' for item in scores}
    total = len(positive)
    if total == 0:
        return levels
    ss_limit = max(1, ceil(total * 0.05))
    s_limit = max(ss_limit, ceil(total * 0.20))
    a_limit = max(s_limit, ceil(total * 0.50))
    for index, item in enumerate(positive, start=1):
        if index <= ss_limit:
            level = 'SS'
        elif index <= s_limit:
            level = 'S'
        elif index <= a_limit:
            level = 'A'
        else:
            level = 'B'
        levels[item['lineup_id']] = level
    return levels


def score_map(include_counts=True, db=None, refresh=False):
    db = db or get_db()
    cache_key = score_cache_key(db)
    if not refresh:
        cached = get_score_cache(cache_key)
        if cached is not None:
            return cached
    scores = compute_lineup_scores(db=db)
    levels = assign_levels(scores)
    data = {}
    for item in scores:
        data[item['lineup_id']] = {
            'score': item['score'],
            'rank_level': levels[item['lineup_id']],
            'like_count': item['like_count'],
            'copy_count': item['copy_count'],
        }
    set_score_cache(cache_key, data)
    return data


def rising_map(db=None, now=None, refresh=False):
    db = db or get_db()
    requested_now = now
    now = now or datetime.now()
    cache_key = rising_cache_key(db)
    if not refresh and requested_now is None:
        cached = get_rising_cache(cache_key)
        if cached is not None:
            return cached
    recent_cutoff = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    previous_cutoff = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    rows = db.execute(
        '''
        SELECT
            l.id AS lineup_id,
            COALESCE(recent_likes.c, 0) AS recent_likes,
            COALESCE(recent_copies.c, 0) AS recent_copies,
            COALESCE(previous_likes.c, 0) AS previous_likes,
            COALESCE(previous_copies.c, 0) AS previous_copies
        FROM lineups l
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS c
            FROM likes
            WHERE created_at >= ?
            GROUP BY lineup_id
        ) recent_likes ON recent_likes.lineup_id = l.id
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS c
            FROM copy_events
            WHERE counted = 1 AND created_at >= ?
            GROUP BY lineup_id
        ) recent_copies ON recent_copies.lineup_id = l.id
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS c
            FROM likes
            WHERE created_at >= ? AND created_at < ?
            GROUP BY lineup_id
        ) previous_likes ON previous_likes.lineup_id = l.id
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS c
            FROM copy_events
            WHERE counted = 1 AND created_at >= ? AND created_at < ?
            GROUP BY lineup_id
        ) previous_copies ON previous_copies.lineup_id = l.id
        WHERE l.status = 'normal'
        ''',
        (recent_cutoff, recent_cutoff, previous_cutoff, recent_cutoff, previous_cutoff, recent_cutoff),
    ).fetchall()
    data = {}
    for row in rows:
        recent_score = row['recent_likes'] * 5 + row['recent_copies']
        previous_score = row['previous_likes'] * 5 + row['previous_copies']
        data[row['lineup_id']] = recent_score - previous_score
    if requested_now is None:
        set_rising_cache(cache_key, data)
    return data
