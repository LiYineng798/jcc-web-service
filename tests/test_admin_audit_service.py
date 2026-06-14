from admin_audit_service import list_admin_audit_logs
from audit import write_audit
from db import get_db


def test_list_admin_audit_logs_returns_paginated_rows(client):
    with client.application.app_context():
        write_audit(1, 'first_action', 'user', '1')
        write_audit(1, 'second_action', 'user', '2')
        get_db().commit()
        payload = list_admin_audit_logs(get_db(), page=1, page_size=10)

    assert payload['page'] == 1
    assert payload['page_size'] == 10
    assert payload['total'] == 2
    assert payload['total_pages'] == 1
    assert payload['items'][0]['action'] == 'second_action'
    assert payload['items'][1]['action'] == 'first_action'
