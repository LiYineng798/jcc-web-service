import pytest

from db import get_db
from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


@pytest.fixture()
def people(app):
    owner, reader, other, admin, guest = [app.test_client() for _ in range(5)]
    for client, name in ((owner,'author'),(reader,'reader'),(other,'other')):
        assert register_user(client, username=name, email=f'{name}@example.com').status_code == 201
    assert admin.post('/api/login', json={'account':'adminxlx','password':'Admin1234'}).status_code == 200
    return owner, reader, other, admin, guest


def post(client, url, data=None):
    return client.post(url, json=data or {}, headers=auth_headers(client))


def notices(client, query=''):
    response = client.get('/api/me/notifications' + query)
    assert response.status_code == 200
    return response.get_json()


def mark(client, item, state='read'):
    return client.put('/api/me/notifications/' + item['id'], json={'status':state,'revision':item['revision']}, headers=auth_headers(client))


def test_aggregates_each_kind_and_reopens_read_notice_without_leaking_actors(people):
    owner, reader, other, _, _ = people
    lineup = create_lineup(owner).get_json()['id']
    assert notices(owner)['total'] == 0
    for person in (reader, other):
        for kind in ('like','favorite','copy'):
            assert post(person, f'/api/lineups/{lineup}/{kind}').status_code in (200,201)
    inbox = notices(owner)
    assert inbox['total'] == inbox['unread_total'] == 3
    assert {item['kind'] for item in inbox['items']} == {'like','favorite','copy'}
    assert all(item['event_count'] == 2 for item in inbox['items'])
    item = next(item for item in inbox['items'] if item['kind']=='copy')
    assert mark(owner,item).status_code == 200
    guest = owner.application.test_client()
    assert post(guest,f'/api/lineups/{lineup}/copy').status_code == 200
    assert mark(owner,item).status_code == 409
    updated = next(item for item in notices(owner)['items'] if item['kind']=='copy')
    assert updated['event_count'] == 3 and updated['new_count'] == 1 and updated['notice_state']=='unread'
    assert 'ip_address' not in updated and 'user_id' not in updated


def test_self_actions_duplicates_and_refavorite_do_not_create_achievement_spam(people):
    owner, reader, _, _, _ = people
    lineup = create_lineup(owner).get_json()['id']
    for kind in ('like','favorite','copy'):
        post(owner,f'/api/lineups/{lineup}/{kind}')
    assert notices(owner)['total'] == 0
    for _ in range(2):
        for kind in ('like','favorite','copy'):
            post(reader,f'/api/lineups/{lineup}/{kind}')
    reader.delete(f'/api/lineups/{lineup}/favorite',headers=auth_headers(reader))
    post(reader,f'/api/lineups/{lineup}/favorite')
    assert all(n['event_count']==1 for n in notices(owner)['items'])


def test_feedback_submission_reply_progress_history_and_private_access(people):
    owner, reader, _, admin, guest = people
    receipt = post(owner,'/api/guestbook',{'content':'希望增加装备筛选'}).get_json()
    key=receipt['feedback_id']
    url=f'/api/me/feedback/{key}'
    assert guest.get(url).status_code==401
    assert reader.get(url).status_code==404
    assert reader.get(receipt['feedback_url']).status_code==404
    first=notices(owner)['items'][0]
    assert first['category']=='feedback' and mark(owner,first).status_code==200
    assert post(reader,f'/api/admin/feedback/{key}/reply',{'status':'resolved','body':'fake','revision':1}).status_code==403
    assert post(admin,f'/api/admin/feedback/{key}/reply',{'status':'in_progress','body':'正在核实','revision':1}).status_code==200
    assert post(admin,f'/api/admin/feedback/{key}/reply',{'status':'resolved','body':'旧页面回复','revision':1}).status_code==409
    assert mark(owner,first).status_code==409
    assert post(admin,f'/api/admin/feedback/{key}/reply',{'status':'resolved','body':'已增加筛选功能','revision':2}).status_code==200
    detail=owner.get(url)
    assert detail.headers['Cache-Control']=='private, no-store'
    data=detail.get_json()
    assert data['status']=='resolved' and data['revision']==3
    assert [e['body'] for e in data['events']]==['希望增加装备筛选','正在核实','已增加筛选功能']
    assert 'ip_address' not in str(data) and 'actor_user_id' not in str(data)
    assert notices(owner)['total']==1 and notices(owner)['unread_total']==1


