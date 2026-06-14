# Admin V4 Workbench Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前“单页全量后台”重构为“轻量概览首页 + 按需加载的 Tab 工作台”，显著降低初始化请求量，提升管理员处理举报、查阵容、管用户和看增长数据时的专注度与响应速度。

**Architecture:** 保留当前 Flask + SQLite + 原生前端结构，继续使用单个 `/admin` 页面壳子，但将内容拆为 `概览 / 举报 / 阵容 / 用户 / 增长分析 / 审计日志` 六个工作台 Tab。默认仅请求 `/api/me` 与新的 `/api/admin/overview`；列表模块改为进入 Tab 后再请求，用户与阵容管理默认空搜索态，增长分析与审计日志也按需加载。为控制复杂度，本轮**不做审计日志筛选**，并将“增长日聚合表”明确为后续优化项而非本次交付项。

**Tech Stack:** Flask、SQLite、原生 JavaScript、现有 `styles.css` 设计系统、Pytest。

---

## File Structure

### Existing files to modify

- `claude_project/admin.py`
  - 新增 `/api/admin/overview`
  - 为举报、阵容、用户、审计日志接口补分页能力
  - 保留 `/api/admin/growth` 但改为仅分析 Tab 使用
- `claude_project/static/admin.js`
  - 重写为 Tab 驱动的管理工作台
  - 初始化只加载登录态与概览
  - 各模块使用懒加载、缓存、防抖、请求取消
- `claude_project/templates/admin.html`
  - 加入顶部 Tab 导航占位
  - 首页壳子改为“驾驶舱 + 工作台容器”
- `claude_project/static/styles.css`
  - 补齐 V4 后台 Tab、概览卡、待办区、快捷入口、分页区、空状态、模块工作台样式
- `claude_project/tests/test_admin.py`
  - 新增/更新接口测试，覆盖 overview 与分页 contract
- `claude_project/tests/test_ui_routes.py`
  - 新增/更新前端壳子与 `admin.js` 关键字符串断言

### Optional file to modify if helper extraction becomes necessary

- `claude_project/analytics.py`
  - 仅当 overview 需要新增轻量统计聚合 helper 时修改；否则不动

### Explicitly out of scope for this plan

- `claude_project/app.py`
  - 不新增 `/admin/*` 多页面路由，本轮采用单页 Tab
- 审计日志筛选接口
- `admin_daily_growth_metrics` 预聚合表

---

### Task 1: Lock V4 contracts with failing tests

**Files:**
- Modify: `claude_project/tests/test_admin.py`
- Modify: `claude_project/tests/test_ui_routes.py`
- Test: `claude_project/tests/test_admin.py`
- Test: `claude_project/tests/test_ui_routes.py`

- [ ] **Step 1: Write failing backend tests for overview and paginated admin APIs**

```python
def test_admin_overview_returns_lightweight_dashboard_payload(client):
    register_user(client, username='alice', email='alice@example.com')
    client.post('/api/logout')
    headers = login_admin(client)

    data = client.get('/api/admin/overview', headers=headers).get_json()

    assert 'stats' in data
    assert 'traffic_7d' in data
    assert 'todos' in data
    assert data['stats']['pending_reports_count'] >= 0
    assert data['stats']['today_uv'] >= 0
    assert len(data['traffic_7d']) == 7


def test_admin_reports_supports_pagination(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='举报测试阵容', code='#REPORTPAGE01').get_json()
    client.post('/api/logout')

    for index in range(3):
        register_user(client, username=f'reporter{index}', email=f'reporter{index}@example.com')
        client.post(
            f"/api/lineups/{lineup['id']}/report",
            json={'reason': f'举报 {index}'},
            headers=auth_headers(client),
        )
        client.post('/api/logout')

    headers = login_admin(client)
    page_1 = client.get('/api/admin/reports?status=pending&page=1&page_size=2', headers=headers).get_json()
    page_2 = client.get('/api/admin/reports?status=pending&page=2&page_size=2', headers=headers).get_json()

    assert page_1['total'] == 3
    assert page_1['page'] == 1
    assert page_1['page_size'] == 2
    assert len(page_1['items']) == 2
    assert page_2['page'] == 2
    assert len(page_2['items']) == 1


def test_admin_lineups_and_users_support_paginated_results(client):
    register_user(client, username='owner', email='owner@example.com', nickname='作者')
    create_lineup(client, name='法师九五', code='#ADMINPAGE01')
    create_lineup(client, name='斗士九五', code='#ADMINPAGE02')
    client.post('/api/logout')

    headers = login_admin(client)
    lineups = client.get('/api/admin/lineups?q=九五&page=1&page_size=1', headers=headers).get_json()
    users = client.get('/api/admin/users?q=作者&page=1&page_size=10', headers=headers).get_json()

    assert lineups['total'] == 2
    assert len(lineups['items']) == 1
    assert users['total'] == 1
    assert users['items'][0]['nickname'] == '作者'


def test_admin_audit_logs_supports_pagination_without_filters(client):
    headers = login_admin(client)
    client.post('/api/admin/users', json={'username': 'eve', 'email': 'eve@example.com', 'password': 'abc123'}, headers=headers)

    payload = client.get('/api/admin/audit-logs?page=1&page_size=10', headers=headers).get_json()

    assert payload['page'] == 1
    assert payload['page_size'] == 10
    assert payload['total'] >= 1
    assert payload['items'][0]['action'] == 'create_user'
```

