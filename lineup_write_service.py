from audit import write_audit
from db import get_db, now_text
from lineup_code import LINEUP_CODE_MESSAGE, extract_lineup_code
from lineups_serialization import serialize_lineup_row
from lineups_utils import (
    DEFAULT_LINEUP_SEASON_ID,
    canonical_lineup_season_id,
    lineup_row,
    lineup_season_manifest,
    normalize_lineup_status,
    season_choice_map,
)
from scoring import score_map


def validate_lineup_payload(data, default_status='normal', default_season_id=None):
    name = str(data.get('name', '')).strip()
    raw_code = str(data.get('code', '')).strip()
    status = normalize_lineup_status(data.get('status'), default=default_status)
    if not name or len(name) > 80:
        return None, '请输入阵容名称'
    if not raw_code or len(raw_code) > 20000:
        return None, '请输入阵容码'
    if not status:
        return None, '阵容状态无效'
    code = extract_lineup_code(raw_code)
    if not code:
        return None, LINEUP_CODE_MESSAGE
    season_id = canonical_lineup_season_id(data.get('season_id'))
    if not season_id:
        season_id = canonical_lineup_season_id(default_season_id)
    if not season_id:
        return None, '请选择所属赛季'
    if season_id not in season_choice_map():
        return None, '赛季无效或已隐藏'
    return {'name': name, 'code': code, 'status': status, 'season_id': season_id}, None


def create_lineup_record(user, data):
    payload, validation_error = validate_lineup_payload(
        data or {},
        default_status='normal',
        default_season_id=lineup_season_manifest().get('default_season_id', DEFAULT_LINEUP_SEASON_ID),
    )
    if validation_error:
        return None, validation_error, 400
    now = now_text()
    db = get_db()
    cursor = db.execute(
        '''INSERT INTO lineups (user_id, name, code, season_id, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user['id'], payload['name'], payload['code'], payload['season_id'], payload['status'], now, now),
    )
    write_audit(user['id'], 'create_lineup', 'lineup', cursor.lastrowid, after=payload)
    db.commit()
    row = lineup_row(cursor.lastrowid)
    return serialize_lineup_row(row, score_map(), user=user), None, 201


def update_lineup_record(user, lineup_id, data):
    row = lineup_row(lineup_id)
    if not row or row['status'] == 'deleted':
        return None, '阵容不存在', 404
    if row['user_id'] != user['id'] and user['role'] != 'admin':
        return None, '无权修改该阵容', 403
    if 'version' in (data or {}) and int(data['version']) != row['version']:
        return None, '阵容已被更新，请刷新后重试', 409
    payload, validation_error = validate_lineup_payload(
        data or {},
        default_status=row['status'],
        default_season_id=row['season_id'],
    )
    if validation_error:
        return None, validation_error, 400
    get_db().execute(
        'UPDATE lineups SET name = ?, code = ?, season_id = ?, status = ?, updated_at = ?, version = version + 1 WHERE id = ?',
        (payload['name'], payload['code'], payload['season_id'], payload['status'], now_text(), lineup_id),
    )
    write_audit(user['id'], 'update_lineup', 'lineup', lineup_id, before=dict(row), after=payload)
    get_db().commit()
    return serialize_lineup_row(lineup_row(lineup_id), score_map(), user=user, admin=user['role'] == 'admin'), None, 200


def delete_lineup_record(user, lineup_id):
    row = lineup_row(lineup_id)
    if not row:
        return None, '阵容不存在', 404
    if row['user_id'] != user['id'] and user['role'] != 'admin':
        return None, '无权删除该阵容', 403
    get_db().execute("UPDATE lineups SET status = 'deleted', updated_at = ? WHERE id = ?", (now_text(), lineup_id))
    write_audit(user['id'], 'delete_lineup', 'lineup', lineup_id, before=dict(row))
    get_db().commit()
    return None, None, 204


def hide_lineup_record(user, lineup_id):
    row = lineup_row(lineup_id)
    if not row or row['status'] == 'deleted':
        return None, '阵容不存在', 404
    if row['user_id'] != user['id'] and user['role'] != 'admin':
        return None, '无权隐藏该阵容', 403
    if row['status'] != 'hidden':
        get_db().execute("UPDATE lineups SET status = 'hidden', updated_at = ? WHERE id = ?", (now_text(), lineup_id))
        write_audit(user['id'], 'hide_lineup', 'lineup', lineup_id, before=dict(row), after={'status': 'hidden'})
        get_db().commit()
    return {'ok': True}, None, 200
