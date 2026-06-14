from __future__ import annotations

from datetime import datetime

from db import get_db
from lineups_utils import row_value


def serialize_lineup_row(row, scores, user=None, admin=False, db=None):
    db = db or get_db()
    score = scores.get(row['id'], {'rank_level': 'B', 'like_count': 0, 'copy_count': 0, 'score': 0})
    owner_role = row_value(row, 'owner_role')
    owner_username = row_value(row, 'owner_username')
    owner_nickname = row_value(row, 'owner_nickname_raw')
    if owner_role is None and owner_nickname is None and owner_username is None:
        owner = db.execute('SELECT id, username, nickname, role FROM users WHERE id = ?', (row['user_id'],)).fetchone()
        owner_role = owner['role'] if owner else None
        owner_username = owner['username'] if owner else None
        owner_nickname = owner['nickname'] if owner else None
    owner_name = '系统' if owner_role == 'admin' else (owner_nickname or '未知用户')
    is_owner = bool(user and user['id'] == row['user_id'])
    is_admin = bool(user and user['role'] == 'admin')
    liked = row_value(row, 'is_liked_today')
    favored = row_value(row, 'is_favorited')
    if liked is None:
        liked = False
    else:
        liked = bool(liked)
    if favored is None:
        favored = False
    else:
        favored = bool(favored)
    if user and row_value(row, 'is_liked_today') is None:
        today = datetime.now().strftime('%Y-%m-%d')
        liked = bool(db.execute(
            'SELECT id FROM likes WHERE user_id = ? AND lineup_id = ? AND like_date = ?',
            (user['id'], row['id'], today),
        ).fetchone())
    if user and row_value(row, 'is_favorited') is None:
        favored = bool(db.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND lineup_id = ?',
            (user['id'], row['id']),
        ).fetchone())
    data = {
        'id': row['id'],
        'name': row['name'],
        'code': row['code'],
        'season_id': row['season_id'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'version': row['version'],
        'status': row['status'],
        'owner_nickname': owner_name,
        'owner_username': owner_username,
        'rank_level': score['rank_level'],
        'like_count': score['like_count'],
        'copy_count': score['copy_count'],
        'is_liked_today': liked,
        'is_favorited': favored,
        'can_edit': is_owner or is_admin,
        'can_delete': is_owner or is_admin,
        'can_hide': row['status'] == 'normal' and (is_owner or is_admin),
    }
    if admin:
        data['score'] = score['score']
        data['user_id'] = row['user_id']
        data['admin_like_adjustment'] = row['admin_like_adjustment']
        data['admin_copy_adjustment'] = row['admin_copy_adjustment']
    return data
