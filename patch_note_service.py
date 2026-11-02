import re

from audit import write_audit
from db import db_kind, get_db, now_text
from db_adapter import insert_returning_id_sql, last_insert_id

PATCH_NOTE_STATUSES = {'draft', 'published', 'hidden'}
CHANGE_LABELS = {
    'buff': '加强',
    'nerf': '削弱',
    'adjust': '调整',
}
CHANGE_RE = re.compile(r'^-\s*\[(buff|nerf|adjust)\]\s*(.+)$')
SUBJECT_RE = re.compile(r'^([^：:]{1,24})[：:]\s*(.+)$')
# The trailing run of numbers, ratios and units before "=>", e.g. "法力值 0/30" or "冷却 1.5秒".
OLD_VALUE_RE = re.compile(r'^(.*?)\s*([-+]?\d[\d.,]*[^\s/]*(?:\s*/\s*[-+]?\d[\d.,]*[^\s/]*)*)$')
VALUE_SPLIT_RE = re.compile(r'\s*[；;]\s*')
EXCERPT_LENGTH = 96
HIGHLIGHT_LIMIT = 4


def split_value_changes(detail):
    """Split "治疗 300 => 325；护甲 40 => 50" into attribute/from/to rows."""
    if '=>' not in detail:
        return []
    changes = []
    for part in VALUE_SPLIT_RE.split(detail):
        if '=>' not in part:
            if changes:
                changes[-1]['note'] = (changes[-1]['note'] + ' ' + part).strip()
            else:
                changes.append({'attribute': part.strip(), 'from': '', 'to': '', 'note': ''})
            continue
        old_value, new_value = (value.strip() for value in part.split('=>', 1))
        match = OLD_VALUE_RE.match(old_value)
        attribute, before = (match.group(1).strip(), match.group(2).strip()) if match else ('', old_value)
        if match and not attribute and not before:
            attribute, before = old_value, ''
        changes.append({'attribute': attribute, 'from': before, 'to': new_value, 'note': ''})
    return changes


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
            text = text.strip()
            subject_match = SUBJECT_RE.match(text)
            subject, detail = subject_match.groups() if subject_match else ('', text)
            item = {
                'type': 'change',
                'kind': kind,
                'label': CHANGE_LABELS[kind],
                'text': text,
                'subject': subject.strip(),
                'detail': detail.strip(),
                'changes': split_value_changes(detail.strip()),
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


def empty_change_counts():
    return {kind: 0 for kind in CHANGE_LABELS}


def group_summary_items(items):
    """Group parsed lines by "##" section; lines before the first heading form an untitled lead section."""
    sections = []
    current = None
    for item in items:
        if item['type'] == 'section' or current is None:
            current = {
                'id': f'section-{len(sections) + 1}',
                'title': item['title'] if item['type'] == 'section' else '',
                'items': [],
                'counts': empty_change_counts(),
            }
            sections.append(current)
            if item['type'] == 'section':
                continue
        current['items'].append(item)
        if item['type'] == 'change':
            current['counts'][item['kind']] += 1
    return [section for section in sections if section['title'] or section['items']]


def summarize_patch_note(items):
    counts = empty_change_counts()
    for item in items:
        if item['type'] == 'change':
            counts[item['kind']] += 1
    texts = [item['text'] for item in items if item['type'] == 'text']
    excerpt = texts[0] if texts else ''
    if len(excerpt) > EXCERPT_LENGTH:
        excerpt = excerpt[:EXCERPT_LENGTH - 1].rstrip() + '…'
    return {
        'counts': counts,
        'change_total': sum(counts.values()),
        'section_titles': [item['title'] for item in items if item['type'] == 'section'],
        'excerpt': excerpt,
        'highlights': [
            {key: item[key] for key in ('kind', 'label', 'subject', 'detail', 'changes')}
            for item in items if item['type'] == 'change'
        ][:HIGHLIGHT_LIMIT],
    }


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
    items = parse_summary_markdown(row['summary_markdown'])
    payload['overview'] = summarize_patch_note(items)
    if include_body:
        payload.update({
            'summary_markdown': row['summary_markdown'],
            'summary_items': items,
            'summary_sections': group_summary_items(items),
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


def adjacent_public_patch_notes(patch_note_id):
    """Return the next newer and older published notes for reading navigation."""
    items = list_public_patch_notes()['items']
    index = next((position for position, item in enumerate(items) if item['id'] == patch_note_id), None)
    if index is None:
        return {'newer': None, 'older': None}
    return {
        'newer': items[index - 1] if index > 0 else None,
        'older': items[index + 1] if index + 1 < len(items) else None,
    }


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
        insert_returning_id_sql(
            '''
            INSERT INTO patch_notes
            (title, version, source_url, summary_markdown, original_text, status, published_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            db_kind(),
        ),
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
    patch_note_id = last_insert_id(cursor, db_kind())
    write_audit(actor_user_id, 'create_patch_note', 'patch_note', target_id=patch_note_id, after=payload)
    db.commit()
    row = db.execute('SELECT * FROM patch_notes WHERE id = ?', (patch_note_id,)).fetchone()
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
