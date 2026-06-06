def test_schema_creates_required_tables(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json()['ok'] is True

    table_names = client.application.get_table_names()
    assert 'users' in table_names
    assert 'lineups' in table_names
    assert 'likes' in table_names
    assert 'copy_events' in table_names
    assert 'cache_state' in table_names
    assert 'audit_logs' in table_names
    assert 'visit_events' in table_names


def test_patch_notes_table_exists(app):
    assert 'patch_notes' in app.get_table_names()


def test_patch_notes_columns_exist(client):
    with client.application.app_context():
        from db import get_db
        columns = get_db().execute('PRAGMA table_info(patch_notes)').fetchall()
    names = {row['name'] for row in columns}
    assert {
        'id',
        'title',
        'version',
        'source_url',
        'summary_markdown',
        'original_text',
        'status',
        'published_at',
        'created_at',
        'updated_at',
    }.issubset(names)
