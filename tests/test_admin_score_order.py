from datetime import datetime, timedelta

from test_admin import login_admin


def seed_lineups(app):
    from db import get_db, now_text
    with app.app_context():
        db = get_db()
        owner = db.execute("SELECT id FROM users WHERE role='admin'").fetchone()['id']
        ids = []
        for index, (season, status, likes, copies) in enumerate([
            ('s17-star-god', 'normal', 2, 0),
            ('s17-star-god', 'normal', 0, 10),
            ('s16-legends', 'normal', 20, 0),
            ('s17-star-god', 'hidden', 3, 0),
            ('s17-star-god', 'deleted', 100, 0),
            ('s17-star-god', 'normal', -2, -5),
        ]):
            ids.append(db.execute('''INSERT INTO lineups
                (user_id,name,code,season_id,status,admin_like_adjustment,admin_copy_adjustment,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (owner, f'测试阵容 {index}', f'#CODE{index}', season, status, likes, copies, now_text(), now_text())).lastrowid)
        # An old like does not contribute to the current seven-day score.
        old = (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S')
        db.execute('INSERT INTO likes (user_id,lineup_id,like_date,created_at) VALUES (?,?,?,?)', (owner, ids[-1], old[:10], old))
        db.commit()
        return ids


def test_score_order_filters_before_pagination_and_has_stable_ties(client, app):
    ids = seed_lineups(app)
    login_admin(client)
    url = '/api/admin/lineups?order=score_desc&season=s17-star-god&status=normal&page_size=1'
    first = client.get(url).get_json()
    assert first['total'] == 3
    assert first['total_pages'] == 3
    assert [(item['id'], item['score']) for item in first['items']] == [(ids[1], 10)]
    second = client.get(url + '&page=2').get_json()
    assert second['items'][0]['id'] == ids[0]
    assert second['items'][0]['score'] == 10
    last = client.get(url + '&page=999').get_json()
    assert last['page'] == 3
    assert last['items'][0]['id'] == ids[-1]
    assert last['items'][0]['score'] == 0
    all_items = client.get('/api/admin/lineups?order=score_desc').get_json()['items']
    assert [item['id'] for item in all_items] == [ids[2], ids[3], ids[1], ids[0], ids[5]]
    search = client.get('/api/admin/lineups?order=score_desc&q=CODE0').get_json()
    assert search['total'] == 1 and search['items'][0]['id'] == ids[0]
    assert client.get('/api/admin/lineups?order=score_desc&q=无匹配').get_json()['items'] == []
    assert client.get('/api/admin/lineups?order=unknown').status_code == 400


def test_score_page_loads_only_page_records_without_per_row_queries(app):
    from admin_lineup_service import list_admin_lineups_by_score
    from db import get_db
    from scoring import score_map
    seed_lineups(app)
    with app.app_context():
        db = get_db()
        scores = score_map()
        admin = db.execute("SELECT * FROM users WHERE role='admin'").fetchone()
        statements = []
        db.connection.set_trace_callback(statements.append)
        try:
            result = list_admin_lineups_by_score(db, '', 'all', '', scores, admin, 1, 2)
        finally:
            db.connection.set_trace_callback(None)
        assert len(result['items']) == 2
        assert len(statements) == 2
        assert statements[0].startswith('SELECT lineups.id ')
        assert 'lineups.id IN (' in statements[1]


def test_score_order_requires_admin(client):
    assert client.get('/api/admin/lineups?order=score_desc').status_code == 401
