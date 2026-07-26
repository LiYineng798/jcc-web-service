from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from copy import deepcopy
from threading import RLock
from time import monotonic

from flask import current_app

HOME_VIEW_CACHE_TTL_SECONDS = 30
SCORE_CACHE_TTL_SECONDS = 30
RISING_CACHE_TTL_SECONDS = 30
RECOMMENDED_CACHE_TTL_SECONDS = 30

# Bounded LRU sizes — this runs on a 2GB host; anonymous requests must not be
# able to grow the caches without limit (search terms used to mint new keys).
HOME_VIEW_CACHE_MAX_ENTRIES = 128
SMALL_CACHE_MAX_ENTRIES = 32

# Score-style caches may serve a result whose revision is stale for this many
# seconds. Copies/likes bump the revision constantly on a busy site; without a
# floor the expensive aggregates recompute on nearly every request. Tests run
# with tolerance 0 so score-math assertions observe writes immediately.
SCORE_STALE_TOLERANCE_SECONDS = 10


def _score_stale_tolerance():
    try:
        if current_app.config.get('TESTING'):
            return 0
    except Exception:
        pass
    return SCORE_STALE_TOLERANCE_SECONDS


@dataclass
class CacheEntry:
    loaded_at: float
    value: object
    revision: object


class TimedCache:
    """TTL + bounded-LRU cache with revision stamps.

    The revision is stored on the entry instead of inside the key so that a
    revision bump overwrites the same slot rather than stranding unreachable
    entries (the previous design leaked one entry per like/copy).
    """

    def __init__(self, ttl_seconds, max_entries):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._lock = RLock()
        self._entries = OrderedDict()

    def get(self, key, revision=None, stale_tolerance=0):
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            age = monotonic() - entry.loaded_at
            if age > self.ttl_seconds:
                self._entries.pop(key, None)
                return None
            if revision is not None and entry.revision != revision and age > stale_tolerance:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return deepcopy(entry.value)

    def set(self, key, value, revision=None):
        with self._lock:
            self._entries[key] = CacheEntry(monotonic(), deepcopy(value), revision)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self):
        with self._lock:
            self._entries.clear()


_HOME_VIEW_CACHE = TimedCache(HOME_VIEW_CACHE_TTL_SECONDS, HOME_VIEW_CACHE_MAX_ENTRIES)
_SCORE_CACHE = TimedCache(SCORE_CACHE_TTL_SECONDS, SMALL_CACHE_MAX_ENTRIES)
_RISING_CACHE = TimedCache(RISING_CACHE_TTL_SECONDS, SMALL_CACHE_MAX_ENTRIES)
_RECOMMENDED_CACHE = TimedCache(RECOMMENDED_CACHE_TTL_SECONDS, SMALL_CACHE_MAX_ENTRIES)


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


def _bounded_query(query):
    value = query or ''
    if len(value) > 48:
        return hashlib.sha1(value.encode('utf-8')).hexdigest()
    return value


def home_view_cache_key(db, user_id, user_role, view, sort, query, season_id, wants_page, page, page_size):
    """Returns an opaque (key, revision) reference for get/set below."""
    key = (
        cache_namespace(),
        user_id or 0,
        user_role or '',
        view,
        sort,
        _bounded_query(query),
        season_id or '',
        int(bool(wants_page)),
        page or 0,
        page_size or 0,
    )
    return key, cache_revision(db, 'home')


def score_cache_key(db):
    return (cache_namespace(),), cache_revision(db, 'score')


def rising_cache_key(db):
    return (cache_namespace(), 'rising'), cache_revision(db, 'score')


def recommended_cache_key(db, user_id):
    return (cache_namespace(), user_id or 0), cache_revision(db, 'score')


def get_home_view_cache(ref):
    key, revision = ref
    return _HOME_VIEW_CACHE.get(key, revision)


def set_home_view_cache(ref, value):
    key, revision = ref
    _HOME_VIEW_CACHE.set(key, value, revision)


def clear_home_view_cache():
    _HOME_VIEW_CACHE.clear()


def get_score_cache(ref):
    key, revision = ref
    return _SCORE_CACHE.get(key, revision, _score_stale_tolerance())


def set_score_cache(ref, value):
    key, revision = ref
    _SCORE_CACHE.set(key, value, revision)


def clear_score_cache():
    _SCORE_CACHE.clear()


def get_rising_cache(ref):
    key, revision = ref
    return _RISING_CACHE.get(key, revision, _score_stale_tolerance())


def set_rising_cache(ref, value):
    key, revision = ref
    _RISING_CACHE.set(key, value, revision)


def clear_rising_cache():
    _RISING_CACHE.clear()


def get_recommended_cache(ref):
    key, revision = ref
    return _RECOMMENDED_CACHE.get(key, revision, _score_stale_tolerance())


def set_recommended_cache(ref, value):
    key, revision = ref
    _RECOMMENDED_CACHE.set(key, value, revision)


def clear_recommended_cache():
    _RECOMMENDED_CACHE.clear()


def clear_lineup_query_caches():
    clear_home_view_cache()
    clear_score_cache()
    clear_rising_cache()
    clear_recommended_cache()