def test_guests_keep_simple_message_flow_without_feedback_thread(people):
    _, _, _, admin, guest=people
    result=post(guest,'/api/guestbook',{'nickname':'游客','content':'游客建议'})
    assert result.status_code==201 and result.get_json()=={'ok':True}
    with guest.application.app_context():
        db=get_db()
        assert db.execute('SELECT COUNT(*) AS c FROM feedback_threads').fetchone()['c']==0
        msg=db.execute('SELECT id FROM guestbook_messages').fetchone()['id']
    assert admin.get(f'/api/admin/feedback/guestbook/{msg}').status_code==404


def test_report_progress_and_legacy_resolution_both_notify_reporter(people):
    owner, reader, _, admin, _=people
    lineup=create_lineup(owner).get_json()['id']
    report=post(reader,f'/api/lineups/{lineup}/report',{'reason':'代码不可用'}).get_json()
    key=report['feedback_id']
    assert post(admin,f'/api/admin/feedback/{key}/reply',{'status':'in_progress','body':'正在测试导入','revision':1}).status_code==200
    assert post(admin,f'/api/admin/reports/{report["id"]}/resolve',{'status':'resolved','hide_lineup':True}).status_code==200
    detail=reader.get(f'/api/me/feedback/{key}').get_json()
    assert detail['status']=='resolved' and len(detail['events'])==3
    assert notices(reader)['total']==1
    assert notices(owner)['total']==0  # reporter feedback is not exposed to the lineup's author
    with owner.application.app_context():
        assert get_db().execute('SELECT status FROM lineups WHERE id=?',(lineup,)).fetchone()['status']=='hidden'


def test_notification_filters_pagination_and_moderation_compatibility(people):
    owner, reader, _, admin, _=people
    lineup=create_lineup(owner).get_json()
    post(reader,f'/api/lineups/{lineup["id"]}/like')
    post(owner,'/api/guestbook',{'content':'请求帮助'})
    assert post(admin,f'/api/admin/lineups/{lineup["id"]}/moderation/ban',{'reason':'待核验','version':lineup['version']}).status_code==200
    assert notices(owner)['total']==3
    for category in ('interaction','feedback','moderation'):
        data=notices(owner,f'?category={category}')
        assert data['total']==1 and data['unread_total']==3
        assert data['items'][0]['category']==category
    assert notices(owner,'?page_size=1&page=2')['page']==2
    moderation=notices(owner,'?category=moderation')['items'][0]
    assert mark(owner,moderation).status_code==200
    assert owner.get('/api/me/lineup-notifications').get_json()['items'][0]['notice_state']=='read'
    assert mark(reader,moderation).status_code==409


@pytest.mark.parametrize('payload', [None,{}, {'status':'bad','revision':1}, {'status':'resolved','body':'','revision':1}, {'status':'resolved','body':'x'*1001,'revision':1}, {'status':'in_progress','revision':True}])
def test_reply_validation_and_csrf(people,payload):
    owner, _, _, admin, _=people
    key=post(owner,'/api/guestbook',{'content':'建议'}).get_json()['feedback_id']
    assert post(admin,f'/api/admin/feedback/{key}/reply',payload).status_code==400
    assert admin.post(f'/api/admin/feedback/{key}/reply',json={'status':'in_progress','revision':1}).status_code==403
    assert owner.get(f'/api/me/feedback/{key}').get_json()['revision']==1


def test_rollback_does_not_leave_reply_or_notifications(people,monkeypatch):
    owner, _, _, admin, _=people
    key=post(owner,'/api/guestbook',{'content':'建议'}).get_json()['feedback_id']
    def fail(*args,**kwargs): raise RuntimeError('audit unavailable')
    monkeypatch.setattr('feedback_service.write_audit',fail)
    with pytest.raises(RuntimeError):
        post(admin,f'/api/admin/feedback/{key}/reply',{'status':'in_progress','body':'回复','revision':1})
    data=owner.get(f'/api/me/feedback/{key}').get_json()
    assert data['revision']==1 and len(data['events'])==1
    assert notices(owner)['items'][0]['revision']==1


def test_guestbook_deletion_removes_private_thread_and_notification(people):
    owner, _, _, admin, _=people
    key=post(owner,'/api/guestbook',{'content':'建议'}).get_json()['feedback_id']
    data=owner.get(f'/api/me/feedback/{key}').get_json()
    assert admin.delete(f'/api/guestbook/{data["source_id"]}',headers=auth_headers(admin)).status_code==200
    assert owner.get(f'/api/me/feedback/{key}').status_code==404
    assert notices(owner)['total']==0
