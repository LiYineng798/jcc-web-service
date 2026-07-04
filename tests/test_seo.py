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
