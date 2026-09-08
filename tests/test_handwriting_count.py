def test_homepage_handwriting_assets_load_before_app(client):
    html = client.get('/').get_data(as_text=True)
    assert 'handwriting-count.css?v=' in html
    assert html.index('handwriting-digits.js?v=') < html.index('handwriting-count.js?v=') < html.index('app.js?v=')
    for asset in ('handwriting-count.css', 'handwriting-count.js', 'handwriting-digits.js',
                  'fonts/handwriting/ShadowsIntoLight.ttf', 'fonts/handwriting/OFL.txt'):
        response = client.get('/static/' + asset)
        assert response.status_code == 200
        assert response.data
