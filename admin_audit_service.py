from admin_pagination import paginate_rows


def list_admin_audit_logs(db, page, page_size):
    # The workspace renders action/target/created_at only — leave the
    # before_json/after_json blobs (which can hold full documents) on disk.
    base_sql = (
        'SELECT id, actor_user_id, action, target_type, target_id, created_at '
        'FROM audit_logs ORDER BY id DESC'
    )
    count_sql = 'SELECT COUNT(*) AS c FROM audit_logs'
    return paginate_rows(db, base_sql, count_sql, [], page, page_size, serializer=dict)
