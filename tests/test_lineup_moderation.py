import pytest

from db import get_db
from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


@pytest.fixture()
def actors(app):
    owner, admin, other, guest = (app.test_client() for _ in range(4))
    assert register_user(owner).status_code == 201
    assert register_user(other, username='bob', email='bob@example.com').status_code == 201
    assert admin.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'}).status_code == 200
    return owner, admin, other, guest


def change(client, lineup, action, reason='阵容码与名称不符，请修正'):
    return client.post(f"/api/admin/lineups/{lineup['id']}/moderation/{action}",
                       json={'version': lineup['version'], 'reason': reason}, headers=auth_headers(client))


def detail(client, lineup):
    return client.get(f"/api/lineups/{lineup['id']}/moderation").get_json()


def submit(owner, lineup, name='修正名称', code='#REVISED123'):
    return owner.post(f"/api/lineups/{lineup['id']}/revision", json={
        'name': name, 'code': code, 'season_id': 's16-legends', 'version': lineup['version'],
    }, headers=auth_headers(owner))


def test_ban_submit_approve_keeps_original_until_review_and_invalidates_public_cache(actors):
    owner, admin, other, guest = actors
    original = create_lineup(owner).get_json()
    assert guest.get('/api/lineups').get_json()[0]['id'] == original['id']
    ban = change(admin, original, 'ban').get_json()
    assert ban['lineup']['status'] == 'banned'
    assert guest.get('/api/lineups').get_json() == []
    assert guest.get('/api/home-stats').get_json()['total_public_lineups'] == 0
    proposed = submit(owner, ban['lineup']).get_json()
    assert proposed['lineup']['name'] == original['name']
    assert proposed['lineup']['code'] == original['code']
    assert proposed['moderation']['state'] == 'pending'
    assert proposed['moderation']['proposal']['code'] == '#REVISED123'
    approved = change(admin, proposed['lineup'], 'approve', '').get_json()
    assert approved['lineup']['status'] == 'normal'
    assert approved['lineup']['name'] == '修正名称'
    assert approved['lineup']['season_id'] == 's16-legends'
    assert approved['moderation']['notice_state'] == 'unread'
    assert [event['action'] for event in approved['events']] == ['approve', 'submit', 'ban']
    public = guest.get(f"/api/lineups/{original['id']}").get_json()
    assert public['code'] == '#REVISED123' and 'moderation' not in public


def test_banned_detail_visibility(actors):
    owner, admin, other, guest = actors
    original = create_lineup(owner).get_json()
    change(admin, original, 'ban')
    # Data endpoints and server-rendered detail never expose restricted data.
    for outsider in (other, guest):
        assert outsider.get(f"/api/lineups/{original['id']}").status_code == 404
        assert outsider.get(f"/lineup/{original['id']}").status_code == 404
    for viewer in (owner, admin):
        response = viewer.get(f"/api/lineups/{original['id']}")
        assert response.status_code == 200
        assert response.get_json()['can_delete'] is False


@pytest.mark.parametrize('method,suffix', [('put',''), ('delete',''), ('post','/hide'), ('post','/copy'), ('post','/like'), ('post','/favorite'), ('post','/report')])
def test_legacy_owner_routes_cannot_bypass_ban(actors, method, suffix):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json(); change(admin, lineup, 'ban')
    response = getattr(owner, method)(f"/api/lineups/{lineup['id']}{suffix}", json={
        'name': '绕过', 'code': '#BYPASS123', 'status': 'normal', 'reason': '反馈', 'season_id': 's17-star-god',
    }, headers=auth_headers(owner))
    assert response.status_code == 409
    assert detail(owner, lineup)['lineup']['status'] == 'banned'


def test_admin_legacy_update_score_report_and_delete_cannot_bypass_ban(actors):
    owner, admin, other, _ = actors
    lineup = create_lineup(owner).get_json()
    report = other.post(f"/api/lineups/{lineup['id']}/report", json={'reason': '失效'}, headers=auth_headers(other)).get_json()
    change(admin, lineup, 'ban')
    assert admin.put(f"/api/admin/lineups/{lineup['id']}", json={'status': 'normal'}, headers=auth_headers(admin)).status_code == 409
    assert admin.post(f"/api/admin/lineups/{lineup['id']}/adjust-score", json={'admin_like_adjustment': 1}, headers=auth_headers(admin)).status_code == 409
    assert admin.delete(f"/api/lineups/{lineup['id']}", headers=auth_headers(admin)).status_code == 409
    admin.post(f"/api/admin/reports/{report['id']}/resolve", json={'hide_lineup': True}, headers=auth_headers(admin))
    assert detail(owner, lineup)['lineup']['status'] == 'banned'


