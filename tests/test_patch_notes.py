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


def test_parse_summary_markdown_splits_subject_and_value_rows():
    item = parse_summary_markdown('- [buff] 阿兹尔：沙兵持续时间 4秒 => 5秒；法力值 30/90 => 30/80')[0]

    assert item['subject'] == '阿兹尔'
    assert item['changes'] == [
        {'attribute': '沙兵持续时间', 'from': '4秒', 'to': '5秒', 'note': ''},
        {'attribute': '法力值', 'from': '30/90', 'to': '30/80', 'note': ''},
    ]
    assert item['old_value'] == '阿兹尔：沙兵持续时间 4秒'

    described = parse_summary_markdown('- [adjust] 法官：机制重做')[0]
    assert described['subject'] == '法官'
    assert described['detail'] == '机制重做'
    assert described['changes'] == []


def test_group_summary_items_builds_sections_with_counts():
    from patch_note_service import group_summary_items, summarize_patch_note

    items = parse_summary_markdown(
        '本次更新说明。\n'
        '## 英雄调整\n'
        '- [buff] 亚托克斯：治疗 300 => 325\n'
        '- [nerf] 菲奥娜：真实伤害 40 => 37\n'
        '## 装备\n'
        '- [nerf] 汲取剑：全能吸血 20% => 18%\n'
    )
    sections = group_summary_items(items)

    assert [section['title'] for section in sections] == ['', '英雄调整', '装备']
    assert [section['id'] for section in sections] == ['section-1', 'section-2', 'section-3']
    assert sections[1]['counts'] == {'buff': 1, 'nerf': 1, 'adjust': 0}
    overview = summarize_patch_note(items)
    assert overview['counts'] == {'buff': 1, 'nerf': 2, 'adjust': 0}
    assert overview['excerpt'] == '本次更新说明。'
    assert overview['section_titles'] == ['英雄调整', '装备']
    assert [item['subject'] for item in overview['highlights']] == ['亚托克斯', '菲奥娜', '汲取剑']



def test_adjacent_public_patch_notes_skips_drafts(client):
    from patch_note_service import adjacent_public_patch_notes

    headers = login_admin(client)
    ids = []
    for title, date, status in [('旧公告', '2026-05-01', 'published'), ('草稿', '2026-05-10', 'draft'), ('新公告', '2026-05-20', 'published')]:
        ids.append(client.post('/api/admin/patch-notes', json={
            'title': title, 'summary_markdown': '- [adjust] 内容', 'status': status, 'published_at': date,
        }, headers=headers).get_json()['id'])

    with client.application.app_context():
        older_view = adjacent_public_patch_notes(ids[0])
        newer_view = adjacent_public_patch_notes(ids[2])
    assert older_view['newer']['title'] == '新公告' and older_view['older'] is None
    assert newer_view['older']['title'] == '旧公告' and newer_view['newer'] is None


def test_public_patch_note_pages_render_published_content_server_side(client):
    headers = login_admin(client)
    created = create_published_patch_note(client, headers).get_json()
    client.post('/api/admin/patch-notes', json={
        'title': '草稿公告',
        'summary_markdown': '- [adjust] 草稿',
        'status': 'draft',
        'published_at': '2026-05-29',
    }, headers=headers)

    listing = client.get('/patch-notes').get_data(as_text=True)
    assert '17.4更新公告' in listing
    assert f'/patch-notes/{created["id"]}' in listing
    assert '草稿公告' not in listing

    detail = client.get(f'/patch-notes/{created["id"]}').get_data(as_text=True)
    assert '亚托克斯' in detail
    assert 'https://example.com/jcc/174' in detail
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in detail
    assert '<script>alert(1)</script>' not in detail


def test_public_patch_notes_page_renders_empty_state(client):
    html = client.get('/patch-notes').get_data(as_text=True)

    assert '暂无更新公告' in html
    assert 'patch-notes.css' in html
