import sqlite3
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from flask import current_app, g
from werkzeug.security import generate_password_hash

from db_adapter import database_kind, to_driver_sql
from lineup_cache import clear_lineup_query_caches
from db_migrations import ensure_indexes, migrate_schema
from db_schema import (
    SCHEMA,
    table_columns as schema_table_columns,
    table_names as schema_table_names,
)


def now_text():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def db_kind():
    if 'db_kind' in g:
        return g.db_kind
    return database_kind(current_app.config['DATABASE_URL'])


class DriverSqlConnection:
    def __init__(self, connection, kind):
        self.connection = connection
        self.kind = kind

    def execute(self, sql, params=()):
        return self.connection.execute(to_driver_sql(sql, self.kind), params)

    def executemany(self, sql, params_seq):
        return self.connection.executemany(to_driver_sql(sql, self.kind), params_seq)

    def executescript(self, sql):
        return self.connection.executescript(sql)

    def commit(self):
        return self.connection.commit()

    def rollback(self):
        return self.connection.rollback()

    def close(self):
        return self.connection.close()

    def cursor(self, *args, **kwargs):
        return DriverSqlCursor(self.connection.cursor(*args, **kwargs), self.kind)


class DriverSqlCursor:
    def __init__(self, cursor, kind):
        self.cursor = cursor
        self.kind = kind

    def execute(self, sql, params=()):
        return self.cursor.execute(to_driver_sql(sql, self.kind), params)

    def executemany(self, sql, params_seq):
        return self.cursor.executemany(to_driver_sql(sql, self.kind), params_seq)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def __iter__(self):
        return iter(self.cursor)

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self.cursor.__exit__(exc_type, exc, traceback)

    def __getattr__(self, name):
        return getattr(self.cursor, name)


def get_db():
    if 'db' not in g:
        kind = database_kind(current_app.config['DATABASE_URL'])
        if kind == 'postgres':
            db = DriverSqlConnection(
                psycopg.connect(current_app.config['DATABASE_URL'], row_factory=dict_row),
                kind,
            )
        else:
            raw_db = sqlite3.connect(current_app.config['DATABASE'])
            raw_db.row_factory = sqlite3.Row
            db = DriverSqlConnection(raw_db, kind)
            db.execute('PRAGMA foreign_keys = ON')
            db.execute('PRAGMA journal_mode = WAL')
            db.execute('PRAGMA busy_timeout = 5000')
        g.db_kind = kind
        g.db = db
    return g.db


def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    kind = database_kind(current_app.config['DATABASE_URL'])
    if kind == 'postgres':
        if not postgres_schema_ready():
            raise RuntimeError('PostgreSQL schema is not initialized. Run jcc-db-service migrations before starting the web service.')
        clear_lineup_query_caches()
        return
    db = get_db()
    db.executescript(SCHEMA)
    admin_id = bootstrap_admin(db)
    migrate_schema(db, admin_id, now_text)
    ensure_indexes(db)
    clear_lineup_query_caches()
    db.commit()


def postgres_schema_ready():
    connection = psycopg.connect(current_app.config['DATABASE_URL'], row_factory=dict_row)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'schema_migrations'
                ) AS exists
                '''
            )
            return bool(cursor.fetchone()['exists'])
    finally:
        connection.close()


def bootstrap_admin(db):
    username = current_app.config['ADMIN_USERNAME']
    password = current_app.config['ADMIN_PASSWORD']
    existing = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if existing:
        return existing['id']
    now = now_text()
    cursor = db.execute(
        '''INSERT INTO users (username, email, nickname, password_hash, role, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'admin', 'active', ?, ?)''',
        (username, f'{username}@local.admin', '系统', generate_password_hash(password), now, now),
    )
    return cursor.lastrowid

def table_columns(db, table_name):
    return schema_table_columns(db, table_name)


def table_names():
    return schema_table_names(get_db())
