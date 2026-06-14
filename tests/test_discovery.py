from datetime import datetime, timedelta

from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_rising_sort_prioritizes_recently_accelerating_lineups(client):
    register_user(client, username='owner', email='owner@example.com')
    rising = create_lineup(client, name='上升阵容', code='#RISING001').get_json()
    stable = create_lineup(client, name='稳定阵容', code='#RISING002').get_json()
    now = datetime.now().replace(second=0, microsecond=0)
    recent_time = now - timedelta(hours=1)
    previous_time = now - timedelta(hours=25)

    with client.application.app_context():
        from db import get_db

        db = get_db()
        db.execute(
            'INSERT INTO likes (user_id, lineup_id, like_date, created_at) VALUES (?, ?, ?, ?)',
            (1, rising['id'], recent_time.strftime('%Y-%m-%d'), recent_time.strftime('%Y-%m-%d %H:%M:%S')),
        )
        db.execute(
            'INSERT INTO copy_events (lineup_id, user_id, ip_address, copy_key, bucket_start, counted, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)',
            (
                rising['id'],
                1,
                '1.1.1.1',
                'user:1-growth',
                recent_time.strftime('%Y-%m-%d %H:%M:%S'),
                recent_time.strftime('%Y-%m-%d %H:%M:%S'),
            ),
        )
        db.execute(
            'INSERT INTO likes (user_id, lineup_id, like_date, created_at) VALUES (?, ?, ?, ?)',
            (1, stable['id'], previous_time.strftime('%Y-%m-%d'), previous_time.strftime('%Y-%m-%d %H:%M:%S')),
        )
        db.commit()

    payload = client.get('/api/lineups?sort=rising&page=1&page_size=10').get_json()
    assert payload['items'][0]['id'] == rising['id']


def test_anonymous_recommended_sort_returns_items(client):
    register_user(client, username='owner', email='owner@example.com')
    create_lineup(client, name='推荐阵容A', code='#REC001')
    create_lineup(client, name='推荐阵容B', code='#REC002')

    payload = client.get('/api/lineups?sort=recommended&page=1&page_size=10').get_json()
    assert payload['total'] == 2
    assert len(payload['items']) == 2


def test_logged_in_recommended_sort_deprioritizes_own_lineups(client):
    register_user(client, username='owner', email='owner@example.com')
    create_lineup(client, name='别人的阵容', code='#REC003')
    client.post('/api/logout')
    register_user(client, username='other', email='other@example.com')
    own = create_lineup(client, name='自己的阵容', code='#REC004').get_json()

    payload = client.get('/api/lineups?sort=recommended&page=1&page_size=10').get_json()
    assert payload['items'][0]['id'] != own['id']


def test_recommended_scores_reuses_supplied_scores_without_recomputing(client, monkeypatch):
    assert register_user(client, username='rec_cache_owner', email='rec_cache_owner@example.com').status_code == 201
    response = create_lineup(client, name='推荐缓存阵容', code='#RECCACHE')
    assert response.status_code == 201
    lineup = response.get_json()

    import recommendation

    def fail_score_map():
        raise AssertionError('score_map should not be called when scores are supplied')

    monkeypatch.setattr(recommendation, 'score_map', fail_score_map)

    with client.application.app_context():
        result = recommendation.recommended_scores(scores={lineup['id']: {'score': 7}})

    assert result[lineup['id']] == 19
