import io
import json

from live_comps_helpers import season_data_path
from live_comp_upload_service import get_upload_job, start_upload_job


def login_admin(client):
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    return {'X-CSRF-Token': client.get('/api/me').get_json()['csrf_token']}


def payload(item_id='new-1', code='#NEW001'):
    return {
        'meta': {'source': 'admin-test'},
        'tiers': {
            'S': [{
                'id': item_id,
                'title': '测试阵容',
                'tier': 'S',
                'jccCode': code,
                'mainAvatar': '/api/live-comps/assets/avatar.png',
                'heroImages': ['/api/live-comps/assets/hero.png'],
            }],
            'A': [], 'B': [], 'C': [], 'D': [],
        },
    }


def test_admin_live_comp_upload_preview_requires_admin_and_csrf(client):
    raw = json.dumps(payload()).encode('utf-8')
    response = client.post(
        '/api/admin/live-comps/uploads/preview',
        data={'season_id': 's17-star-god', 'file': (io.BytesIO(raw), 'upload.json')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 401

    login_admin(client)
    response = client.post(
        '/api/admin/live-comps/uploads/preview',
        data={'season_id': 's17-star-god', 'file': (io.BytesIO(raw), 'upload.json')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 403


def test_admin_live_comp_upload_preview_returns_diff_and_start_is_idempotent(client, app, tmp_path):
    app.config.update(
        LIVE_COMPS_BACKUP_DIR=str(tmp_path / 'backups'),
        LIVE_COMPS_UPLOAD_JOB_DIR=str(tmp_path / 'jobs'),
    )
    with app.app_context():
        path = season_data_path('s17-star-god')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload('old-1', '#OLD001'), ensure_ascii=False), encoding='utf-8')

    headers = login_admin(client)
    raw = json.dumps(payload('new-1', '#NEW001')).encode('utf-8')
    response = client.post(
        '/api/admin/live-comps/uploads/preview',
        data={'season_id': 's17-star-god', 'file': (io.BytesIO(raw), 'upload.json')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert response.status_code == 201
    job = response.get_json()
    assert job['status'] == 'preview'
    assert job['preview']['added_ids'] == ['new-1']
    assert job['preview']['removed_ids'] == ['old-1']
    assert job['preview']['code_changed_ids'] == []

    started = client.post(f"/api/admin/live-comps/uploads/{job['job_id']}/start", headers=headers)
    assert started.status_code == 200
    assert started.get_json()['status'] == 'queued'
    duplicate = client.post(f"/api/admin/live-comps/uploads/{job['job_id']}/start", headers=headers)
    assert duplicate.status_code == 409


def test_start_unknown_live_comp_upload_returns_404(client):
    headers = login_admin(client)
    response = client.post('/api/admin/live-comps/uploads/missing/start', headers=headers)
    assert response.status_code == 404