def test_reject_resubmit_archive_and_new_unread_result(actors):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json(); banned = change(admin, lineup, 'ban').get_json()
    submitted = submit(owner, banned['lineup']).get_json()
    item = detail(owner, lineup)['moderation']
    notification_url = f"/api/me/lineup-notifications/{lineup['id']}"
    assert owner.put(notification_url, json={'status': 'archived', 'revision': item['revision']}, headers=auth_headers(owner)).status_code == 200
    rejected = change(admin, submitted['lineup'], 'reject', '请重新检查赛季').get_json()
    assert rejected['moderation']['notice_state'] == 'unread'
    assert rejected['moderation']['review_note'] == '请重新检查赛季'
    assert rejected['lineup']['code'] == lineup['code']
    assert owner.put(notification_url, json={'status': 'read', 'revision': item['revision']}, headers=auth_headers(owner)).status_code == 409
    payload = owner.get('/api/me/lineup-notifications?status=unread').get_json()
    assert payload['total'] == payload['counts']['unread'] == 1
    second = submit(owner, rejected['lineup'], code='#SECOND123').get_json()
    assert second['moderation']['state'] == 'pending'
    assert change(admin, second['lineup'], 'approve').status_code == 200


@pytest.mark.parametrize('action', ['approve', 'release'])
def test_restoring_previously_hidden_lineup_keeps_it_hidden(actors, action):
    owner, admin, _, guest = actors
    lineup = create_lineup(owner, status='hidden').get_json()
    banned = change(admin, lineup, 'ban').get_json()['lineup']
    if action == 'approve': banned = submit(owner, banned).get_json()['lineup']
    response = change(admin, banned, action).get_json()
    assert response['lineup']['status'] == 'hidden'
    assert guest.get(f"/api/lineups/{lineup['id']}").status_code == 404


def test_permissions_csrf_and_private_responses(actors):
    owner, admin, other, guest = actors
    lineup = create_lineup(owner).get_json()
    assert change(owner, lineup, 'ban').status_code == 403
    assert change(other, lineup, 'ban').status_code == 403
    assert change(guest, lineup, 'ban').status_code == 401
    assert admin.post(f"/api/admin/lineups/{lineup['id']}/moderation/ban", json={'reason': '测试', 'version': lineup['version']}).status_code == 403
    banned = change(admin, lineup, 'ban').get_json()['lineup']
    assert submit(other, banned).status_code == 404
    assert other.get(f"/api/lineups/{lineup['id']}/moderation").status_code == 404
    assert owner.get('/api/me/lineup-notifications').headers['Cache-Control'] == 'private, no-store'
    assert owner.get(f"/api/lineups/{lineup['id']}/moderation").headers['Cache-Control'] == 'private, no-store'
    assert guest.get('/api/admin/lineup-moderation-summary').status_code == 401


def test_stale_ban_double_submit_and_double_review_are_rejected(actors, app):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json()
    banned = change(admin, lineup, 'ban').get_json()['lineup']
    assert change(admin, lineup, 'ban').status_code == 409
    assert change(admin, lineup, 'release').status_code == 409
    submitted = submit(owner, banned).get_json()['lineup']
    assert submit(owner, banned).status_code == 409
    assert change(admin, submitted, 'release').status_code == 409
    assert change(admin, submitted, 'approve').status_code == 200
    assert change(admin, submitted, 'reject').status_code == 409
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) AS c FROM lineup_moderation_events').fetchone()['c'] == 3
        assert get_db().execute("SELECT COUNT(*) AS c FROM audit_logs WHERE action LIKE 'lineup_%'").fetchone()['c'] == 3


@pytest.mark.parametrize('bad_reason', ['', '   ', 'x' * 501, {}, 123])
def test_ban_requires_valid_reason(actors, bad_reason):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json()
    assert change(admin, lineup, 'ban', bad_reason).status_code == 400
    assert detail(owner, lineup)['moderation'] is None


@pytest.mark.parametrize('field,value', [('name',''), ('code','invalid'), ('season_id','unknown'), ('status','normal'), ('version','2')])
def test_submission_validation(actors, field, value):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json(); banned = change(admin, lineup, 'ban').get_json()['lineup']
    body = {'name': '修正', 'code': '#FIXED123', 'season_id': 's17-star-god', 'version': banned['version'], field: value}
    response = owner.post(f"/api/lineups/{lineup['id']}/revision", json=body, headers=auth_headers(owner))
    assert response.status_code in {400, 409}
    assert detail(owner, lineup)['moderation']['state'] == 'banned'


