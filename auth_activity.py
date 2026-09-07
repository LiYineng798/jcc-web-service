"""Count authenticated daily users without treating session restores as logins."""


def authenticated_active_users(db, target_date):
    from analytics import _day_bounds

    return int(db.execute(
        '''
        SELECT COUNT(DISTINCT activity.user_id) AS c
        FROM (
            SELECT user_id FROM visit_events WHERE visit_date = ? AND user_id IS NOT NULL
            UNION
            SELECT user_id FROM login_events
            WHERE success = 1 AND created_at >= ? AND created_at < ?
        ) activity
        JOIN users u ON u.id = activity.user_id
        WHERE u.role != 'admin'
        ''',
        (target_date, *_day_bounds(target_date)),
    ).fetchone()['c'])
