from lineup_interaction_service import (
    copy_lineup_record,
    favorite_lineup_record,
    like_lineup_record,
    report_lineup_record,
    unfavorite_lineup_record,
)
from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_like_lineup_record_rejects_duplicate_like_same_day(client):
    register_user(client)
    user = client.get('/api/me').get_json()['user']
    lineup = create_lineup(client).get_json()

    with client.application.app_context():
        payload, error, status_code = like_lineup_record(user=user, lineup_id=lineup['id'])
        payload_2, error_2, status_code_2 = like_lineup_record(user=user, lineup_id=lineup['id'])

    assert error is None
    assert status_code == 201
    assert payload['lineup']['like_count'] == 1
    assert payload_2 is None
    assert status_code_2 == 409
    assert error_2 == '今天已经点赞过该阵容'


def test_copy_lineup_record_counts_once_per_bucket_for_same_user(client):
    register_user(client)
    user = client.get('/api/me').get_json()['user']
    lineup = create_lineup(client).get_json()

    with client.application.app_context():
        first, first_error, first_status = copy_lineup_record(user=user, lineup_id=lineup['id'], ip='1.2.3.4')
        second, second_error, second_status = copy_lineup_record(user=user, lineup_id=lineup['id'], ip='1.2.3.4')

    assert first_error is None
    assert first_status == 200
    assert first['counted'] is True
    assert second_error is None
    assert second_status == 200
    assert second['counted'] is False


def test_favorite_and_unfavorite_lineup_record_toggle_favorite(client):
    register_user(client)
    user = client.get('/api/me').get_json()['user']
    lineup = create_lineup(client).get_json()

    with client.application.app_context():
        payload, error, status_code = favorite_lineup_record(user=user, lineup_id=lineup['id'])
        unfav_payload, unfav_error, unfav_status = unfavorite_lineup_record(user=user, lineup_id=lineup['id'])

    assert error is None
    assert status_code == 200
    assert payload == {'ok': True, 'created': True}
    assert unfav_error is None
    assert unfav_status == 200
    assert unfav_payload == {'ok': True}


def test_report_lineup_record_creates_pending_report(client):
    register_user(client)
    user = client.get('/api/me').get_json()['user']
    lineup = create_lineup(client).get_json()

    with client.application.app_context():
        payload, error, status_code = report_lineup_record(user=user, lineup_id=lineup['id'], reason='无效阵容')

    assert error is None
    assert status_code == 201
    assert payload['status'] == 'pending'