def test_filters_pagination_and_notification_ownership(actors):
    owner, admin, other, _ = actors
    first = create_lineup(owner).get_json()
    second = create_lineup(owner, name='第二条', code='#SECOND').get_json()
    change(admin, first, 'ban'); ban = change(admin, second, 'ban').get_json()
    submit(owner, ban['lineup'])
    assert admin.get('/api/admin/lineups?status=banned').get_json()['total'] == 1
    pending = admin.get('/api/admin/lineups?status=pending').get_json()
    assert pending['items'][0]['id'] == second['id']
    assert pending['counts'] == {'pending': 1, 'banned': 1}
    assert admin.get('/api/admin/lineup-moderation-summary').get_json() == {'pending': 1}
    assert admin.get('/api/admin/lineups?status=invalid').status_code == 400
    assert admin.get('/api/admin/lineups?season=s16-legends').get_json()['total'] == 0
    assert owner.get('/api/me/lineup-notifications?page_size=1&page=2').get_json()['page'] == 2
    assert other.get('/api/me/lineup-notifications').get_json()['items'] == []
    assert other.put(f"/api/me/lineup-notifications/{first['id']}", json={'status':'read','revision':1}, headers=auth_headers(other)).status_code == 409


def test_unknown_admin_status_and_invalid_score_are_rejected(actors):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json()
    for status in ('banned', 'deleted', 'arbitrary'):
        assert admin.put(f"/api/admin/lineups/{lineup['id']}", json={'status':status}, headers=auth_headers(admin)).status_code == 400
    assert admin.post(f"/api/admin/lineups/{lineup['id']}/adjust-score", json={'admin_like_adjustment':1.5}, headers=auth_headers(admin)).status_code == 400


def test_old_edit_racing_ban_cannot_overwrite_it(actors, app, monkeypatch):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json()
    import lineup_write_service
    original_validate = lineup_write_service.validate_lineup_payload
    def concurrent_change(*args, **kwargs):
        payload = original_validate(*args, **kwargs)
        # Model an update committed after the legacy route read its row.
        get_db().execute("UPDATE lineups SET status='banned', version=version+1 WHERE id=?", (lineup['id'],))
        get_db().commit()
        return payload
    monkeypatch.setattr(lineup_write_service, 'validate_lineup_payload', concurrent_change)
    response = owner.put(f"/api/lineups/{lineup['id']}", json={'name':'过期更新','code':'#STALE123'}, headers=auth_headers(owner))
    assert response.status_code == 409
    with app.app_context():
        row = get_db().execute('SELECT * FROM lineups WHERE id=?', (lineup['id'],)).fetchone()
        assert row['name'] == lineup['name'] and row['status'] == 'banned'


def test_owner_cannot_repost_restricted_code_or_put_it_on_another_lineup(actors):
    owner, admin, _, _ = actors
    first = create_lineup(owner).get_json()
    second = create_lineup(owner, code='#SEPARATE123').get_json()
    change(admin, first, 'ban')
    assert create_lineup(owner).status_code == 409
    response = owner.put(f"/api/lineups/{second['id']}", json={
        'name': '新名字', 'code': first['code'], 'season_id': second['season_id'],
    }, headers=auth_headers(owner))
    assert response.status_code == 409


def test_review_revalidates_season_when_visibility_changed(actors, monkeypatch):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json()
    banned = change(admin, lineup, 'ban').get_json()['lineup']
    submitted = submit(owner, banned).get_json()['lineup']
    import lineup_write_service
    monkeypatch.setattr(lineup_write_service, 'season_choice_map', lambda: {'s17-star-god': {}})
    response = change(admin, submitted, 'approve')
    assert response.status_code == 400
    assert detail(owner, lineup)['moderation']['state'] == 'pending'
    assert change(admin, submitted, 'reject').status_code == 200


def test_notice_toggle_preserves_review_version_and_owner_permissions(actors, app):
    owner, admin, other, _ = actors
    lineup = create_lineup(owner).get_json()
    banned = change(admin, lineup, 'ban').get_json()
    url = f"/api/me/lineup-notifications/{lineup['id']}"
    for state in ('read', 'unread', 'archived', 'read'):
        response = owner.put(url, json={'status': state, 'revision': banned['moderation']['revision']}, headers=auth_headers(owner))
        assert response.status_code == 200
        assert detail(owner, lineup)['lineup']['version'] == banned['lineup']['version']
    with app.app_context():
        get_db().execute("UPDATE users SET status='disabled' WHERE username='alice'")
        get_db().commit()
    assert owner.get('/api/me/lineup-notifications').status_code == 403


def test_failed_audit_rolls_back_ban_and_notification(actors, app, monkeypatch):
    owner, admin, _, _ = actors
    lineup = create_lineup(owner).get_json()
    import lineup_moderation_service
    def fail(*args, **kwargs):
        raise RuntimeError('simulated audit write failure')
    monkeypatch.setattr(lineup_moderation_service, 'write_audit', fail)
    with pytest.raises(RuntimeError, match='simulated audit'):
        change(admin, lineup, 'ban')
    record = detail(owner, lineup)
    assert record['lineup']['status'] == 'normal'
    assert record['moderation'] is None and record['events'] == []