- [ ] **Step 2: Write failing UI shell tests for tabbed admin workbench**

```python
def test_admin_page_contains_tabbed_workbench_shell(client):
    login_response = client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    assert login_response.status_code == 200

    html = client.get('/admin').get_data(as_text=True)
    assert 'data-admin-tab="overview"' in html
    assert 'data-admin-tab="reports"' in html
    assert 'data-admin-tab="lineups"' in html
    assert 'data-admin-tab="users"' in html
    assert 'data-admin-tab="analytics"' in html
    assert 'data-admin-tab="audit"' in html


def test_admin_js_uses_overview_first_and_lazy_tab_loading():
    with open(r'D:\\1\\codex\\jcc\\claude_project\\static\\admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '/api/admin/overview' in js
    assert 'activeTab' in js
    assert 'AbortController' in js
    assert 'debounce' in js
    assert '搜索用户名、邮箱或昵称后开始查找' in js
    assert '输入阵容名、阵容码、作者后开始查找' in js
    assert 'pending_reports_count' in js
```

- [ ] **Step 3: Run tests to verify they fail for the right reason**

Run: `pytest claude_project/tests/test_admin.py claude_project/tests/test_ui_routes.py -q -p no:cacheprovider`

Expected:

- `test_admin_overview_returns_lightweight_dashboard_payload` fails because `/api/admin/overview` does not exist
- pagination tests fail because current APIs return arrays rather than `{items,total,...}`
- UI shell tests fail because `admin.html` and `admin.js` still use single-page full-load implementation

- [ ] **Step 4: Do not write production code yet**

```text
确认红灯后再进入 Task 2；此时不修改后端和前端代码。
```

---

### Task 2: Build the lightweight overview and paginated backend contracts

**Files:**
- Modify: `claude_project/admin.py`
- Modify: `claude_project/tests/test_admin.py`
- Optional Modify: `claude_project/analytics.py`
- Test: `claude_project/tests/test_admin.py`

- [ ] **Step 1: Add small pagination helpers in `admin.py`**

```python
def _parse_page():
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    return page if page > 0 else 1


def _parse_page_size(default=20, maximum=100):
    try:
        page_size = int(request.args.get('page_size', default))
    except (TypeError, ValueError):
        page_size = default
    page_size = page_size if page_size > 0 else default
    return min(page_size, maximum)


def _paginate_rows(base_sql, count_sql, params, serializer=dict, default_page_size=20):
    page = _parse_page()
    page_size = _parse_page_size(default=default_page_size)
    total = get_db().execute(count_sql, params).fetchone()['c']
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size
    rows = get_db().execute(f'{base_sql} LIMIT ? OFFSET ?', [*params, page_size, offset]).fetchall()
    return {
        'items': [serializer(row) for row in rows],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }
```

- [ ] **Step 2: Add `/api/admin/overview` and keep payload intentionally small**

