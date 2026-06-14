from patch_note_service import parse_summary_markdown, validate_patch_note_payload
from test_admin import login_admin


def test_parse_summary_markdown_recognizes_sections_and_change_types():
    parsed = parse_summary_markdown(
        '## 英雄调整\n\n'
        '- [buff] 亚托克斯：治疗 300 => 325\n'
        '- [nerf] 菲奥娜：真实伤害 40 => 37\n'
        '- [adjust] 法官：机制重做\n'
    )

    assert parsed[0] == {'type': 'section', 'title': '英雄调整'}
    assert parsed[1]['kind'] == 'buff'
    assert parsed[1]['label'] == '加强'
    assert parsed[1]['old_value'] == '亚托克斯：治疗 300'
    assert parsed[1]['new_value'] == '325'
    assert parsed[2]['kind'] == 'nerf'
    assert parsed[2]['label'] == '削弱'
    assert parsed[3]['kind'] == 'adjust'
    assert parsed[3]['text'] == '法官：机制重做'


def test_validate_patch_note_payload_rejects_invalid_status_and_source_url():
    payload, error = validate_patch_note_payload({
        'title': '17.4更新公告',
        'published_at': '2026-05-28',
        'summary_markdown': '- [buff] 亚托克斯：治疗 300 => 325',
        'status': 'online',
        'source_url': 'javascript:alert(1)',
    })

    assert payload is None
    assert error == '状态无效'


def test_validate_patch_note_payload_accepts_minimal_payload():
    payload, error = validate_patch_note_payload({
        'title': '17.4更新公告',
        'published_at': '2026-05-28',
        'summary_markdown': '- [buff] 亚托克斯：治疗 300 => 325',
        'status': 'published',
        'source_url': 'https://example.com/notice',
    })

    assert error is None
    assert payload['title'] == '17.4更新公告'
    assert payload['version'] == ''
    assert payload['status'] == 'published'


def create_published_patch_note(client, headers):
    response = client.post('/api/admin/patch-notes', json={
        'title': '17.4更新公告',
        'version': '17.4',
        'source_url': 'https://example.com/jcc/174',
        'summary_markdown': '## 英雄调整\n- [buff] 亚托克斯：治疗 300 => 325',
        'original_text': '<script>alert(1)</script>\n原文正文',
        'status': 'published',
        'published_at': '2026-05-28',
    }, headers=headers)
    return response


def test_public_patch_notes_only_lists_published(client):
    headers = login_admin(client)
    published = create_published_patch_note(client, headers)
    assert published.status_code == 201
    draft = client.post('/api/admin/patch-notes', json={
        'title': '草稿公告',
        'summary_markdown': '- [adjust] 草稿',
        'status': 'draft',
        'published_at': '2026-05-29',
    }, headers=headers)
    assert draft.status_code == 201

    payload = client.get('/api/patch-notes').get_json()
    assert [item['title'] for item in payload['items']] == ['17.4更新公告']


def test_public_patch_note_detail_includes_summary_items_and_plain_original(client):
    headers = login_admin(client)
    created = create_published_patch_note(client, headers).get_json()

    payload = client.get(f"/api/patch-notes/{created['id']}").get_json()

    assert payload['title'] == '17.4更新公告'
    assert payload['summary_items'][1]['kind'] == 'buff'
    assert payload['original_text'] == '<script>alert(1)</script>\n原文正文'


def test_public_patch_note_detail_hides_drafts(client):
    headers = login_admin(client)
    created = client.post('/api/admin/patch-notes', json={
        'title': '草稿公告',
        'summary_markdown': '- [adjust] 草稿',
        'status': 'draft',
        'published_at': '2026-05-29',
    }, headers=headers).get_json()

    assert client.get(f"/api/patch-notes/{created['id']}").status_code == 404
