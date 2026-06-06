# Daily UV Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add daily site UV tracking for guests and logged-in users, and surface the numbers in the admin dashboard with a cleaner admin layout.

**Architecture:** Keep tracking inside the existing Flask + SQLite app. Record visits only for HTML page routes, store deduplicated visitor rows in a new `visit_events` table, and extend `/api/admin/stats` plus the admin frontend to present UV metrics and a 7-day trend.

**Tech Stack:** Flask, SQLite, pytest, vanilla JavaScript, existing `styles.css`

---

### Task 1: Add schema and tracking tests

**Files:**
- Modify: `db.py`
- Modify: `tests/test_schema.py`
- Create: `tests/test_visits.py`

- [ ] **Step 1: Write failing schema and visit tracking tests**

```python
def test_schema_creates_visit_events_table(client):
    assert 'visit_events' in client.application.get_table_names()


def test_home_page_sets_visitor_cookie_and_records_guest_uv(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'visitor_token=' in response.headers.get('Set-Cookie', '')
    with client.application.app_context():
        from db import get_db
        row = get_db().execute('SELECT visitor_kind, page_key FROM visit_events').fetchone()
        assert row['visitor_kind'] == 'ip_fallback'
        assert row['page_key'] == 'home'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_schema.py D:\1\codex\jcc\claude_project\tests\test_visits.py -q -p no:cacheprovider`
Expected: FAIL because `visit_events` and visit recording do not exist.

- [ ] **Step 3: Implement the visit table and helper module**

```python
CREATE TABLE IF NOT EXISTS visit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_date TEXT NOT NULL,
    visitor_key TEXT NOT NULL,
    visitor_kind TEXT NOT NULL,
    user_id INTEGER,
    visitor_token TEXT,
    ip_address TEXT,
    page_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(visit_date, page_key, visitor_key)
);
```

```python
def record_page_visit(page_key, user=None):
    incoming_token = request.cookies.get(VISITOR_COOKIE_NAME)
    ip = get_client_ip()
    visitor_kind, visitor_key = resolve_visitor_identity(user, incoming_token, ip)
    db.execute('INSERT OR IGNORE INTO visit_events (...) VALUES (...)', (...))
```

- [ ] **Step 4: Re-run the schema and visit tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_schema.py D:\1\codex\jcc\claude_project\tests\test_visits.py -q -p no:cacheprovider`
Expected: PASS

### Task 2: Track only page visits and dedupe correctly

**Files:**
- Modify: `app.py`
- Create: `visits.py`
- Test: `tests/test_visits.py`

- [ ] **Step 1: Extend the visit tests for dedupe and route scope**

```python
def test_guest_with_cookie_counts_once_per_day(client):
    first = client.get('/')
    cookie = first.headers['Set-Cookie'].split(';', 1)[0]
    client.get('/', headers={'Cookie': cookie})
    with client.application.app_context():
        from db import get_db
        count = get_db().execute("SELECT COUNT(*) AS c FROM visit_events WHERE page_key = 'home'").fetchone()['c']
        assert count == 1


def test_api_requests_do_not_create_visit_rows(client):
    client.get('/api/lineups')
    with client.application.app_context():
        from db import get_db
        count = get_db().execute('SELECT COUNT(*) AS c FROM visit_events').fetchone()['c']
        assert count == 0


def test_logged_in_user_uses_user_identity_for_uv(client):
    register_user(client)
    client.get('/')
    with client.application.app_context():
        from db import get_db
        row = get_db().execute('SELECT visitor_kind, visitor_key FROM visit_events ORDER BY id DESC LIMIT 1').fetchone()
        assert row['visitor_kind'] == 'user'
        assert row['visitor_key'].startswith('user:')
```

- [ ] **Step 2: Run the visit tests to verify failure**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_visits.py -q -p no:cacheprovider`
Expected: FAIL until the tracked page wrapper is wired into `app.py`.

- [ ] **Step 3: Wire tracked page rendering into HTML routes only**

```python
@app.get('/')
def index():
    return tracked_template_response('index.html', 'home')
```

```python
@app.get('/auth')
def auth_page():
    return tracked_template_response('auth.html', 'auth')
```

- [ ] **Step 4: Re-run the visit tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_visits.py -q -p no:cacheprovider`
Expected: PASS

### Task 3: Extend admin stats with UV metrics

**Files:**
- Modify: `admin.py`
- Test: `tests/test_admin.py`
- Test: `tests/test_visits.py`

- [ ] **Step 1: Write failing stats tests**

```python
def test_admin_stats_include_uv_metrics(client):
    client.get('/')
    headers = login_admin(client)
    data = client.get('/api/admin/stats', headers=headers).get_json()
    assert 'today_uv' in data
    assert 'yesterday_uv' in data
    assert 'last_7_days_uv' in data
```

- [ ] **Step 2: Run admin and visit tests to verify failure**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_admin.py D:\1\codex\jcc\claude_project\tests\test_visits.py -q -p no:cacheprovider`
Expected: FAIL because `/api/admin/stats` does not return UV fields.

- [ ] **Step 3: Add UV aggregation helpers to admin stats**

```python
today_uv = db.execute('SELECT COUNT(DISTINCT visitor_key) AS c FROM visit_events WHERE visit_date = ?', (today,)).fetchone()['c']
yesterday_uv = db.execute('SELECT COUNT(DISTINCT visitor_key) AS c FROM visit_events WHERE visit_date = ?', (yesterday,)).fetchone()['c']
```

- [ ] **Step 4: Re-run admin and visit tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_admin.py D:\1\codex\jcc\claude_project\tests\test_visits.py -q -p no:cacheprovider`
Expected: PASS

### Task 4: Improve admin dashboard layout and show UV data

**Files:**
- Modify: `static/admin.js`
- Modify: `static/styles.css`
- Modify: `templates/admin.html`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Write a failing UI route test for the traffic module anchor**

```python
def test_admin_page_contains_dialog_and_dashboard_roots(client):
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    html = client.get('/admin').get_data(as_text=True)
    assert 'id="adminDialogRoot"' in html
    assert 'id="adminApp"' in html
```

- [ ] **Step 2: Implement the UV cards and 7-day trend module with cleaner layout**

```javascript
['今日 UV', state.stats.today_uv || 0, '全站独立访问']
['昨日 UV', state.stats.yesterday_uv || 0, '用于观察波动']
```

```javascript
grid.append(renderTraffic(), renderReports(), renderLineups(), renderUsers(), renderLogs())
```

```css
.admin-traffic-list { display: grid; gap: 10px; }
.admin-traffic-item { display: flex; justify-content: space-between; }
```

- [ ] **Step 3: Re-run the route tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: PASS

### Task 5: Full verification

**Files:**
- Modify: `app.py`
- Modify: `admin.py`
- Modify: `db.py`
- Create: `visits.py`
- Modify: `static/admin.js`
- Modify: `static/styles.css`
- Modify: `templates/admin.html`
- Modify: `tests/test_admin.py`
- Modify: `tests/test_schema.py`
- Create: `tests/test_visits.py`

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 2: Start the local preview service**

Run: `python D:\1\codex\jcc\claude_project\run_server.py`
Expected: app listens on `http://127.0.0.1:5000`

- [ ] **Step 3: Commit after review if requested**

```bash
git -C D:\1\codex\jcc\jcc_git add .
git -C D:\1\codex\jcc\jcc_git commit -m "feat: add daily uv tracking and admin analytics"
```
