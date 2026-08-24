from audit import write_audit
from db import get_db


def login_admin(client):
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    return {'X-CSRF-Token': client.get('/api/me').get_json()['csrf_token']}


def test_audit_supports_non_numeric_target_key_without_target_id(client):
    with client.application.app_context():
        write_audit(
            1,
            'text_target_action',
            'season',
            target_key='s18-enchanted-wilds',
            after={'status': 'archived'},
        )
        get_db().commit()
        row = get_db().execute(
            "SELECT target_id, target_key FROM audit_logs WHERE action = 'text_target_action'"
        ).fetchone()

    assert row['target_id'] is None
    assert row['target_key'] == 's18-enchanted-wilds'


def test_live_comp_season_update_uses_text_audit_key(client):
    headers = login_admin(client)
    response = client.put(
        '/api/admin/live-comps/seasons/s17-star-god',
        json={'description': '审计字段回归测试'},
        headers=headers,
    )

    assert response.status_code == 200
    with client.application.app_context():
        row = get_db().execute(
            """
            SELECT target_id, target_key
            FROM audit_logs
            WHERE action = 'update_live_comps_season'
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    assert row['target_id'] is None
    assert row['target_key'] == 's17-star-god'
