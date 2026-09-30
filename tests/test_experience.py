import sqlite3
from datetime import date, timedelta
import pytest
from test_admin import login_admin

PHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148 Safari/604.1'
DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0'


def receipt(client, query='九五', headers=None):
    client.set_cookie('visitor_token','experience-test')
    return client.get('/api/lineups', query_string={'view':'all','sort':'latest','season':'s17-star-god','q':query,'page':1},headers=headers).get_json()['search_receipt']


def csrf(client):
    return {'X-CSRF-Token':client.get('/api/me').get_json()['csrf_token']}


def count(app):
    from db import get_db
    with app.app_context():
        return get_db().execute('SELECT COUNT(*) AS c FROM search_events').fetchone()['c']


def test_search_receipt_does_not_record_typeahead_and_submission_is_idempotent(client,app):
    signed=receipt(client,headers={'User-Agent':PHONE})
    receipt(client,'测试中间输入')
    assert count(app)==0
    data={'receipt':signed,'event_id':'a'*32,'result_count':999}
    headers={**csrf(client),'User-Agent':PHONE}
    assert client.post('/api/search-events',json=data,headers=headers).status_code==204
    assert client.post('/api/search-events',json=data,headers=headers).status_code==204
    assert count(app)==1
    from db import get_db
    with app.app_context():
        row=get_db().execute('SELECT * FROM search_events').fetchone()
        assert row['result_count']==0 and row['device_type']=='mobile' and row['query']=='九五'


def test_search_requires_csrf_valid_signed_result_and_same_visitor(client,app):
    signed=receipt(client)
    data={'receipt':signed,'event_id':'b'*32}
    assert client.post('/api/search-events',json=data).status_code==403
    headers=csrf(client)
    assert client.post('/api/search-events',json={**data,'receipt':signed+'bad'},headers=headers).status_code==400
    client.set_cookie('visitor_token','different')
    assert client.post('/api/search-events',json=data,headers=headers).status_code==400
    assert count(app)==0


def test_search_rejects_expired_receipts(client,monkeypatch):
    signed=receipt(client)
    headers=csrf(client)
    import time
    now=time.time()
    monkeypatch.setattr('itsdangerous.timed.time.time',lambda:now+601)
    assert client.post('/api/search-events',json={'receipt':signed,'event_id':'c'*32},headers=headers).status_code==400


def test_private_admin_and_bot_searches_do_not_issue_receipts(client):
    client.set_cookie('visitor_token','experience-test')
    for params in [{'q':'九五','view':'favorites','page':1},{'q':'九五','view':'mine','page':1},{'q':'','page':1},{'q':'x'*81,'page':1}]:
        assert 'search_receipt' not in client.get('/api/lineups',query_string=params).get_json()
    assert 'search_receipt' not in client.get('/api/lineups?q=九五&page=1',headers={'User-Agent':'Googlebot'}).get_json()
    login_admin(client)
    assert 'search_receipt' not in client.get('/api/lineups?q=九五&page=1').get_json()


@pytest.mark.parametrize('ua,expected',[(PHONE,'mobile'),(DESKTOP,'desktop'),('Mozilla/5.0 (iPad; CPU OS 18_0)','tablet'),('Mozilla/5.0 (Macintosh) Mobile/15E148 Safari','tablet'),('Mozilla/5.0 (Linux; Android 14) Safari','tablet'),('Mozilla/5.0 (Linux; Android 14) Mobile Safari','mobile'),('','unknown'),('curl/8','unknown')])
def test_device_categories(app,ua,expected):
    from device_type import request_device_type
    with app.test_request_context(headers={'User-Agent':ua}):
        assert request_device_type()==expected


def test_device_backfill_is_idempotent_and_does_not_guess_old_devices():
    from db import DriverSqlConnection
    from db_migrations import migrate_device_columns
    raw=sqlite3.connect(':memory:');raw.row_factory=sqlite3.Row
    raw.executescript("CREATE TABLE visit_events(id INTEGER,created_at TEXT); CREATE TABLE copy_action_events(id INTEGER); INSERT INTO visit_events VALUES(1,'2026-01-01');")
    db=DriverSqlConnection(raw,'sqlite')
    migrate_device_columns(db);migrate_device_columns(db)
    assert db.execute('SELECT device_type FROM visit_events').fetchone()['device_type']=='unknown'
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO visit_events(device_type) VALUES('fingerprint')")
    raw.close()


def test_device_visit_keeps_existing_deduplication_and_copy_actions_keep_success_semantics(client,app):
    from db import get_db
    from copy_action_service import record_copy_action
    client.set_cookie('visitor_token','experience-test')
    client.get('/',headers={'User-Agent':PHONE})
    client.get('/',headers={'User-Agent':DESKTOP})
    with app.test_request_context(headers={'User-Agent':PHONE}):
        record_copy_action('live_comp','fixture',success=True,counted=False)
        get_db().commit()
        assert get_db().execute('SELECT device_type FROM copy_action_events').fetchone()['device_type']=='mobile'
    with app.app_context():
        rows=get_db().execute("SELECT device_type FROM visit_events WHERE page_key='home'").fetchall()
        assert len(rows)==1 and rows[0]['device_type']=='mobile'


def test_admin_summary_excludes_admins_and_does_not_sum_overlapping_device_visitors(client,app):
    from db import get_db,now_text
    from experience_service import experience_summary
    for index,ua in enumerate([PHONE,DESKTOP]):
        signed=receipt(client,headers={'User-Agent':ua})
        assert client.post('/api/search-events',json={'receipt':signed,'event_id':str(index)*32},headers={**csrf(client),'User-Agent':ua}).status_code==204
    assert client.get('/api/admin/experience').status_code==401
    headers=login_admin(client)
    with app.app_context():
        db=get_db();admin=db.execute("SELECT id FROM users WHERE role='admin'").fetchone()['id']
        db.execute("INSERT INTO search_events(event_id,visitor_key,user_id,query,season_id,sort_key,result_count,created_at) VALUES(?,?,?,?,?,?,?,?)",('d'*32,'admin',admin,'不应出现','s17-star-god','latest',0,now_text()));db.commit()
        statements=[];db.connection.set_trace_callback(statements.append)
        result=experience_summary()
        db.connection.set_trace_callback(None)
        assert len([s for s in statements if s.startswith('SELECT')])<=10
    response=client.get('/api/admin/experience');data=response.get_json()
    assert response.headers['Cache-Control']=='private, no-store'
    assert data['summary']['searches']==2 and data['summary']['search_visitors']==1
    assert data['summary']['zero_result_pct']==100
    assert len(data['top_queries'])==1 and data['top_queries'][0]['query']=='九五'
    assert data['top_queries'][0]['sort_label']=='最新'
    assert [d['search_visitors'] for d in data['devices']][:3]==[1,0,1]
    assert client.get('/api/admin/experience?start=2026-02-30').status_code==400
    future=(date.today()+timedelta(days=1)).isoformat()
    assert client.get('/api/admin/experience?end='+future).status_code==400
    assert client.get('/api/admin/experience?start=2000-01-01').status_code==400