```python
@admin_bp.get('/api/admin/overview')
def admin_overview():
    admin, error = admin_required()
    if error:
        return error

    db = get_db()
    today = now_text()[:10]
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    pending_reports_count = db.execute(
        "SELECT COUNT(*) AS c FROM reports WHERE status = 'pending'"
    ).fetchone()['c']
    hidden_lineups_count = db.execute(
        "SELECT COUNT(*) AS c FROM lineups WHERE status = 'hidden'"
    ).fetchone()['c']
    recent_audit_count = db.execute(
        "SELECT COUNT(*) AS c FROM audit_logs WHERE created_at LIKE ?",
        (f'{today}%',),
    ).fetchone()['c']

    return jsonify({
        'stats': {
            'today_uv': daily_uv_count(today),
            'yesterday_uv': daily_uv_count(yesterday),
            'today_users': db.execute("SELECT COUNT(*) AS c FROM users WHERE role != 'admin' AND created_at LIKE ?", (f'{today}%',)).fetchone()['c'],
            'today_logins': db.execute(
                '''
                SELECT COUNT(DISTINCT le.user_id) AS c
                FROM login_events le
                JOIN users u ON u.id = le.user_id
                WHERE le.success = 1 AND le.created_at LIKE ? AND u.role != 'admin'
                ''',
                (f'{today}%',),
            ).fetchone()['c'],
            'total_users': db.execute("SELECT COUNT(*) AS c FROM users WHERE role != 'admin'").fetchone()['c'],
            'pending_reports_count': pending_reports_count,
        },
        'traffic_7d': last_7_days_uv(),
        'todos': {
            'pending_reports_count': pending_reports_count,
            'hidden_lineups_count': hidden_lineups_count,
            'recent_audit_count': recent_audit_count,
        },
    })
```

- [ ] **Step 3: Convert report, lineup, user, audit APIs to paginated payloads**

```python
@admin_bp.get('/api/admin/reports')
def admin_reports():
    admin, error = admin_required()
    if error:
        return error
    status = request.args.get('status', 'pending').strip()
    params = []
    from_sql = '''
        FROM reports
        JOIN users AS reporter ON reporter.id = reports.reporter_user_id
        LEFT JOIN users AS handler ON handler.id = reports.handled_by
        JOIN lineups ON lineups.id = reports.lineup_id
        LEFT JOIN users AS owner ON owner.id = lineups.user_id
    '''
    if status in {'pending', 'resolved', 'dismissed'}:
        from_sql += ' WHERE reports.status = ?'
        params.append(status)
    base_sql = '''
        SELECT reports.*, reporter.username AS reporter_username, reporter.nickname AS reporter_nickname,
               handler.username AS handled_by_username, handler.nickname AS handled_by_nickname,
               lineups.name AS lineup_name, lineups.code AS lineup_code, lineups.status AS lineup_status,
               owner.username AS owner_username, owner.nickname AS owner_nickname
    ''' + from_sql + ' ORDER BY reports.id DESC'
    count_sql = 'SELECT COUNT(*) AS c ' + from_sql
    return jsonify(_paginate_rows(base_sql, count_sql, params, serializer=dict, default_page_size=20))
```

```python
@admin_bp.get('/api/admin/lineups')
def admin_lineups():
    admin, error = admin_required()
    if error:
        return error
    q = request.args.get('q', '').strip()
    params = []
    where_sql = '''
        FROM lineups
        LEFT JOIN users ON users.id = lineups.user_id
        WHERE lineups.status != 'deleted'
    '''
    if q:
        where_sql += '''
            AND (lineups.name LIKE ? OR lineups.code LIKE ? OR users.username LIKE ? OR users.nickname LIKE ?)
        '''
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%'])
    scores = score_map()
    base_sql = 'SELECT lineups.* ' + where_sql + ' ORDER BY lineups.id DESC'
    count_sql = 'SELECT COUNT(*) AS c ' + where_sql
    return jsonify(_paginate_rows(base_sql, count_sql, params, serializer=lambda row: _serialize(row, scores, user=admin, admin=True), default_page_size=20))
```

