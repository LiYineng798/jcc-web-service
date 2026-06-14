# Patch Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manually managed update announcement feature with lightweight homepage entry, public patch note pages, admin CRUD, and structured summary rendering.

**Architecture:** Add a first-class `patch_notes` SQLite table and a focused `patch_note_service.py` module for validation, serialization, and summary parsing. Expose public routes through a new `patch_notes.py` blueprint and admin routes through `admin.py`, following the existing thin-route/service pattern.

**Tech Stack:** Flask, SQLite, Jinja templates, vanilla JavaScript, existing `static/styles.css`, pytest.

---

## File Structure

- Create `patch_note_service.py`: validation, CRUD service functions, public/admin serializers, summary parser.
- Create `patch_notes.py`: public page routes and public JSON API.
- Create `templates/patch_notes.html`: public list page.
- Create `templates/patch_note_detail.html`: public detail page.
- Create `static/patch-notes.js`: list/detail API loading and original-text toggle.
- Modify `db_schema.py`: add `patch_notes` table and index.
- Modify `db_migrations.py`: add migration for existing databases.
- Modify `app.py`: register `patch_notes_bp`.
- Modify `admin.py`: add admin patch note endpoints.
- Modify `templates/index.html`: add `更新公告` nav link.
- Modify `templates/admin.html`: add admin tab.
- Modify `static/admin.js`: add admin state, loading, rendering, create/edit/delete/status actions.
- Modify `static/styles.css`: add patch note public/admin styles.
- Create `tests/test_patch_notes.py`: public/service/parser coverage.
- Create `tests/test_admin_patch_notes.py`: admin API coverage.
- Modify `tests/test_ui_routes.py`: homepage/admin/page route assertions.

---

### Task 1: Schema and Migration

**Files:**
- Modify: `db_schema.py`
- Modify: `db_migrations.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write failing schema tests**

Add these tests to `tests/test_schema.py`:

```python
def test_patch_notes_table_exists(app):
    assert 'patch_notes' in app.get_table_names()


