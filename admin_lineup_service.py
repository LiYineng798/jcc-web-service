from __future__ import annotations

import re

from audit import write_audit
from db import db_kind, now_text
from db_adapter import insert_returning_id_sql, last_insert_id, qmarks
from lineup_code import extract_lineup_code
from lineups_serialization import serialize_lineup_row
from lineups_utils import canonical_lineup_season_id, lineup_row, season_choice_map
from scoring import score_map

BULK_LINEUP_PATTERN = re.compile(r'[＃#]([^＃#\r\n]+)[＃#]\s*([A-Za-z0-9]+)')
BULK_NAME_SEPARATORS = ('-', '－', '–', '—')
MAX_BULK_IMPORT_TEXT_LENGTH = 200000


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


def bulk_lineup_display_name(name_segment):
    name = str(name_segment or '').strip()
    for separator in BULK_NAME_SEPARATORS:
        if separator in name:
            suffix = name.rsplit(separator, 1)[1].strip()
            if suffix:
                return suffix
    return name


def parse_bulk_lineup_entries(raw_text):
    entries = []
    for line_number, raw_line in enumerate(str(raw_text or '').splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        match = BULK_LINEUP_PATTERN.search(line)
        if not match:
            entries.append({
                'line': line_number,
                'raw': line,
                'status': 'invalid',
                'reason': '阵容码格式无效',
            })
            continue
        name = bulk_lineup_display_name(match.group(1))
        code = extract_lineup_code(f'#{match.group(2)}')
        if not name:
            entries.append({
                'line': line_number,
                'raw': line,
                'status': 'invalid',
                'reason': '阵容名称为空',
            })
            continue
        if len(name) > 80:
            entries.append({
                'line': line_number,
                'raw': line,
                'status': 'invalid',
                'reason': '阵容名称过长',
            })
            continue
        if not code:
            entries.append({
                'line': line_number,
                'raw': line,
                'status': 'invalid',
                'reason': '阵容码格式无效',
            })
            continue
        entries.append({
            'line': line_number,
            'name': name,
            'code': code,
            'status': 'pending',
        })
    return entries


def existing_lineup_codes(db, codes):
    if not codes:
        return set()
    rows = db.execute(
        f'SELECT code FROM lineups WHERE code IN ({qmarks(db_kind(), len(codes))})',
        tuple(codes),
    ).fetchall()
    return {row['code'] for row in rows}


def _mark_upload_duplicates(entries):
    seen = set()
    unique_codes = []
    for entry in entries:
        if entry['status'] == 'invalid':
            continue
        code = entry['code']
        if code in seen:
            entry['status'] = 'duplicate_in_upload'
            entry['reason'] = '本次上传内重复'
            continue
        seen.add(code)
        unique_codes.append(code)
    return unique_codes


def _bulk_import_summary(season_id, entries):
    return {
        'ok': True,
        'season_id': season_id,
        'importable_count': sum(1 for entry in entries if entry['status'] == 'importable'),
        'created_count': sum(1 for entry in entries if entry['status'] == 'created'),
        'duplicate_existing_count': sum(1 for entry in entries if entry['status'] == 'duplicate_existing'),
        'duplicate_in_upload_count': sum(1 for entry in entries if entry['status'] == 'duplicate_in_upload'),
        'invalid_count': sum(1 for entry in entries if entry['status'] == 'invalid'),
        'items': entries,
    }


def prepare_bulk_import_preview(db, data):
    raw_text = str((data or {}).get('raw_text') or '').strip()
    if not raw_text:
        return None, '请粘贴阵容码', 400
    if len(raw_text) > MAX_BULK_IMPORT_TEXT_LENGTH:
        return None, '粘贴内容过长', 400

    season_id = canonical_lineup_season_id((data or {}).get('season_id'))
    if not season_id or season_id not in season_choice_map():
        return None, '赛季无效或已隐藏', 400

    entries = parse_bulk_lineup_entries(raw_text)
    if not entries:
        return None, '请粘贴阵容码', 400

    unique_codes = _mark_upload_duplicates(entries)
    existing_codes = existing_lineup_codes(db, unique_codes)
    for entry in entries:
        if entry['status'] in {'invalid', 'duplicate_in_upload'}:
            continue
        if entry['code'] in existing_codes:
            entry['status'] = 'duplicate_existing'
            entry['reason'] = '阵容码已存在'
            continue
        entry['status'] = 'importable'
    return _bulk_import_summary(season_id, entries), None, 200


def preview_bulk_import_lineups(db, data):
    return prepare_bulk_import_preview(db, data)


def bulk_import_lineups(db, admin_id, data):
    summary, service_error, status_code = prepare_bulk_import_preview(db, data)
    if service_error:
        return summary, service_error, status_code

    season_id = summary['season_id']
    now = now_text()
    for entry in summary['items']:
        if entry['status'] != 'importable':
            continue
        cursor = db.execute(
            insert_returning_id_sql(
                '''INSERT INTO lineups (user_id, name, code, season_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'normal', ?, ?)''',
                db_kind(),
            ),
            (admin_id, entry['name'], entry['code'], season_id, now, now),
        )
        entry['id'] = last_insert_id(cursor, db_kind())
        entry['status'] = 'created'

    summary = _bulk_import_summary(season_id, summary['items'])
    write_audit(
        admin_id,
        'admin_bulk_import_lineups',
        'lineup_bulk_import',
        after={
            'season_id': season_id,
            'created_count': summary['created_count'],
            'duplicate_existing_count': summary['duplicate_existing_count'],
            'duplicate_in_upload_count': summary['duplicate_in_upload_count'],
            'invalid_count': summary['invalid_count'],
        },
    )
    db.commit()
    return summary, None, 200


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