```python
@admin_bp.get('/api/admin/users')
def admin_users():
    admin, error = admin_required()
    if error:
        return error
    q = request.args.get('q', '').strip()
    params = []
    from_sql = 'FROM users'
    if q:
        from_sql += ' WHERE username LIKE ? OR email LIKE ? OR nickname LIKE ?'
        params = [f'%{q}%', f'%{q}%', f'%{q}%']
    base_sql = 'SELECT id, username, email, nickname, role, status, created_at, updated_at, last_login_at ' + from_sql + ' ORDER BY id DESC'
    count_sql = 'SELECT COUNT(*) AS c ' + from_sql
    return jsonify(_paginate_rows(base_sql, count_sql, params, serializer=dict, default_page_size=20))
```

```python
@admin_bp.get('/api/admin/audit-logs')
def admin_audit_logs():
    admin, error = admin_required()
    if error:
        return error
    base_sql = 'SELECT * FROM audit_logs ORDER BY id DESC'
    count_sql = 'SELECT COUNT(*) AS c FROM audit_logs'
    return jsonify(_paginate_rows(base_sql, count_sql, [], serializer=dict, default_page_size=30))
```

- [ ] **Step 4: Run the targeted backend tests and make them green**

Run: `pytest claude_project/tests/test_admin.py -q -p no:cacheprovider`

Expected:

- overview payload test passes
- paginated reports / lineups / users / audit logs tests pass
- existing admin mutation tests remain green

- [ ] **Step 5: Keep current growth implementation, but mark pre-aggregation as deferred**

```text
本轮不引入 admin_daily_growth_metrics 表；继续复用现有 /api/admin/growth?date=YYYY-MM-DD，
但只在“增长分析”Tab 被点开时请求。
```

---

### Task 3: Refactor the admin shell into overview-first tabs with lazy loading

**Files:**
- Modify: `claude_project/templates/admin.html`
- Modify: `claude_project/static/admin.js`
- Modify: `claude_project/tests/test_ui_routes.py`
- Test: `claude_project/tests/test_ui_routes.py`

- [ ] **Step 1: Change `admin.html` from single content block to tabbed workbench shell**

```html
<section class="panel admin-panel-shell">
  <div class="admin-tab-bar" id="adminTabBar" role="tablist" aria-label="后台模块">
    <button class="admin-tab is-active" data-admin-tab="overview" type="button">概览</button>
    <button class="admin-tab" data-admin-tab="reports" type="button">举报</button>
    <button class="admin-tab" data-admin-tab="lineups" type="button">阵容</button>
    <button class="admin-tab" data-admin-tab="users" type="button">用户</button>
    <button class="admin-tab" data-admin-tab="analytics" type="button">增长分析</button>
    <button class="admin-tab" data-admin-tab="audit" type="button">审计日志</button>
  </div>
  <div id="adminApp">后台数据加载中...</div>
</section>
```

- [ ] **Step 2: Replace eager `loadData()` with overview-first boot sequence**

```javascript
const state = {
  me: null,
  csrfToken: '',
  activeTab: 'overview',
  overview: null,
  growth: null,
  growthDate: todayInputValue(),
  reports: { items: [], total: 0, page: 1, pageSize: 20, status: 'pending', loadedAt: 0 },
  lineups: { items: [], total: 0, page: 1, pageSize: 20, query: '', searched: false, loadedAt: 0 },
  users: { items: [], total: 0, page: 1, pageSize: 20, query: '', searched: false, loadedAt: 0 },
  audit: { items: [], total: 0, page: 1, pageSize: 30, loadedAt: 0 },
  cacheTtlMs: 30000,
  controllers: {},
  notice: '',
  passwordUser: null,
  passwordError: '',
};

async function boot() {
  const me = await fetch('/api/me').then((response) => response.json());
  state.me = me.user;
  state.csrfToken = me.csrf_token;
  await loadOverview({ force: true });
  render();
}
```

- [ ] **Step 3: Add lazy tab loaders with cache and `AbortController`**

