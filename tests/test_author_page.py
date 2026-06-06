from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_author_page_exists_and_uses_username_route(client):
    register_user(client, username='author1', email='author1@example.com', nickname='作者一号')
    create_lineup(client, name='作者阵容', code='#AUTHOR001')

    response = client.get('/author/author1')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="authorApp"' in html
    assert 'author.js' in html
    assert 'authPromptRoot' in html
    assert 'history-store.js' in html
    assert 'auth-intent.js' in html


def test_author_api_returns_profile_and_public_lineups(client):
    register_user(client, username='author2', email='author2@example.com', nickname='作者二号')
    create_lineup(client, name='阵容A', code='#AUTHOR002')
    create_lineup(client, name='阵容B', code='#AUTHOR003')

    payload = client.get('/api/authors/author2').get_json()
    assert payload['profile']['username'] == 'author2'
    assert payload['profile']['nickname'] == '作者二号'
    assert payload['summary']['published_lineups'] == 2
    assert len(payload['lineups']) == 2


def test_author_api_hides_hidden_lineups(client):
    register_user(client, username='author3', email='author3@example.com', nickname='作者三号')
    visible = create_lineup(client, name='公开阵容', code='#AUTHOR004').get_json()
    hidden = create_lineup(client, name='隐藏阵容', code='#AUTHOR005', status='hidden').get_json()

    payload = client.get('/api/authors/author3').get_json()
    lineup_ids = [item['id'] for item in payload['lineups']]
    assert visible['id'] in lineup_ids
    assert hidden['id'] not in lineup_ids
    assert payload['summary']['published_lineups'] == 1
