import re

from audit import write_audit
from db import get_db, now_text

PATCH_NOTE_STATUSES = {'draft', 'published', 'hidden'}
CHANGE_LABELS = {
    'buff': '加强',
    'nerf': '削弱',
    'adjust': '调整',
}
CHANGE_RE = re.compile(r'^-\s*\[(buff|nerf|adjust)\]\s*(.+)$')


def parse_summary_markdown(markdown):
    items = []
    for raw_line in str(markdown or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('## '):
            items.append({'type': 'section', 'title': line[3:].strip()})
            continue
        match = CHANGE_RE.match(line)
        if match:
            kind, text = match.groups()
            item = {
                'type': 'change',
                'kind': kind,
                'label': CHANGE_LABELS[kind],
                'text': text.strip(),
                'old_value': '',
                'new_value': '',
            }
            if '=>' in text:
                old_value, new_value = text.split('=>', 1)
                item['old_value'] = old_value.strip()
                item['new_value'] = new_value.strip()
            items.append(item)
            continue
        items.append({'type': 'text', 'text': line})
    return items


def validate_patch_note_payload(data, existing=None):
    if not isinstance(data, dict):
        return None, '无效的请求数据'
    existing = existing or {}
    title = str(data.get('title', existing.get('title', ''))).strip()
    version = str(data.get('version', existing.get('version', ''))).strip()
    source_url = str(data.get('source_url', existing.get('source_url', ''))).strip()
    summary_markdown = str(data.get('summary_markdown', existing.get('summary_markdown', ''))).strip()
    original_text = str(data.get('original_text', existing.get('original_text', ''))).strip()
    status = str(data.get('status', existing.get('status', 'draft'))).strip()
    published_at = str(data.get('published_at', existing.get('published_at', ''))).strip()

    if not title:
        return None, '标题不能为空'
    if not summary_markdown:
        return None, '精简版不能为空'
    if not published_at:
        return None, '发布日期不能为空'
    if status not in PATCH_NOTE_STATUSES:
        return None, '状态无效'
    if source_url and not (source_url.startswith('http://') or source_url.startswith('https://') or source_url.startswith('/')):
        return None, '来源链接无效'

    return {
        'title': title,
        'version': version,
        'source_url': source_url,
        'summary_markdown': summary_markdown,
        'original_text': original_text,
        'status': status,
        'published_at': published_at,
    }, None


def serialize_patch_note(row, include_body=False):
    payload = {
        'id': row['id'],
        'title': row['title'],
        'version': row['version'],
        'source_url': row['source_url'],
        'status': row['status'],
        'published_at': row['published_at'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }
    if include_body:
        payload.update({
            'summary_markdown': row['summary_markdown'],
            'summary_items': parse_summary_markdown(row['summary_markdown']),
            'original_text': row['original_text'],
        })
    return payload


def list_public_patch_notes():
    rows = get_db().execute(
        '''
        SELECT * FROM patch_notes
        WHERE status = 'published'
        ORDER BY published_at DESC, id DESC
        '''
    ).fetchall()
    return {'items': [serialize_patch_note(row) for row in rows]}


def get_public_patch_note(patch_note_id):
    row = get_db().execute(
        "SELECT * FROM patch_notes WHERE id = ? AND status = 'published'",
        (patch_note_id,),
    ).fetchone()
    if not row:
        return None, '公告不存在', 404
    return serialize_patch_note(row, include_body=True), None, 200


def list_admin_patch_notes():
    rows = get_db().execute(
        '''
        SELECT * FROM patch_notes
        ORDER BY updated_at DESC, id DESC
        '''
    ).fetchall()
    return {'items': [serialize_patch_note(row, include_body=True) for row in rows]}


def create_patch_note(actor_user_id, data):
    payload, error = validate_patch_note_payload(data)
    if error:
        return None, error, 400
    now = now_text()
    db = get_db()
    cursor = db.execute(
        '''
        INSERT INTO patch_notes
        (title, version, source_url, summary_markdown, original_text, status, published_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            payload['title'],
            payload['version'],
            payload['source_url'],
            payload['summary_markdown'],
            payload['original_text'],
            payload['status'],
            payload['published_at'],
            now,
            now,
        ),
    )
    write_audit(actor_user_id, 'create_patch_note', 'patch_note', target_id=cursor.lastrowid, after=payload)
    db.commit()
    row = db.execute('SELECT * FROM patch_notes WHERE id = ?', (cursor.lastrowid,)).fetchone()
    return serialize_patch_note(row, include_body=True), None, 201


def update_patch_note(actor_user_id, patch_note_id, data):
    db = get_db()
    row = db.execute('SELECT * FROM patch_notes WHERE id = ?', (patch_note_id,)).fetchone()
    if not row:
        return None, '公告不存在', 404
    before = serialize_patch_note(row, include_body=True)
    payload, error = validate_patch_note_payload(data, existing=before)
    if error:
        return None, error, 400
    now = now_text()
    db.execute(
        '''
        UPDATE patch_notes
        SET title = ?, version = ?, source_url = ?, summary_markdown = ?, original_text = ?,
            status = ?, published_at = ?, updated_at = ?
        WHERE id = ?
        ''',
        (
            payload['title'],
            payload['version'],
            payload['source_url'],
            payload['summary_markdown'],
            payload['original_text'],
            payload['status'],
            payload['published_at'],
            now,
            patch_note_id,
        ),
    )
    after_row = db.execute('SELECT * FROM patch_notes WHERE id = ?', (patch_note_id,)).fetchone()
    after = serialize_patch_note(after_row, include_body=True)
    write_audit(actor_user_id, 'update_patch_note', 'patch_note', target_id=patch_note_id, before=before, after=after)
    db.commit()
    return after, None, 200


def hide_patch_note(actor_user_id, patch_note_id):
    return update_patch_note(actor_user_id, patch_note_id, {'status': 'hidden'})
