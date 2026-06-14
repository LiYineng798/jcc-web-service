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


def test_db_schema_table_helpers_use_postgres_metadata_queries():
    executed = []

    class FakeRow(dict):
        pass

    class FakeDb:
        kind = 'postgres'

        def execute(self, sql, params=()):
            executed.append((sql, params))
            if 'information_schema.columns' in sql:
                return self
            if 'information_schema.tables' in sql:
                return self
            raise AssertionError(sql)

        def fetchall(self):
            sql = executed[-1][0]
            if 'information_schema.columns' in sql:
                return [FakeRow(column_name='id'), FakeRow(column_name='username')]
            return [FakeRow(table_name='users'), FakeRow(table_name='lineups')]

    columns = table_columns(FakeDb(), 'users')
    names = table_names(FakeDb())

    assert columns == {'id', 'username'}
    assert names == {'users', 'lineups'}
    assert executed[0][1] == ('users',)
