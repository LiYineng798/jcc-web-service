import recommendation
from live_comps_helpers import read_live_comps_payload_for_season


def test_recommended_scores_reads_cache_even_with_supplied_scores(app, monkeypatch):
    sentinel = {'cached': True}
    monkeypatch.setattr(recommendation, 'get_recommended_cache', lambda key: sentinel)
    with app.app_context():
        assert recommendation.recommended_scores(scores={}) is sentinel


def test_live_comps_payload_cache_reuses_parsed_payload(app):
    with app.app_context():
        first, *_ = read_live_comps_payload_for_season()
        second, *_ = read_live_comps_payload_for_season()
        assert first is second


def test_sitemap_is_cached_with_public_cache_header(client):
    response = client.get('/sitemap.xml')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'public, max-age=3600'


def test_homepage_assets_are_versioned(client):
    html = client.get('/').get_data(as_text=True)
    assert 'fonts.googleapis' not in html
    assert '/static/styles.css?v=' in html
    assert '/static/app.js?v=' in html


def test_season_page_assets_carry_version(client):
    html = client.get('/tools/seasons/s18').get_data(as_text=True)
    assert 'data-version=' in html
    detail_html = client.get('/tools/s18-preview', follow_redirects=True).get_data(as_text=True)
    assert 'data-version=' in detail_html
