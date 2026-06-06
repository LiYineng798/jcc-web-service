from test_admin import login_admin
from test_auth import register_user


def patch_note_payload(**overrides):
    payload = {
        'title': '17.4更新公告',
        'version': '17.4',
        'source_url': 'https://example.com/jcc/174',
        'summary_markdown': '## 英雄调整\n- [buff] 亚托克斯：治疗 300 => 325',
        'original_text': '官方原文',
        'status': 'draft',
        'published_at': '2026-05-28',
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_update_publish_and_hide_patch_note(client):
    headers = login_admin(client)
    created = client.post('/api/admin/patch-notes', json=patch_note_payload(), headers=headers)
    assert created.status_code == 201
    patch_note_id = created.get_json()['id']

    updated = client.put(
        f'/api/admin/patch-notes/{patch_note_id}',
        json=patch_note_payload(status='published', title='17.4正式更新公告'),
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.get_json()['status'] == 'published'
    assert updated.get_json()['title'] == '17.4正式更新公告'

    listed = client.get('/api/admin/patch-notes', headers=headers).get_json()
    assert listed['items'][0]['id'] == patch_note_id

    hidden = client.delete(f'/api/admin/patch-notes/{patch_note_id}', headers=headers)
    assert hidden.status_code == 200
    assert hidden.get_json()['status'] == 'hidden'


def test_admin_patch_note_validation_errors(client):
    headers = login_admin(client)
    response = client.post('/api/admin/patch-notes', json=patch_note_payload(title=''), headers=headers)
    assert response.status_code == 400
    assert response.get_json()['error'] == '标题不能为空'

    response = client.post('/api/admin/patch-notes', json=patch_note_payload(source_url='javascript:alert(1)'), headers=headers)
    assert response.status_code == 400
    assert response.get_json()['error'] == '来源链接无效'


def test_non_admin_cannot_manage_patch_notes(client):
    assert client.get('/api/admin/patch-notes').status_code == 401
    register_user(client, username='normal', email='normal@example.com')
    assert client.get('/api/admin/patch-notes').status_code == 403
    response = client.post('/api/admin/patch-notes', json=patch_note_payload())
    assert response.status_code == 403
