from lineups_serialization import serialize_lineup_row


class FakeDb:
    def execute(self, sql, params):
        raise AssertionError('owner/interaction query should not be needed when row includes joined fields')


def test_serialize_lineup_row_uses_joined_owner_and_flags():
    row = {
        'id': 10,
        'name': '测试阵容',
        'code': '#CODE',
        'season_id': 's17-star-god',
        'created_at': '2026-05-24 10:00:00',
        'updated_at': '2026-05-24 10:00:00',
        'version': 1,
        'status': 'normal',
        'user_id': 3,
        'admin_like_adjustment': 2,
        'admin_copy_adjustment': 1,
        'owner_role': 'user',
        'owner_username': 'alice',
        'owner_nickname_raw': 'Alice',
        'is_liked_today': 1,
        'is_favorited': 0,
    }
    scores = {10: {'rank_level': 'A', 'like_count': 8, 'copy_count': 5, 'score': 88}}

    data = serialize_lineup_row(row, scores, user={'id': 3, 'role': 'user'}, db=FakeDb())

    assert data['owner_nickname'] == 'Alice'
    assert data['owner_username'] == 'alice'
    assert data['rank_level'] == 'A'
    assert data['is_liked_today'] is True
    assert data['is_favorited'] is False
    assert data['can_edit'] is True
    assert data['can_hide'] is True
