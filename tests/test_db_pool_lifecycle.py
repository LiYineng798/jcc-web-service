"""Exercise the production pool path without opening network connections."""

from concurrent.futures import ThreadPoolExecutor
import sys
from threading import Barrier, Event, Lock
from types import SimpleNamespace

import pytest
from flask import Flask
from psycopg_pool import ConnectionPool

import db


class OfflinePool(ConnectionPool):
    """Use Psycopg's real ownership check with offline connection doubles."""

    def __init__(self, *args, **kwargs):
        kwargs['open'] = False
        super().__init__(*args, **kwargs)
        self.returned = []

    def getconn(self, timeout=None):
        return SimpleNamespace(_pool=self)

    def putconn(self, connection):
        self._check_pool_putconn(connection)
        self.returned.append(connection)


@pytest.fixture()
def pool_app(monkeypatch):
    monkeypatch.setattr(db, '_pg_pool', None)
    monkeypatch.setattr(db, '_pg_pool_url', None)
    monkeypatch.setattr('psycopg_pool.ConnectionPool', OfflinePool)
    app = Flask(__name__)
    # Deliberately do not set TESTING: get_db normally bypasses pools in tests.
    app.config['DATABASE_URL'] = 'postgresql://unused/pool-test'
    app.teardown_appcontext(db.close_db)
    yield app
    if db._pg_pool is not None:
        db._pg_pool.close()


def test_concurrent_first_use_creates_one_pool_and_returns_all_connections(pool_app, monkeypatch):
    workers = 8
    start = Barrier(workers)
    borrowed = Barrier(workers)
    first_constructor = Event()
    duplicate_constructor = Event()
    release_constructor = Event()
    created = []
    record_lock = Lock()

    class SlowPool(OfflinePool):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with record_lock:
                created.append(self)
                first_constructor.set()
                if len(created) > 1:
                    duplicate_constructor.set()
            assert release_constructor.wait(5), 'Constructor was not released'

    monkeypatch.setattr('psycopg_pool.ConnectionPool', SlowPool)

    def use_connection():
        start.wait(timeout=5)
        with pool_app.app_context():
            connection = db.get_db()
            assert db.get_db() is connection
            borrowed.wait(timeout=5)
            return connection.connection

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(use_connection) for _ in range(workers)]
            try:
                assert first_constructor.wait(5)
                # Widen the cold-start race: an unlocked implementation enters
                # another constructor while the first one is still blocked.
                duplicate_constructor.wait(.2)
            finally:
                release_constructor.set()
            connections = [future.result(timeout=5) for future in futures]
        assert len(created) == 1
        assert len(created[0].returned) == workers
        assert {id(c) for c in connections} == {id(c) for c in created[0].returned}
    finally:
        for pool in created:
            pool.close()


@pytest.mark.parametrize('clear_global', [False, True])
@pytest.mark.parametrize('task_fails', [False, True])
def test_return_uses_checkout_owner_even_if_global_changes(pool_app, monkeypatch, clear_global, task_fails):
    owner = OfflinePool(name='jcc-web')
    replacement = None if clear_global else OfflinePool(name='jcc-web')

    def checkout(timeout=None):
        # Simulate another configuration replacing the global during getconn.
        monkeypatch.setattr(db, '_pg_pool', replacement)
        return SimpleNamespace(_pool=owner)

    monkeypatch.setattr(owner, 'getconn', checkout)
    monkeypatch.setattr(db, '_postgres_pool', lambda url: owner)
    try:
        def use_connection():
            with pool_app.app_context():
                db.get_db()
                if task_fails:
                    raise RuntimeError('task failed')

        if task_fails:
            with pytest.raises(RuntimeError, match='task failed'):
                use_connection()
        else:
            use_connection()
        assert len(owner.returned) == 1
        if replacement is not None:
            assert replacement.returned == []
    finally:
        owner.close()
        if replacement is not None:
            replacement.close()


def test_pool_replacement_failure_keeps_previous_pool_usable(pool_app, monkeypatch):
    old = db._postgres_pool(pool_app.config['DATABASE_URL'])
    closes = []
    monkeypatch.setattr(old, 'close', lambda: closes.append(True))

    def fail_constructor(*args, **kwargs):
        raise ValueError('invalid pool configuration')

    monkeypatch.setattr('psycopg_pool.ConnectionPool', fail_constructor)
    with pytest.raises(ValueError, match='invalid pool configuration'):
        db._postgres_pool('postgresql://unused/another-db')
    # Offline pools start closed, so observe close() calls instead of .closed.
    assert closes == []
    assert db._pg_pool is old
    assert db._pg_pool_url == pool_app.config['DATABASE_URL']


def test_teardown_returns_connection_only_once(pool_app):
    with pool_app.app_context():
        connection = db.get_db().connection
        owner = db._pg_pool
        db.close_db()
        db.close_db()
    assert owner.returned == [connection]


def test_first_constructor_failure_can_be_retried(pool_app, monkeypatch):
    attempts = []

    def create_pool(*args, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise ValueError('first attempt failed')
        return OfflinePool(*args, **kwargs)

    monkeypatch.setattr('psycopg_pool.ConnectionPool', create_pool)
    with pytest.raises(ValueError, match='first attempt failed'):
        with pool_app.app_context():
            db.get_db()
    assert db._pg_pool is None
    assert db._pg_pool_url is None
    with pool_app.app_context():
        db.get_db()
    assert len(db._pg_pool.returned) == 1


def test_checkout_failure_does_not_return_an_unborrowed_connection(pool_app, monkeypatch):
    pool = db._postgres_pool(pool_app.config['DATABASE_URL'])

    def fail_checkout(timeout=None):
        raise TimeoutError('checkout timed out')

    monkeypatch.setattr(pool, 'getconn', fail_checkout)
    with pytest.raises(TimeoutError, match='checkout timed out'):
        with pool_app.app_context():
            db.get_db()
    assert pool.returned == []


def test_missing_pool_package_uses_and_closes_direct_connection(pool_app, monkeypatch):
    closes = []
    direct = SimpleNamespace(close=lambda: closes.append(True))
    monkeypatch.setitem(sys.modules, 'psycopg_pool', None)
    monkeypatch.setattr(db.psycopg, 'connect', lambda *args, **kwargs: direct)
    with pool_app.app_context():
        assert db.get_db().connection is direct
    assert closes == [True]
    assert db._pg_pool is None
