from datetime import datetime, timedelta

from db import get_db
from lineup_cache import (
    get_recommended_cache,
    recommended_cache_key,
    set_recommended_cache,
)
from scoring import score_map


def recommended_scores(user=None, scores=None, db=None, refresh=False):
    db = db or get_db()
    user_id = user['id'] if user else None
    cache_key = recommended_cache_key(db, user_id)
    if scores is None and not refresh:
        cached = get_recommended_cache(cache_key)
        if cached is not None:
            return cached
    scores = scores if scores is not None else score_map(db=db)
    fresh_cutoff = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    rows = db.execute(
        '''
        SELECT id, user_id, created_at, updated_at
        FROM lineups
        WHERE status = 'normal'
        '''
    ).fetchall()
    data = {}
    for row in rows:
        base = scores.get(row['id'], {}).get('score', 0)
        freshness_bonus = 12 if row['updated_at'] >= fresh_cutoff else 0
        own_penalty = -20 if user and row['user_id'] == user['id'] else 0
        data[row['id']] = base + freshness_bonus + own_penalty
    set_recommended_cache(cache_key, data)
    return data