```javascript
async function loadOverview({ force = false } = {}) {
  if (!force && state.overview && Date.now() - state.overview.loadedAt < state.cacheTtlMs) return;
  const payload = await api('/api/admin/overview');
  state.overview = { ...payload, loadedAt: Date.now() };
}

async function loadReports({ force = false } = {}) {
  if (!force && Date.now() - state.reports.loadedAt < state.cacheTtlMs) return;
  const query = new URLSearchParams({
    status: state.reports.status,
    page: String(state.reports.page),
    page_size: String(state.reports.pageSize),
  });
  const payload = await api(`/api/admin/reports?${query.toString()}`);
  state.reports = { ...state.reports, ...payload, loadedAt: Date.now() };
}

async function loadLineups({ force = false } = {}) {
  if (!state.lineups.searched) return;
  abortRequest('lineups');
  state.controllers.lineups = new AbortController();
  const query = new URLSearchParams({
    q: state.lineups.query,
    page: String(state.lineups.page),
    page_size: String(state.lineups.pageSize),
  });
  const payload = await api(`/api/admin/lineups?${query.toString()}`, { signal: state.controllers.lineups.signal });
  state.lineups = { ...state.lineups, ...payload, loadedAt: Date.now() };
}
```

```javascript
function abortRequest(key) {
  if (state.controllers[key]) state.controllers[key].abort();
}

function debounce(callback, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => callback(...args), delay);
  };
}
```

- [ ] **Step 4: Render each tab as a focused workspace, not an all-in-one wall**

```javascript
function render() {
  syncHeader();
  syncTabs();
  root.replaceChildren();
  if (state.notice) root.append(el('div', 'message admin-inline-message', state.notice));
  if (state.activeTab === 'overview') root.append(renderOverviewDashboard());
  if (state.activeTab === 'reports') root.append(renderReportsWorkspace());
  if (state.activeTab === 'lineups') root.append(renderLineupsWorkspace());
  if (state.activeTab === 'users') root.append(renderUsersWorkspace());
  if (state.activeTab === 'analytics') root.append(renderAnalyticsWorkspace());
  if (state.activeTab === 'audit') root.append(renderAuditWorkspace());
  renderPasswordDialog();
}
```

```javascript
function renderOverviewDashboard() {
  const wrap = el('div', 'admin-dashboard');
  wrap.append(
    renderOverviewStats(),
    renderTrafficOverview(),
    renderTodoPanel(),
    renderQuickLinks(),
  );
  return wrap;
}
```

- [ ] **Step 5: Give lineups and users an empty default state until search happens**

```javascript
function renderLineupsWorkspace() {
  const { section, body } = createModule('阵容管理', '搜索阵容名、阵容码、作者后再加载结果', lineupSearchControls());
  if (!state.lineups.searched) {
    body.append(empty('输入阵容名、阵容码、作者后开始查找'));
    return section;
  }
  body.append(renderLineupList(), renderPagination('lineups'));
  return section;
}

function renderUsersWorkspace() {
  const { section, body } = createModule('用户管理', '搜索用户名、邮箱或昵称后再加载结果', userSearchControls());
  if (!state.users.searched) {
    body.append(empty('搜索用户名、邮箱或昵称后开始查找'));
    return section;
  }
  body.append(renderUserList(), renderPagination('users'));
  return section;
}
```

- [ ] **Step 6: Keep analytics and audit lazy as independent tabs**

```javascript
async function activateTab(tabKey) {
  state.activeTab = tabKey;
  if (tabKey === 'overview') await loadOverview();
  if (tabKey === 'reports') await loadReports({ force: true });
  if (tabKey === 'analytics') await loadGrowth({ force: true });
  if (tabKey === 'audit') await loadAudit({ force: true });
  render();
}
```

- [ ] **Step 7: Run UI-focused tests and make them green**

Run: `pytest claude_project/tests/test_ui_routes.py -q -p no:cacheprovider`

Expected:

- admin shell tests pass
- `admin.js` contains `/api/admin/overview`, `activeTab`, `AbortController`, `debounce`
- no references remain to initial eager loading of users / lineups / reports / logs on first paint

---

### Task 4: Apply V4 dashboard layout and workspace styling

**Files:**
- Modify: `claude_project/static/styles.css`
- Modify: `claude_project/templates/admin.html`
- Modify: `claude_project/static/admin.js`
- Test: `claude_project/tests/test_ui_routes.py`

- [ ] **Step 1: Add V4 admin tab bar and overview dashboard layout styles**

