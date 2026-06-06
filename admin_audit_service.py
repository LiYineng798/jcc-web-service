from admin_pagination import paginate_rows


def list_admin_audit_logs(db, page, page_size):
    base_sql = 'SELECT * FROM audit_logs ORDER BY id DESC'
    count_sql = 'SELECT COUNT(*) AS c FROM audit_logs'
    return paginate_rows(db, base_sql, count_sql, [], page, page_size, serializer=dict)
