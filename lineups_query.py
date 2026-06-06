from __future__ import annotations

from datetime import datetime

from lineups_utils import visibility_clause


def build_list_clauses(user, view, query, season_id, default_season_id):
    visibility_sql, visibility_params = visibility_clause(user, alias='l')
    clauses = [visibility_sql]
    params = list(visibility_params)
    selected_season_id = season_id or default_season_id
    if selected_season_id:
        clauses.append('l.season_id = ?')
        params.append(selected_season_id)
    if view == 'mine':
        clauses = ["l.status != 'deleted'"]
        params = []
        clauses.append('l.user_id = ?')
        params.append(user['id'])
    if view == 'favorites':
        clauses.append('EXISTS (SELECT 1 FROM favorites f WHERE f.lineup_id = l.id AND f.user_id = ?)')
        params.append(user['id'])
    if query:
        clauses.append('l.name LIKE ?')
        params.append(f'%{query}%')
    return clauses, params


def count_lineups(db, clauses, params):
    sql = 'SELECT COUNT(*) AS total FROM lineups l WHERE ' + ' AND '.join(clauses)
    return db.execute(sql, params).fetchone()['total']


def matching_lineup_ids(db, clauses, params):
    sql = 'SELECT l.id FROM lineups l WHERE ' + ' AND '.join(clauses)
    rows = db.execute(sql, params).fetchall()
    return [row['id'] for row in rows]


def order_by_ids_sql(lineup_ids):
    if not lineup_ids:
        return 'l.id ASC'
    cases = ' '.join(f'WHEN {int(lineup_id)} THEN {index}' for index, lineup_id in enumerate(lineup_ids))
    return f'CASE l.id {cases} ELSE {len(lineup_ids)} END'


def fetch_lineup_rows(db, clauses, params, user=None, order_by='l.updated_at DESC, l.id DESC', limit=None, offset=None, lineup_ids=None):
    joins = ['JOIN users owner ON owner.id = l.user_id']
    select_fields = [
        'l.*',
        'owner.username AS owner_username',
        'owner.nickname AS owner_nickname_raw',
        'owner.role AS owner_role',
    ]
    join_params = []
    if user:
        today = datetime.now().strftime('%Y-%m-%d')
        joins.append('LEFT JOIN likes liked ON liked.lineup_id = l.id AND liked.user_id = ? AND liked.like_date = ?')
        joins.append('LEFT JOIN favorites favored ON favored.lineup_id = l.id AND favored.user_id = ?')
        join_params.extend([user['id'], today, user['id']])
        select_fields.extend([
            'CASE WHEN liked.id IS NULL THEN 0 ELSE 1 END AS is_liked_today',
            'CASE WHEN favored.id IS NULL THEN 0 ELSE 1 END AS is_favorited',
        ])
    else:
        select_fields.extend(['0 AS is_liked_today', '0 AS is_favorited'])

    where_clauses = list(clauses)
    where_params = list(params)
    if lineup_ids is not None:
        if not lineup_ids:
            return []
        placeholders = ','.join('?' for _ in lineup_ids)
        where_clauses.append(f'l.id IN ({placeholders})')
        where_params.extend(lineup_ids)

    sql = 'SELECT ' + ', '.join(select_fields) + ' FROM lineups l ' + ' '.join(joins)
    sql += ' WHERE ' + ' AND '.join(where_clauses)
    sql += f' ORDER BY {order_by}'

    query_params = join_params + where_params
    if limit is not None:
        sql += ' LIMIT ?'
        query_params.append(limit)
    if offset is not None:
        sql += ' OFFSET ?'
        query_params.append(offset)
    return db.execute(sql, query_params).fetchall()