```css
.admin-tab-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}

.admin-tab {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface-solid);
  color: var(--muted);
  padding: 10px 16px;
}

.admin-tab.is-active {
  background: var(--accent);
  color: #fffaf5;
  border-color: transparent;
}

.admin-dashboard {
  display: grid;
  gap: 18px;
}

.admin-dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
```

- [ ] **Step 2: Add focused workspace containers instead of fixed-height wall cards**

```css
.admin-workspace {
  display: grid;
  gap: 16px;
}

.admin-workspace-panel {
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  background: var(--surface);
  box-shadow: var(--shadow);
}

.admin-pagination {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
}

.admin-empty-search {
  padding: 44px 20px;
  text-align: center;
  color: var(--muted);
}
```

- [ ] **Step 3: Simplify homepage density and keep lists out of the overview tab**

```text
概览页仅渲染：
- 4~5 张 KPI 卡
- 7 日访问趋势
- 待办事项
- 快捷入口

举报、阵容、用户、增长分析、审计日志都不在概览页直接挂载。
```

- [ ] **Step 4: Add mobile-safe tab and dashboard responsive rules**

```css
@media (max-width: 860px) {
  .admin-dashboard-grid {
    grid-template-columns: 1fr;
  }

  .admin-tab-bar {
    overflow-x: auto;
    flex-wrap: nowrap;
    padding-bottom: 4px;
  }
}
```

- [ ] **Step 5: Run UI tests again after CSS and shell adjustments**

Run: `pytest claude_project/tests/test_ui_routes.py -q -p no:cacheprovider`

Expected:

- admin shell string checks still pass
- no regression in existing favicon / admin shell tests

---

### Task 5: Full verification and rollout notes

**Files:**
- Modify: `claude_project/tests/test_admin.py`
- Modify: `claude_project/tests/test_ui_routes.py`
- Optional Modify: `claude_project/项目交接文档.md`
- Test: `claude_project/tests`

- [ ] **Step 1: Run the focused admin test suite**

Run: `pytest claude_project/tests/test_admin.py claude_project/tests/test_ui_routes.py -q -p no:cacheprovider`

Expected: all pass

- [ ] **Step 2: Run the full project test suite**

Run: `pytest claude_project/tests -q -p no:cacheprovider`

Expected: all pass with no admin regression

- [ ] **Step 3: Manually verify the V4 interaction sequence locally**

```text
1. 打开 /admin
2. 确认首屏只请求 /api/me 与 /api/admin/overview
3. 切到“举报”Tab，确认这时才请求 /api/admin/reports
4. 切到“阵容”Tab，确认默认空搜索态，不主动请求列表
5. 输入阵容关键词，确认带分页请求 /api/admin/lineups
6. 切到“用户”Tab，确认默认空搜索态，搜索后才请求
7. 切到“增长分析”Tab，确认这时才请求 /api/admin/growth
8. 切到“审计日志”Tab，确认这时才请求 /api/admin/audit-logs
```

- [ ] **Step 4: Update handoff docs only if the UI contract changed materially**

```text
如最终交付采用 Tab 工作台并引入 /api/admin/overview，
则在 项目交接文档.md 中补充：
- 管理后台模块结构
- 概览接口说明
- 列表接口分页 contract
```

- [ ] **Step 5: Do not add audit log filtering in this iteration**

```text
本轮明确不实现：
- /api/admin/audit-logs?action=...
- /api/admin/audit-logs?from=...&to=...

只实现分页与按需加载。
```

---

## Notes for execution

- 采用 **Tab 工作台** 而不是多路由拆页，是为了在不动 `app.py` 路由结构的前提下，先完成最关键的“按需加载 + 信息解耦”。
- `overview` 是本次 V4 改造的核心，请保持 payload 小而稳定，不要把完整举报列表、用户列表、阵容列表塞回去。
- `lineups` 与 `users` 的“默认空搜索态”是本次性能优化的关键，不要为了“看起来有内容”又把首次加载退回全量请求。
- 增长分析仍使用现有 `growth_summary(target_date=...)`，当前数据量下可接受；若未来增长事件明显增多，再另起计划做 `admin_daily_growth_metrics` 聚合表。
