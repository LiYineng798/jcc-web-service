import sqlite3
from datetime import datetime

from flask import current_app, g
from werkzeug.security import generate_password_hash

from lineup_cache import clear_lineup_query_caches
from db_migrations import ensure_indexes, migrate_schema
from db_schema import (
    SCHEMA,
    table_columns as schema_table_columns,
    table_names as schema_table_names,
)


def now_text():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_db():
    if 'db' not in g:
        db = sqlite3.connect(current_app.config['DATABASE'])
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('PRAGMA journal_mode = WAL')
        db.execute('PRAGMA busy_timeout = 5000')
        g.db = db
    return g.db


def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    admin_id = bootstrap_admin(db)
    migrate_schema(db, admin_id, now_text)
    ensure_indexes(db)
    clear_lineup_query_caches()
    db.commit()


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
