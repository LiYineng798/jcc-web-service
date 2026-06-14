from __future__ import annotations

from audit import write_audit
from db import now_text
from lineups_serialization import serialize_lineup_row
from lineups_utils import lineup_row
from scoring import score_map


def build_admin_lineups_query(query):
    query = str(query or '').strip()
    params = []
    from_sql = '''FROM lineups
             LEFT JOIN users ON users.id = lineups.user_id
             WHERE lineups.status != 'deleted' '''
    if query:
        from_sql += ''' AND (
            lineups.name LIKE ? OR lineups.code LIKE ? OR users.username LIKE ? OR users.nickname LIKE ?
        )'''
        params.extend([f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'])
    base_sql = 'SELECT lineups.* ' + from_sql + ' ORDER BY lineups.id DESC'
    count_sql = 'SELECT COUNT(*) AS c ' + from_sql
    return base_sql, count_sql, params


def prepare_admin_lineup_update(data):
    fields = []
    params = []
    for key in ['name', 'code', 'status']:
        if key in data:
            fields.append(f'{key} = ?')
            params.append(str(data[key]).strip())
    return fields, params


def update_admin_lineup(db, admin_id, lineup_id, data):
    row = lineup_row(lineup_id)
    if not row:
        return None, '阵容不存在', 404
    fields, params = prepare_admin_lineup_update(data)
    if not fields:
        return None, '没有可更新字段', 400
    fields.append('updated_at = ?')
    fields.append('version = version + 1')
    params.extend([now_text(), lineup_id])
    db.execute(f'UPDATE lineups SET {", ".join(fields)} WHERE id = ?', params)
    write_audit(admin_id, 'admin_update_lineup', 'lineup', lineup_id, before=dict(row), after=data)
    db.commit()
    refreshed = lineup_row(lineup_id)
    return serialize_lineup_row(refreshed, score_map(), user={'id': admin_id, 'role': 'admin'}, admin=True), None, 200


def adjust_admin_lineup_score(db, admin_id, lineup_id, data):
    row = lineup_row(lineup_id)
    if not row:
        return None, '阵容不存在', 404
    like_adjustment = int(data.get('admin_like_adjustment', row['admin_like_adjustment']))
    copy_adjustment = int(data.get('admin_copy_adjustment', row['admin_copy_adjustment']))
    db.execute(
        'UPDATE lineups SET admin_like_adjustment = ?, admin_copy_adjustment = ?, updated_at = ? WHERE id = ?',
        (like_adjustment, copy_adjustment, now_text(), lineup_id),
    )
    write_audit(
        admin_id,
        'adjust_score',
        'lineup',
        lineup_id,
        before=dict(row),
        after={'admin_like_adjustment': like_adjustment, 'admin_copy_adjustment': copy_adjustment},
    )
    db.commit()
    refreshed = lineup_row(lineup_id)
    return serialize_lineup_row(refreshed, score_map(), user={'id': admin_id, 'role': 'admin'}, admin=True), None, 200
