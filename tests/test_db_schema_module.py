from db_schema import EXTRA_INDEX_STATEMENTS, LINEUP_COLUMN_MIGRATIONS, SCHEMA, table_columns, table_names
from db import get_db


def test_db_schema_exposes_core_schema_fragments():
    assert 'CREATE TABLE IF NOT EXISTS users' in SCHEMA
    assert 'CREATE TABLE IF NOT EXISTS lineups' in SCHEMA
    assert 'season_id' in LINEUP_COLUMN_MIGRATIONS
    assert any('idx_lineups_user_status_updated_at' in statement for statement in EXTRA_INDEX_STATEMENTS)


def test_db_schema_table_helpers_read_current_database(client):
    with client.application.app_context():
        db = get_db()
        columns = table_columns(db, 'users')
        names = table_names(db)

    assert 'username' in columns
    assert 'users' in names
    assert 'lineups' in names