def test_patch_notes_columns_exist(client):
    with client.application.app_context():
        from db import get_db
        columns = get_db().execute('PRAGMA table_info(patch_notes)').fetchall()
    names = {row['name'] for row in columns}
    assert {
        'id',
        'title',
        'version',
        'source_url',
        'summary_markdown',
        'original_text',
        'status',
        'published_at',
        'created_at',
        'updated_at',
    }.issubset(names)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_schema.py::test_patch_notes_table_exists tests/test_schema.py::test_patch_notes_columns_exist -v`

Expected: first test fails because `patch_notes` is absent.

- [ ] **Step 3: Add schema**

In `db_schema.py`, add this SQL block before the closing `'''` of `SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS patch_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    summary_markdown TEXT NOT NULL,
    original_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patch_notes_status_published_at
ON patch_notes (status, published_at DESC, id DESC);
```

- [ ] **Step 4: Add migration helper**

In `db_migrations.py`, update imports and migration entry point:

```python
from db_schema import EXTRA_INDEX_STATEMENTS, LINEUP_COLUMN_MIGRATIONS, table_columns, table_names


def migrate_schema(db, admin_id, now_text_func):
    migrate_lineups_table(db, admin_id)
    migrate_legacy_live_comp_stats(db, now_text_func)
    migrate_patch_notes_table(db)
```

Add this function:

```python
def migrate_patch_notes_table(db):
    tables = table_names(db)
    if 'patch_notes' not in tables:
        db.execute(
            '''
            CREATE TABLE IF NOT EXISTS patch_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                summary_markdown TEXT NOT NULL,
                original_text TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                published_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
    db.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_patch_notes_status_published_at
        ON patch_notes (status, published_at DESC, id DESC)
        '''
    )
```

- [ ] **Step 5: Run schema tests**

Run: `pytest tests/test_schema.py tests/test_db_migrations_module.py -v`

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add db_schema.py db_migrations.py tests/test_schema.py
git commit -m "feat: add patch notes schema"
```

---

### Task 2: Patch Note Service and Parser

**Files:**
- Create: `patch_note_service.py`
- Test: `tests/test_patch_notes.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_patch_notes.py`:

```python
from patch_note_service import parse_summary_markdown, validate_patch_note_payload


def test_parse_summary_markdown_recognizes_sections_and_change_types():
    parsed = parse_summary_markdown(
        '## 英雄调整\n\n'
        '- [buff] 亚托克斯：治疗 300 => 325\n'
        '- [nerf] 菲奥娜：真实伤害 40 => 37\n'
        '- [adjust] 法官：机制重做\n'
    )

    assert parsed[0] == {'type': 'section', 'title': '英雄调整'}
    assert parsed[1]['kind'] == 'buff'
    assert parsed[1]['label'] == '加强'
    assert parsed[1]['old_value'] == '亚托克斯：治疗 300'
    assert parsed[1]['new_value'] == '325'
    assert parsed[2]['kind'] == 'nerf'
    assert parsed[2]['label'] == '削弱'
    assert parsed[3]['kind'] == 'adjust'
    assert parsed[3]['text'] == '法官：机制重做'


def test_validate_patch_note_payload_rejects_invalid_status_and_source_url():
    payload, error = validate_patch_note_payload({
        'title': '17.4更新公告',
        'published_at': '2026-05-28',
        'summary_markdown': '- [buff] 亚托克斯：治疗 300 => 325',
        'status': 'online',
        'source_url': 'javascript:alert(1)',
    })

    assert payload is None
    assert error == '状态无效'


def test_validate_patch_note_payload_accepts_minimal_payload():
    payload, error = validate_patch_note_payload({
        'title': '17.4更新公告',
        'published_at': '2026-05-28',
        'summary_markdown': '- [buff] 亚托克斯：治疗 300 => 325',
        'status': 'published',
        'source_url': 'https://example.com/notice',
    })

    assert error is None
    assert payload['title'] == '17.4更新公告'
    assert payload['version'] == ''
    assert payload['status'] == 'published'
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_patch_notes.py -v`

Expected: import fails because `patch_note_service.py` does not exist.

- [ ] **Step 3: Create service module**

Create `patch_note_service.py`:

```python
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
```

- [ ] **Step 4: Run service tests**

Run: `pytest tests/test_patch_notes.py -v`

Expected: parser and validation tests pass.

- [ ] **Step 5: Commit**

```bash
git add patch_note_service.py tests/test_patch_notes.py
git commit -m "feat: add patch note service"
```

---

### Task 3: Public API and Page Routes

**Files:**
- Create: `patch_notes.py`
- Modify: `app.py`
- Modify: `app_pages.py`
- Test: `tests/test_patch_notes.py`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Add failing public route tests**

Append to `tests/test_patch_notes.py`:

```python
from test_admin import login_admin


def create_published_patch_note(client, headers):
    response = client.post('/api/admin/patch-notes', json={
        'title': '17.4更新公告',
        'version': '17.4',
        'source_url': 'https://example.com/jcc/174',
        'summary_markdown': '## 英雄调整\n- [buff] 亚托克斯：治疗 300 => 325',
        'original_text': '<script>alert(1)</script>\n原文正文',
        'status': 'published',
        'published_at': '2026-05-28',
    }, headers=headers)
    return response


def test_public_patch_notes_only_lists_published(client):
    headers = login_admin(client)
    published = create_published_patch_note(client, headers)
    assert published.status_code == 201
    draft = client.post('/api/admin/patch-notes', json={
        'title': '草稿公告',
        'summary_markdown': '- [adjust] 草稿',
        'status': 'draft',
        'published_at': '2026-05-29',
    }, headers=headers)
    assert draft.status_code == 201

    payload = client.get('/api/patch-notes').get_json()
    assert [item['title'] for item in payload['items']] == ['17.4更新公告']


def test_public_patch_note_detail_includes_summary_items_and_plain_original(client):
    headers = login_admin(client)
    created = create_published_patch_note(client, headers).get_json()

    payload = client.get(f"/api/patch-notes/{created['id']}").get_json()

    assert payload['title'] == '17.4更新公告'
    assert payload['summary_items'][1]['kind'] == 'buff'
    assert payload['original_text'] == '<script>alert(1)</script>\n原文正文'


def test_public_patch_note_detail_hides_drafts(client):
    headers = login_admin(client)
    created = client.post('/api/admin/patch-notes', json={
        'title': '草稿公告',
        'summary_markdown': '- [adjust] 草稿',
        'status': 'draft',
        'published_at': '2026-05-29',
    }, headers=headers).get_json()

    assert client.get(f"/api/patch-notes/{created['id']}").status_code == 404
```

Append to `tests/test_ui_routes.py`:

```python
def test_patch_note_pages_exist_and_homepage_links_to_patch_notes(client):
    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/patch-notes"' in index_html
    assert '更新公告' in index_html

    list_response = client.get('/patch-notes')
    detail_response = client.get('/patch-notes/1')

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert 'id="patchNotesApp"' in list_response.get_data(as_text=True)
    assert 'id="patchNoteDetailApp"' in detail_response.get_data(as_text=True)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_patch_notes.py tests/test_ui_routes.py::test_patch_note_pages_exist_and_homepage_links_to_patch_notes -v`

Expected: admin endpoints and public routes are missing.

- [ ] **Step 3: Create public blueprint**

Create `patch_notes.py`:

```python
from flask import Blueprint, jsonify

from patch_note_service import get_public_patch_note, list_public_patch_notes
from route_response import respond_service_result
from visits import tracked_template_response

patch_notes_bp = Blueprint('patch_notes', __name__)


@patch_notes_bp.get('/patch-notes')
def patch_notes_page():
    return tracked_template_response('patch_notes.html', 'patch_notes')


@patch_notes_bp.get('/patch-notes/<int:patch_note_id>')
def patch_note_detail_page(patch_note_id):
    return tracked_template_response('patch_note_detail.html', 'patch_note_detail', patch_note_id=patch_note_id)


@patch_notes_bp.get('/api/patch-notes')
def public_patch_notes():
    return jsonify(list_public_patch_notes())


@patch_notes_bp.get('/api/patch-notes/<int:patch_note_id>')
def public_patch_note_detail(patch_note_id):
    payload, service_error, status_code = get_public_patch_note(patch_note_id)
    return respond_service_result(payload, service_error, status_code)
```

- [ ] **Step 4: Register blueprint**

In `app.py`, add the import and registration near other blueprints:

```python
from patch_notes import patch_notes_bp
```

```python
app.register_blueprint(patch_notes_bp)
```

- [ ] **Step 5: Add admin API**

In `admin.py`, import:

```python
from patch_note_service import create_patch_note, hide_patch_note, list_admin_patch_notes, update_patch_note
```

Add endpoints near other admin API routes:

```python
@admin_bp.get('/api/admin/patch-notes')
def admin_patch_notes():
    admin, error = admin_required()
    if error:
        return error
    return jsonify(list_admin_patch_notes())


@admin_bp.post('/api/admin/patch-notes')
def admin_create_patch_note():
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = create_patch_note(admin['id'], request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.put('/api/admin/patch-notes/<int:patch_note_id>')
def admin_update_patch_note(patch_note_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = update_patch_note(admin['id'], patch_note_id, request.get_json(silent=True) or {})
    return respond_service_result(result, service_error, status_code)


@admin_bp.delete('/api/admin/patch-notes/<int:patch_note_id>')
def admin_delete_patch_note(patch_note_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = hide_patch_note(admin['id'], patch_note_id)
    return respond_service_result(result, service_error, status_code)
```

- [ ] **Step 6: Add placeholder templates and homepage link**

Create `templates/patch_notes.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>更新公告 - 金铲铲阵容库</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon.png') }}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}" />
  </head>
  <body>
    <div class="page-shell detail-page-shell">
      <nav class="nav-bar" aria-label="页面工具">
        <a class="ghost-link" href="/">返回阵容库</a>
        <button class="theme-toggle" id="themeToggle" type="button" aria-label="切换深浅色模式">
          <span id="themeIcon">☾</span>
          <span id="themeText">夜间模式</span>
        </button>
      </nav>
      <header class="auth-hero">
        <p class="eyebrow">Patch Notes</p>
        <h1>更新公告</h1>
        <p class="hero-description">查看版本更新重点和官方原文归档。</p>
      </header>
      <section class="panel">
        <div id="patchNotesApp">公告加载中...</div>
      </section>
    </div>
    <script src="{{ url_for('static', filename='patch-notes.js') }}" defer></script>
  </body>
</html>
```

Create `templates/patch_note_detail.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>更新公告详情 - 金铲铲阵容库</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon.png') }}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}" />
  </head>
  <body>
    <div class="page-shell detail-page-shell">
      <nav class="nav-bar" aria-label="页面工具">
        <a class="ghost-link" href="/patch-notes">返回更新公告</a>
        <a class="ghost-link" href="/">返回阵容库</a>
        <button class="theme-toggle" id="themeToggle" type="button" aria-label="切换深浅色模式">
          <span id="themeIcon">☾</span>
          <span id="themeText">夜间模式</span>
        </button>
      </nav>
      <section class="panel">
        <div id="patchNoteDetailApp" data-patch-note-id="{{ patch_note_id }}">公告加载中...</div>
      </section>
    </div>
    <script src="{{ url_for('static', filename='patch-notes.js') }}" defer></script>
  </body>
</html>
```

In `templates/index.html`, add this beside the simulator link:

```html
            <a class="ghost-link nav-tool-link" href="/patch-notes">更新公告</a>
```

- [ ] **Step 7: Add minimal JS so templates load cleanly**

Create `static/patch-notes.js`:

```javascript
const patchListRoot = document.querySelector('#patchNotesApp');
const patchDetailRoot = document.querySelector('#patchNoteDetailApp');
const patchThemeToggle = document.querySelector('#themeToggle');
const patchThemeIcon = document.querySelector('#themeIcon');
const patchThemeText = document.querySelector('#themeText');

setPatchTheme(localStorage.getItem('theme') || 'light');
patchThemeToggle?.addEventListener('click', () => setPatchTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));

if (patchListRoot) loadPatchNoteList();
if (patchDetailRoot) loadPatchNoteDetail();

async function loadPatchNoteList() {
  try {
    const data = await fetch('/api/patch-notes').then((response) => response.json());
    renderPatchNoteList(data.items || []);
  } catch (error) {
    patchListRoot.textContent = '公告加载失败，请稍后再试';
  }
}

async function loadPatchNoteDetail() {
  try {
    const id = patchDetailRoot.dataset.patchNoteId;
    const response = await fetch(`/api/patch-notes/${id}`);
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.error || '公告不存在');
    renderPatchNoteDetail(data);
  } catch (error) {
    patchDetailRoot.textContent = error.message || '公告加载失败';
  }
}

function renderPatchNoteList(items) {
  patchListRoot.replaceChildren();
  const list = document.createElement('div');
  list.className = 'patch-note-list';
  if (!items.length) {
    list.append(el('div', 'empty-state', '暂无更新公告'));
  } else {
    items.forEach((item) => {
      const card = el('article', 'patch-note-card');
      const title = el('h2', '', item.title);
      const meta = el('p', 'admin-meta', `${item.version || '版本公告'} · ${item.published_at}`);
      const link = el('a', 'primary-link', '查看公告');
      link.href = `/patch-notes/${item.id}`;
      card.append(title, meta, link);
      list.append(card);
    });
  }
  patchListRoot.append(list);
}

function renderPatchNoteDetail(item) {
  patchDetailRoot.replaceChildren();
  const stack = el('div', 'detail-stack patch-note-detail');
  stack.append(el('p', 'section-kicker', 'Patch Notes'));
  stack.append(el('h1', 'detail-title', item.title));
  stack.append(el('p', 'hero-description', `${item.version || '版本公告'} · ${item.published_at}`));
  if (item.source_url) {
    const source = el('a', 'ghost-link', '查看原公告');
    source.href = item.source_url;
    source.target = item.source_url.startsWith('/') ? '' : '_blank';
    source.rel = 'noopener';
    stack.append(source);
  }
  stack.append(renderSummary(item.summary_items || []));
  if (item.original_text) stack.append(renderOriginal(item.original_text));
  patchDetailRoot.append(stack);
}

function renderSummary(items) {
  const wrap = el('div', 'patch-note-summary');
  items.forEach((item) => {
    if (item.type === 'section') {
      wrap.append(el('h2', 'patch-note-section', item.title));
      return;
    }
    if (item.type === 'change') {
      const row = el('article', `patch-note-change patch-note-change-${item.kind}`);
      row.append(el('span', `change-tag change-tag-${item.kind}`, item.label));
      const body = el('div', 'patch-note-change-body');
      if (item.old_value || item.new_value) {
        body.append(el('span', 'change-old-value', item.old_value), el('span', 'change-arrow', '=>'), el('span', 'change-new-value', item.new_value));
      } else {
        body.append(el('span', '', item.text));
      }
      row.append(body);
      wrap.append(row);
      return;
    }
    wrap.append(el('p', 'patch-note-text', item.text));
  });
  return wrap;
}

function renderOriginal(text) {
  const details = document.createElement('details');
  details.className = 'patch-note-original';
  const summary = el('summary', '', '展开原文');
  const pre = el('pre', 'code-preview');
  pre.textContent = text;
  details.append(summary, pre);
  return details;
}

function setPatchTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  if (patchThemeIcon) patchThemeIcon.textContent = theme === 'dark' ? '☼' : '☾';
  if (patchThemeText) patchThemeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}

function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
```

- [ ] **Step 8: Run public tests**

Run: `pytest tests/test_patch_notes.py tests/test_ui_routes.py::test_patch_note_pages_exist_and_homepage_links_to_patch_notes -v`

Expected: tests pass.

- [ ] **Step 9: Commit**

```bash
git add app.py admin.py patch_notes.py templates/patch_notes.html templates/patch_note_detail.html templates/index.html static/patch-notes.js tests/test_patch_notes.py tests/test_ui_routes.py
git commit -m "feat: add public patch notes pages"
```

---

### Task 4: Admin Patch Notes API Coverage

**Files:**
- Test: `tests/test_admin_patch_notes.py`
- Modify if needed: `patch_note_service.py`
- Modify if needed: `admin.py`

- [ ] **Step 1: Write admin API tests**

Create `tests/test_admin_patch_notes.py`:

```python
from test_admin import login_admin
from test_auth import register_user


def patch_note_payload(**overrides):
    payload = {
        'title': '17.4更新公告',
        'version': '17.4',
        'source_url': 'https://example.com/jcc/174',
        'summary_markdown': '## 英雄调整\n- [buff] 亚托克斯：治疗 300 => 325',
        'original_text': '官方原文',
        'status': 'draft',
        'published_at': '2026-05-28',
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_update_publish_and_hide_patch_note(client):
    headers = login_admin(client)
    created = client.post('/api/admin/patch-notes', json=patch_note_payload(), headers=headers)
    assert created.status_code == 201
    patch_note_id = created.get_json()['id']

    updated = client.put(
        f'/api/admin/patch-notes/{patch_note_id}',
        json=patch_note_payload(status='published', title='17.4正式更新公告'),
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.get_json()['status'] == 'published'
    assert updated.get_json()['title'] == '17.4正式更新公告'

    listed = client.get('/api/admin/patch-notes', headers=headers).get_json()
    assert listed['items'][0]['id'] == patch_note_id

    hidden = client.delete(f'/api/admin/patch-notes/{patch_note_id}', headers=headers)
    assert hidden.status_code == 200
    assert hidden.get_json()['status'] == 'hidden'


def test_admin_patch_note_validation_errors(client):
    headers = login_admin(client)
    response = client.post('/api/admin/patch-notes', json=patch_note_payload(title=''), headers=headers)
    assert response.status_code == 400
    assert response.get_json()['error'] == '标题不能为空'

    response = client.post('/api/admin/patch-notes', json=patch_note_payload(source_url='javascript:alert(1)'), headers=headers)
    assert response.status_code == 400
    assert response.get_json()['error'] == '来源链接无效'


def test_non_admin_cannot_manage_patch_notes(client):
    assert client.get('/api/admin/patch-notes').status_code == 401
    register_user(client, username='normal', email='normal@example.com')
    assert client.get('/api/admin/patch-notes').status_code == 403
    response = client.post('/api/admin/patch-notes', json=patch_note_payload())
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_admin_patch_notes.py -v`

Expected: tests pass. If the delete test fails because `hide_patch_note()` requires existing fields, update `hide_patch_note()` to read the row and call `update_patch_note()` with the serialized existing payload plus `status='hidden'`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_admin_patch_notes.py patch_note_service.py admin.py
git commit -m "test: cover admin patch notes api"
```

---

### Task 5: Public Styling and Rendering Verification

**Files:**
- Modify: `static/styles.css`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Add CSS presence test**

Append to `tests/test_ui_routes.py`:

```python
def test_patch_note_styles_exist():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.patch-note-list' in css
    assert '.change-tag-buff' in css
    assert '.change-tag-nerf' in css
    assert '.patch-note-original' in css
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_ui_routes.py::test_patch_note_styles_exist -v`

Expected: fails because CSS classes are absent.

- [ ] **Step 3: Add CSS**

Append to `static/styles.css`:

```css
.patch-note-list,
.patch-note-summary {
  display: grid;
  gap: 14px;
}

.patch-note-card,
.patch-note-change {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface-solid);
}

.patch-note-card {
  display: grid;
  gap: 10px;
  padding: 18px;
}

.patch-note-card h2 {
  margin-bottom: 0;
  font-size: 1.12rem;
}

.patch-note-detail {
  gap: 18px;
}

.patch-note-section {
  margin: 12px 0 0;
  font-size: 1.08rem;
}

.patch-note-change {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 14px 16px;
}

.change-tag {
  display: inline-flex;
  min-width: 48px;
  justify-content: center;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 0.82rem;
  font-weight: 800;
}

.change-tag-buff {
  background: rgba(196, 67, 58, 0.13);
  color: #c4433a;
}

.change-tag-nerf {
  background: rgba(36, 133, 82, 0.13);
  color: #248552;
}

.change-tag-adjust {
  background: rgba(164, 106, 18, 0.13);
  color: #a46a12;
}

.patch-note-change-body {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 0;
  line-height: 1.7;
}

.change-old-value {
  color: var(--muted);
  text-decoration: line-through;
  text-decoration-thickness: 1px;
}

.patch-note-change-buff .change-new-value {
  color: #c4433a;
  font-weight: 800;
}

.patch-note-change-nerf .change-new-value {
  color: #248552;
  font-weight: 800;
}

.patch-note-change-adjust .change-new-value {
  color: var(--accent-strong);
  font-weight: 800;
}

.patch-note-text {
  margin-bottom: 0;
  color: var(--muted);
  line-height: 1.8;
}

.patch-note-original {
  display: grid;
  gap: 12px;
}

.patch-note-original summary {
  width: fit-content;
  color: var(--accent-strong);
  cursor: pointer;
  font-weight: 700;
}

@media (max-width: 560px) {
  .patch-note-change {
    grid-template-columns: 1fr;
  }

  .change-tag {
    width: fit-content;
  }
}
```

- [ ] **Step 4: Run style test**

Run: `pytest tests/test_ui_routes.py::test_patch_note_styles_exist -v`

Expected: test passes.

- [ ] **Step 5: Commit**

```bash
git add static/styles.css tests/test_ui_routes.py
git commit -m "style: add patch note presentation"
```

---

### Task 6: Admin UI Workbench

**Files:**
- Modify: `templates/admin.html`
- Modify: `static/admin.js`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Add admin UI tests**

Update `test_pages_include_favicon_and_favicon_route_exists` in `tests/test_ui_routes.py` to include:

```python
    assert 'data-admin-tab="patch-notes"' in admin_html
```

Append:

```python
def test_admin_js_contains_patch_notes_workbench():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'patchNotes' in js
    assert 'loadPatchNotes' in js
    assert 'renderPatchNotesWorkspace' in js
    assert 'PATCH_NOTE_TEMPLATE' in js
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_ui_routes.py::test_pages_include_favicon_and_favicon_route_exists tests/test_ui_routes.py::test_admin_js_contains_patch_notes_workbench -v`

Expected: fails because admin tab and JS are absent.

- [ ] **Step 3: Add admin tab**

In `templates/admin.html`, add this button in the admin tab bar:

```html
          <button class="admin-tab" data-admin-tab="patch-notes" type="button">更新公告</button>
```

- [ ] **Step 4: Add admin state and loader**

In `static/admin.js`, add this to `state`:

```javascript
    patchNotes: { items: [], loadedAt: 0 },
    patchNoteEditing: null,
```

Add this constant near `liveSeasonStatusOptions`:

```javascript
  const PATCH_NOTE_TEMPLATE = `## 英雄调整

- [buff] 名称：旧值 => 新值
- [nerf] 名称：旧值 => 新值
- [adjust] 名称：机制说明

## 羁绊调整

- [buff] 名称：旧值 => 新值

## 装备调整

- [nerf] 名称：旧值 => 新值`;
```

In `activateTab`, add:

```javascript
    if (tabKey === 'patch-notes') await loadPatchNotes();
```

Add loader:

```javascript
  async function loadPatchNotes({ force = false } = {}) {
    if (!force && isFresh(state.patchNotes.loadedAt)) return;
    const payload = await api('/api/admin/patch-notes');
    state.patchNotes = { items: payload.items || [], loadedAt: Date.now() };
  }
```

In `render()`, add:

```javascript
    if (state.activeTab === 'patch-notes') root.append(renderPatchNotesWorkspace());
```

- [ ] **Step 5: Add admin workbench rendering**

Add these functions before `renderSettingsWorkspace()`:

```javascript
  function renderPatchNotesWorkspace() {
    const panel = workbenchPanel('更新公告', '维护游戏官网更新公告、精简版和原文归档');
    const body = panel.querySelector('.admin-workspace-body');
    const actions = el('div', 'card-actions');
    actions.append(button('新增公告', () => {
      state.patchNoteEditing = emptyPatchNoteDraft();
      render();
    }, 'small-button'));
    body.append(actions);

    if (state.patchNoteEditing) {
      body.append(renderPatchNoteForm(state.patchNoteEditing));
    }

    const list = el('div', 'admin-list');
    if (!state.patchNotes.items.length) {
      list.append(empty('暂无更新公告'));
    } else {
      state.patchNotes.items.forEach((item) => list.append(patchNoteAdminCard(item)));
    }
    body.append(list);
    return panel;
  }

  function emptyPatchNoteDraft() {
    return {
      id: null,
      title: '',
      version: '',
      source_url: '',
      summary_markdown: PATCH_NOTE_TEMPLATE,
      original_text: '',
      status: 'draft',
      published_at: todayInputValue(),
    };
  }

  function patchNoteAdminCard(item) {
    const card = el('article', 'admin-card admin-card-tight');
    const head = el('div', 'admin-card-head');
    head.append(el('h3', '', item.title), el('span', 'admin-pill', item.status));
    const meta = el('p', 'admin-meta', `${item.version || '版本公告'} · ${item.published_at} · 更新 ${item.updated_at}`);
    const actions = el('div', 'card-actions');
    actions.append(
      button('编辑', () => {
        state.patchNoteEditing = { ...item };
        render();
      }, 'small-button'),
      button(item.status === 'published' ? '下线' : '发布', async () => {
        await savePatchNote({ ...item, status: item.status === 'published' ? 'hidden' : 'published' });
      }, 'small-button'),
      button('隐藏', async () => {
        if (!confirm('确定隐藏这条公告吗？')) return;
        await api(`/api/admin/patch-notes/${item.id}`, { method: 'DELETE' });
        await loadPatchNotes({ force: true });
        setNotice('公告已隐藏');
        state.patchNoteEditing = null;
        render();
      }, 'small-button danger-button'),
    );
    card.append(head, meta, actions);
    return card;
  }

  function renderPatchNoteForm(item) {
    const form = el('form', 'admin-card');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = readPatchNoteForm();
      await savePatchNote(payload);
    });

    const fields = el('div');
    fields.style.cssText = 'display:grid;gap:12px;width:100%';
    fields.append(
      adminInput('patchNoteTitle', '标题', item.title),
      adminInput('patchNoteVersion', '版本号，例如 17.4', item.version),
      adminInput('patchNotePublishedAt', '发布日期，例如 2026-05-28', item.published_at),
      adminInput('patchNoteSourceUrl', '来源链接（可选）', item.source_url),
      adminTextarea('patchNoteSummary', '精简版 Markdown', item.summary_markdown, 10),
      adminTextarea('patchNoteOriginal', '原文（可选）', item.original_text, 10),
    );

    const statusRow = el('div', 'card-actions');
    ['draft', 'published', 'hidden'].forEach((status) => {
      statusRow.append(button(status, () => {
        document.querySelector('#patchNoteStatus').value = status;
        renderPatchNoteStatusButtons(statusRow, status);
      }, `small-button${item.status === status ? ' is-active' : ''}`));
    });
    const hiddenStatus = el('input');
    hiddenStatus.type = 'hidden';
    hiddenStatus.id = 'patchNoteStatus';
    hiddenStatus.value = item.status || 'draft';
    fields.append(hiddenStatus, statusRow);

    const actions = el('div', 'card-actions');
    actions.append(
      button('插入模板', () => {
        document.querySelector('#patchNoteSummary').value = PATCH_NOTE_TEMPLATE;
      }, 'small-button'),
      button('取消', () => {
        state.patchNoteEditing = null;
        render();
      }, 'small-button'),
    );
    const submit = el('button', 'small-button is-active', item.id ? '保存公告' : '创建公告');
    submit.type = 'submit';
    actions.append(submit);
    form.append(fields, actions);
    return form;
  }

  function renderPatchNoteStatusButtons(row, activeStatus) {
    row.querySelectorAll('.small-button').forEach((buttonNode) => {
      buttonNode.classList.toggle('is-active', buttonNode.textContent === activeStatus);
    });
  }

  function adminInput(id, placeholder, value) {
    const input = el('input');
    input.id = id;
    input.placeholder = placeholder;
    input.value = value || '';
    return input;
  }

  function adminTextarea(id, placeholder, value, rows) {
    const textarea = el('textarea');
    textarea.id = id;
    textarea.placeholder = placeholder;
    textarea.value = value || '';
    textarea.rows = rows;
    return textarea;
  }

  function readPatchNoteForm() {
    return {
      id: state.patchNoteEditing?.id || null,
      title: document.querySelector('#patchNoteTitle')?.value?.trim() || '',
      version: document.querySelector('#patchNoteVersion')?.value?.trim() || '',
      published_at: document.querySelector('#patchNotePublishedAt')?.value?.trim() || '',
      source_url: document.querySelector('#patchNoteSourceUrl')?.value?.trim() || '',
      summary_markdown: document.querySelector('#patchNoteSummary')?.value?.trim() || '',
      original_text: document.querySelector('#patchNoteOriginal')?.value?.trim() || '',
      status: document.querySelector('#patchNoteStatus')?.value || 'draft',
    };
  }

  async function savePatchNote(payload) {
    const url = payload.id ? `/api/admin/patch-notes/${payload.id}` : '/api/admin/patch-notes';
    const method = payload.id ? 'PUT' : 'POST';
    await api(url, { method, body: JSON.stringify(payload) });
    await loadPatchNotes({ force: true });
    state.patchNoteEditing = null;
    setNotice('公告已保存');
    render();
  }
```

- [ ] **Step 6: Run admin UI tests**

Run: `pytest tests/test_ui_routes.py::test_pages_include_favicon_and_favicon_route_exists tests/test_ui_routes.py::test_admin_js_contains_patch_notes_workbench -v`

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git add templates/admin.html static/admin.js tests/test_ui_routes.py
git commit -m "feat: add admin patch notes workbench"
```

---

### Task 7: Final Verification

**Files:**
- Review: all changed files

- [ ] **Step 1: Run targeted test suite**

Run:

```bash
pytest tests/test_patch_notes.py tests/test_admin_patch_notes.py tests/test_schema.py tests/test_ui_routes.py tests/test_security.py -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Manually run local server**

Run:

```bash
python run_server.py
```

Expected: server starts at `http://127.0.0.1:5000`.

- [ ] **Step 4: Manual browser checks**

Open these URLs:

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/patch-notes`
- `http://127.0.0.1:5000/admin`

Expected:

- Homepage nav shows `更新公告`.
- `/patch-notes` loads without console errors.
- Admin has `更新公告` tab.
- Creating a published announcement makes it visible on `/patch-notes`.
- Detail page shows summary first and original text collapsed.

- [ ] **Step 5: Commit verification fixes if needed**

If verification requires edits:

```bash
git add <changed-files>
git commit -m "fix: polish patch notes feature"
```

If no edits are needed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: schema, public pages, admin CRUD, manual source/original handling, template-based summary parsing, red buff and green nerf styling, and tests are each covered by tasks.
- Scope control: automatic crawling is explicitly absent from the implementation tasks.
- Type consistency: data fields use `title`, `version`, `source_url`, `summary_markdown`, `original_text`, `status`, `published_at` across schema, service, API, and UI.

