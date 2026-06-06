from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from time import monotonic

from flask import current_app

HOME_VIEW_CACHE_TTL_SECONDS = 30
SCORE_CACHE_TTL_SECONDS = 30
RISING_CACHE_TTL_SECONDS = 30
RECOMMENDED_CACHE_TTL_SECONDS = 30


@dataclass
class CacheEntry:
    loaded_at: float
    value: object


class TimedCache:
    def __init__(self, ttl_seconds):
        self.ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._entries = {}

    def get(self, key):
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            if monotonic() - entry.loaded_at > self.ttl_seconds:
                self._entries.pop(key, None)
                return None
            return deepcopy(entry.value)

    def set(self, key, value):
        with self._lock:
            self._entries[key] = CacheEntry(monotonic(), deepcopy(value))

    def clear(self):
        with self._lock:
            self._entries.clear()


_HOME_VIEW_CACHE = TimedCache(HOME_VIEW_CACHE_TTL_SECONDS)
_SCORE_CACHE = TimedCache(SCORE_CACHE_TTL_SECONDS)
_RISING_CACHE = TimedCache(RISING_CACHE_TTL_SECONDS)
_RECOMMENDED_CACHE = TimedCache(RECOMMENDED_CACHE_TTL_SECONDS)


def cache_namespace():
    try:
        return current_app.config.get('DATABASE', 'default-database')
    except Exception:
        return 'default-database'


def cache_revision(db, cache_key):
    row = db.execute(
        'SELECT revision FROM cache_state WHERE cache_key = ?',
        (cache_key,),
    ).fetchone()
    return int(row['revision']) if row else 0


def home_view_cache_key(db, user_id, user_role, view, sort, query, season_id, wants_page, page, page_size):
    return (
        cache_namespace(),
        cache_revision(db, 'home'),
        user_id or 0,
        user_role or '',
        view,
        sort,
        query or '',
        season_id or '',
        int(bool(wants_page)),
        page or 0,
        page_size or 0,
    )


def score_cache_key(db):
    return (cache_namespace(), cache_revision(db, 'score'))


def rising_cache_key(db):
    return (cache_namespace(), cache_revision(db, 'score'))


def recommended_cache_key(db, user_id):
    return (cache_namespace(), cache_revision(db, 'score'), user_id or 0)


def get_home_view_cache(key):
    return _HOME_VIEW_CACHE.get(key)


def set_home_view_cache(key, value):
    _HOME_VIEW_CACHE.set(key, value)


def clear_home_view_cache():
    _HOME_VIEW_CACHE.clear()


def get_score_cache(key):
    return _SCORE_CACHE.get(key)


def set_score_cache(key, value):
    _SCORE_CACHE.set(key, value)


def clear_score_cache():
    _SCORE_CACHE.clear()


def get_rising_cache(key):
    return _RISING_CACHE.get(key)


def set_rising_cache(key, value):
    _RISING_CACHE.set(key, value)


def clear_rising_cache():
    _RISING_CACHE.clear()


def get_recommended_cache(key):
    return _RECOMMENDED_CACHE.get(key)


def set_recommended_cache(key, value):
    _RECOMMENDED_CACHE.set(key, value)


def clear_recommended_cache():
    _RECOMMENDED_CACHE.clear()


def clear_lineup_query_caches():
    clear_home_view_cache()
    clear_score_cache()
    clear_rising_cache()
    clear_recommended_cache()
