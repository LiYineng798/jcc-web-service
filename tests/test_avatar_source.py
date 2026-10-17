def test_avatar_source_page_is_public_and_not_indexed(client):
    response = client.get('/avatar-source')
    assert response.status_code == 200
    assert response.headers['X-Robots-Tag'] == 'noindex'
    assert b'AGPL' in response.data
    assert b'avatar-lab/THIRD_PARTY_NOTICES.txt' in response.data


def test_avatar_source_download_uses_fixed_filename(client):
    response = client.get('/avatar-source/download')
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert 'attachment' in response.headers['Content-Disposition']
        assert response.data.startswith(b'PK')
    assert client.get('/avatar-source/download/../../config.py').status_code == 404
