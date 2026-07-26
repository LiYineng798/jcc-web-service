from seo import code_preview, make_seo, season_label, truncate_text


def test_make_seo_builds_canonical_and_social_fields(app):
    with app.test_request_context('/lineup/12?sort=hot', base_url='https://jcc.example'):
        seo = make_seo(
            title='测试阵容 - 金铲铲阵容库',
            description='测试阵容描述',
            path='/lineup/12',
        )

    assert seo['title'] == '测试阵容 - 金铲铲阵容库'
    assert seo['description'] == '测试阵容描述'
    assert seo['canonical_url'] == 'https://jcc.example/lineup/12'
    assert seo['og_type'] == 'website'
    assert seo['robots'] == 'index, follow'
    assert seo['json_ld'] == []


def test_make_seo_supports_noindex(app):
    with app.test_request_context('/admin', base_url='https://jcc.example'):
        seo = make_seo(title='后台', description='后台页面', noindex=True)

    assert seo['canonical_url'] == 'https://jcc.example/admin'
    assert seo['robots'] == 'noindex, nofollow'


def test_truncate_text_is_plain_and_length_limited():
    assert truncate_text('  abc\ndefghi  ', 8) == 'abc d...'
    assert truncate_text('', 8) == ''


def test_code_preview_masks_long_lineup_codes():
    assert code_preview('#ABC123') == '#ABC123'
    assert code_preview('#1234567890ABCDEFG') == '#1234567890...'


def test_season_label_uses_catalog_name():
    assert season_label('s17-star-god') == 'S17 · 星神'
    assert season_label('unknown-season') == 'unknown-season'


def test_robots_txt_lists_disallowed_private_surfaces_and_sitemap(client):
    response = client.get('/robots.txt')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == 'text/plain'
    assert 'User-agent: *' in body
    assert 'Allow: /' in body
    assert 'Disallow: /api/' in body
    assert 'Disallow: /admin' in body
    assert 'Disallow: /auth' in body
    assert 'Disallow: /me' in body
    assert 'Disallow: /lineup/new' in body
    assert 'Sitemap: http://localhost/sitemap.xml' in body


def test_sitemap_includes_public_urls_and_excludes_hidden_and_draft(client):
    from test_admin import login_admin
    from test_auth import register_user
    from test_lineup_permissions import create_lineup

    register_user(client, username='mapauthor', email='mapauthor@example.com', nickname='地图作者')
    public_lineup = create_lineup(client, name='地图公开阵容', code='#MAPSEO1').get_json()
    hidden_lineup = create_lineup(client, name='地图隐藏阵容', code='#MAPSEO2', status='hidden').get_json()
    client.post('/api/logout')
    headers = login_admin(client)
    published_note = client.post('/api/admin/patch-notes', json={
        'title': '地图公告',
        'version': 'M1',
        'source_url': '',
        'summary_markdown': '地图公告内容',
        'original_text': '',
        'status': 'published',
        'published_at': '2026-07-04',
    }, headers=headers).get_json()
    draft_note = client.post('/api/admin/patch-notes', json={
        'title': '地图草稿',
        'version': 'M2',
        'source_url': '',
        'summary_markdown': '地图草稿内容',
        'original_text': '',
        'status': 'draft',
        'published_at': '2026-07-04',
    }, headers=headers).get_json()

    response = client.get('/sitemap.xml')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype in {'application/xml', 'text/xml'}
    assert '<loc>http://localhost/</loc>' in body
    assert '<loc>http://localhost/tools/seasons/s18</loc>' in body
    assert '<loc>http://localhost/tools/seasons/s18/champions/' in body
    assert f'<loc>http://localhost/lineup/{public_lineup["id"]}</loc>' in body
    assert f'<loc>http://localhost/lineup/{hidden_lineup["id"]}</loc>' not in body
    assert '<loc>http://localhost/author/mapauthor</loc>' in body
    assert f'<loc>http://localhost/patch-notes/{published_note["id"]}</loc>' in body
    assert f'<loc>http://localhost/patch-notes/{draft_note["id"]}</loc>' not in body
    assert '<loc>http://localhost/admin</loc>' not in body
    assert '<loc>http://localhost/api/' not in body
