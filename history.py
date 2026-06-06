from db import get_db, now_text
from scoring import score_map
from lineups_serialization import serialize_lineup_row


def _upsert_history(table_name, user_id, lineup_id, created_at=None):
    timestamp = created_at or now_text()
    get_db().execute(
        f'''
        INSERT INTO {table_name} (user_id, lineup_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, lineup_id) DO UPDATE SET
            updated_at = excluded.updated_at
        ''',
        (user_id, lineup_id, timestamp, timestamp),
    )
    get_db().commit()


def record_recent_view(user_id, lineup_id, created_at=None):
    _upsert_history('recent_lineup_views', user_id, lineup_id, created_at=created_at)


def record_recent_copy(user_id, lineup_id, created_at=None):
    _upsert_history('recent_lineup_copies', user_id, lineup_id, created_at=created_at)


def _history_rows(table_name, user_id, limit=20, user=None):
    visibility_sql = "l.status = 'normal'"
    visibility_params = []
    if user:
        if user['role'] == 'admin':
            visibility_sql = "l.status != 'deleted'"
        else:
            visibility_sql = "(l.status = 'normal' OR (l.status = 'hidden' AND l.user_id = ?))"
            visibility_params.append(user['id'])
    rows = get_db().execute(
        f'''
        SELECT
            l.*,
            owner.nickname AS owner_nickname_raw,
            owner.role AS owner_role,
            history.updated_at AS history_at
        FROM {table_name} history
        JOIN lineups l ON l.id = history.lineup_id
        JOIN users owner ON owner.id = l.user_id
        WHERE history.user_id = ? AND {visibility_sql}
        ORDER BY history.updated_at DESC, history.id DESC
        LIMIT ?
        ''',
        (user_id, *visibility_params, limit),
    ).fetchall()
    scores = score_map()
    return [{**serialize_lineup_row(row, scores, user=user), 'history_at': row['history_at']} for row in rows]


def list_recent_views(user_id, limit=20, user=None):
    return _history_rows('recent_lineup_views', user_id, limit=limit, user=user)


def list_recent_copies(user_id, limit=20, user=None):
    return _history_rows('recent_lineup_copies', user_id, limit=limit, user=user)


def sync_recent_history(user_id, views, copies):
    for item in list(views or [])[:20]:
        lineup_id = int(item['lineup_id'])
        record_recent_view(user_id, lineup_id, created_at=item.get('at'))
    for item in list(copies or [])[:20]:
        lineup_id = int(item['lineup_id'])
        record_recent_copy(user_id, lineup_id, created_at=item.get('at'))
