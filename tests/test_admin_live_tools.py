import time

from test_admin import login_admin
from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup
from test_live_comps import sample_live_comps_payload, write_live_comps_seed


def test_admin_can_create_live_comps_season(client):
    headers = login_admin(client)
    response = client.post('/api/admin/live-comps/seasons', json={
        'id': 's19-new-season',
        'name': 'S19 · 新赛季',
        'description': '测试新增',
        'status': 'hidden',
    }, headers=headers)
    assert response.status_code == 200
    manifest = response.get_json()
    created = next(season for season in manifest['seasons'] if season['id'] == 's19-new-season')
    assert created['name'] == 'S19 · 新赛季'
    assert created['status'] == 'hidden'
    assert created['data_file'] == 's19-new-season.json'
    assert created['order'] == max(int(season['order']) for season in manifest['seasons'])

    # 再次读取仍存在（写入了 manifest 文件）
    listed = client.get('/api/admin/live-comps/seasons', headers=headers).get_json()
    assert any(season['id'] == 's19-new-season' for season in listed['seasons'])

    # hidden 状态不出现在公开赛季接口
    public = client.get('/api/live-comps/seasons').get_json()
    assert all(season['id'] != 's19-new-season' for season in public['seasons'])

    # 启用后出现在公开赛季接口
    client.put('/api/admin/live-comps/seasons/s19-new-season', json={'status': 'active'}, headers=headers)
    public = client.get('/api/live-comps/seasons').get_json()
    assert any(season['id'] == 's19-new-season' for season in public['seasons'])


def test_create_live_comps_season_validation(client):
    headers = login_admin(client)

    def attempt(payload):
        return client.post('/api/admin/live-comps/seasons', json=payload, headers=headers)

    assert attempt({'id': 'Bad ID', 'name': 'x'}).status_code == 400
    assert attempt({'id': 's', 'name': 'x'}).status_code == 400
    assert attempt({'id': 's19-ok', 'name': ''}).status_code == 400
    assert attempt({'id': 's19-ok', 'name': 'x', 'status': 'nope'}).status_code == 400
    assert attempt({'id': 'default', 'name': '别名冲突'}).status_code == 400
    assert attempt({'id': 's17-star-god', 'name': '重复'}).status_code == 400
    assert attempt({'id': 's19-ok', 'name': '正常'}).status_code == 200
    assert attempt({'id': 's19-ok', 'name': '再次重复'}).status_code == 400


def test_create_live_comps_season_requires_admin(client):
    register_user(client)
    headers = auth_headers(client)
    assert client.post('/api/admin/live-comps/seasons', json={'id': 's19-x', 'name': 'x'}, headers=headers).status_code == 403


def test_admin_can_touch_live_comps_season_updated_at(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    headers = login_admin(client)

    before = client.get('/api/live-comps/summary?season=s17-star-god').get_json()['updated_at']
    time.sleep(1.1)
    response = client.post('/api/admin/live-comps/seasons/s17-star-god/touch-updated-at', headers=headers)
    assert response.status_code == 200
    touched = response.get_json()
    assert touched['season_id'] == 's17-star-god'
    assert touched['updated_at'] > before

    after = client.get('/api/live-comps/summary?season=s17-star-god').get_json()['updated_at']
    assert after == touched['updated_at']


def test_touch_live_comps_season_errors(client):
    headers = login_admin(client)
    assert client.post('/api/admin/live-comps/seasons/no-such-season/touch-updated-at', headers=headers).status_code == 404
    # 存在但没有数据文件的赛季
    assert client.post('/api/admin/live-comps/seasons/s16-legends/touch-updated-at', headers=headers).status_code == 400


def test_admin_copy_rank_ranks_lineups_and_live_comps(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    register_user(client, username='ranker', email='ranker@example.com')
    lineup = create_lineup(client, name='排行阵容', code='#RANK001').get_json()
    headers = auth_headers(client)
    client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers)
    live_id = sample_live_comps_payload()['tiers']['S'][0]['id']
    assert client.post(f'/api/live-comps/{live_id}/copy', headers=headers).status_code == 200
    client.post('/api/logout')

    headers = login_admin(client)
    data = client.get('/api/admin/copy-rank', headers=headers).get_json()
    assert data['items']
    top = data['items'][0]
    assert top['rank'] == 1
    assert top['target_type'] == 'lineup'
    assert top['title'] == '排行阵容'
    assert top['lineup_id'] == lineup['id']
    assert top['copies'] == 2
    assert top['unique_visitors'] == 1
    assert top['details']
    assert top['details'][0]['actor'] == 'ranker'
    assert top['details'][0]['uploader'] == 'ranker'
    assert top['details'][0]['code'] == '#RANK001'

    live_rows = [item for item in data['items'] if item['target_type'] == 'live_comp']
    assert live_rows and live_rows[0]['target_id'] == str(live_id)
    assert live_rows[0]['title']
    assert live_rows[0]['copies'] == 1


def test_admin_copy_rank_requires_admin_and_handles_empty_day(client):
    assert client.get('/api/admin/copy-rank').status_code == 401
    headers = login_admin(client)
    data = client.get('/api/admin/copy-rank?date=2000-01-01', headers=headers).get_json()
    assert data['date'] == '2000-01-01'
    assert data['items'] == []
