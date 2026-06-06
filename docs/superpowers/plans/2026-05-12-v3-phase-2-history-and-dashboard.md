# V3 Phase 2 History And Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为登录用户补齐“最近浏览、最近复制、个人数据面板、举报处理反馈闭环”这四类账号价值能力，同时保留游客本地历史并在登录后同步到账号。

**Architecture:** 新增一个独立的“个人中心”页面 `/me` 承载数据面板、最近浏览、最近复制和我的举报；首页继续负责内容发现，不把个人信息流堆回首页。后端新增两张轻量历史表（只存登录账号侧历史），游客阶段的最近浏览和最近复制暂存 `localStorage`，登录/注册成功后通过单个同步接口入库，避免为游客历史引入复杂数据库身份模型。

**Tech Stack:** Flask、SQLite、Jinja2、Vanilla JS、Pytest

---

## Scope Decision

`修改V3.md` 的第二阶段原始愿景包括：

- 最近浏览
- 最近复制
- 我的数据面板
- 举报处理结果反馈
- 登录弹层替代跳转

本计划**只覆盖前四项**，明确**不包含登录弹层**。

### Why login modal is excluded here

登录弹层属于一套独立的交互基础设施问题：

- 要改首页和登录页的交互边界
- 要处理验证码、错误提示、焦点管理和移动端弹层滚动
- 要和 Phase 1 的“登录后自动续操作”整合

把它和“历史记录 + 个人中心”混做会显著放大回归范围。因此 Phase 2 只做账号价值补强，登录弹层单独留到下一份计划。

---

## Assumptions And Dependencies

1. **推荐先落地 Phase 1 再做本计划**
   - Phase 1 会补“我的收藏”和登录续操作
   - Phase 2 会自然复用这些交互

2. **如果 Phase 1 还没实施**
   - 本计划仍然可执行
   - 但 `auth-intent.js`、`favoritesTab`、游客引导文案这些 Phase 1 资产不能被假定为已经存在
   - 执行时要把本计划中涉及它们的地方改成基于当前代码的最小实现

3. **本计划不改线上部署方式**
   - 仍是 Flask + Gunicorn + SQLite
   - 不新增队列、不新增 Redis、不拆服务

---

## Current Code Map

### Existing backend that this phase can reuse

- `lineups.py`
  - 已有 `/api/lineups`
  - 已有 `/api/lineups/<id>`
  - 已有 `/api/lineups/<id>/copy`
  - 已有 `/api/lineups/<id>/report`
  - 复制计数逻辑已经稳定，但它只服务热度分，不适合直接当最近复制历史

- `auth.py`
  - 已有 `/api/login`、`/api/register`、`/api/me`
  - 登录/注册成功后返回 `csrf_token`
  - 适合在前端登录成功后立即发一次“游客历史同步”请求

- `db.py`
  - 已有 `favorites`、`reports`、`copy_events`、`visit_events`
  - 但没有“最近浏览历史”和“最近复制历史”的用户级明细表

- `admin.py`
  - 管理员已可处理举报并改变 `reports.status`
  - Phase 2 只需要把这些处理结果反馈给普通用户，不需要改后台处理流程

### Existing frontend that this phase must respect

- `templates/index.html` + `static/app.js`
  - 首页仍是主发现页
  - 当前没有“个人中心”入口

- `templates/auth.html` + `static/auth.js`
  - 登录成功后跳回 `/`
  - 适合同步游客历史后再跳转

- 目前没有独立的账号中心页
  - 这是本阶段新增的核心页面

### Existing constraints

- 测试数据库固定为 `test-lineups.sqlite3`
- 所有 pytest 需要串行跑，不能并行
- 当前没有前端测试框架
  - 本阶段仍采用：后端接口测试 + 模板断言 + 本地手工验证

---

## Product Decisions Locked In For Phase 2

### 1. “最近浏览”必须有一个明确的“查看”动作

当前站点只有阵容列表卡片，没有独立详情页。  
如果不引入“查看”动作，就无法准确定义“浏览过这套阵容”。

**本计划决定：**

- 新增公共详情页 `/lineup/<id>`
- 首页卡片增加“查看”按钮
- 只有进入详情页时，才记为“最近浏览”

这比“滚到屏幕里就算浏览过”更准确，也更可控。

### 2. 游客历史只保存在本地，不直接落游客数据库

**本计划决定：**

- 游客最近浏览 / 最近复制先存在 `localStorage`
- 登录或注册成功后，通过 `/api/me/history/sync` 同步到账号

这样做的好处：

- 不需要把游客 token 和历史明细表强绑定
- 不会引入更多匿名历史清理逻辑
- 更适合当前 SQLite 单机站点

### 3. 个人中心单独成页，不塞回首页

**本计划决定：**

- 新增 `/me`
- 页面内聚合：
  - 我的数据
  - 最近浏览
  - 最近复制
  - 我的举报
  - 我的阵容状态

原因：

- 首页继续保持内容发现简洁性
- 个人数据天然适合在单独页面浏览
- 代码边界更清晰：`account.js` 负责账号页，不继续膨胀 `app.js`

### 4. 举报反馈闭环先做“我的举报状态”，不做消息系统

**本计划决定：**

- 普通用户在 `/me` 看自己发起的举报
- 状态展示为：待处理 / 已处理 / 已驳回
- 如已处理，同时显示处理时间和阵容当前状态

这就足够形成第一版反馈闭环，不引入站内消息系统。

---

## File Structure For This Phase

### New files

- `history.py`
  - 最近浏览 / 最近复制历史的数据库读写 helper

- `templates/account.html`
  - 个人中心页面

- `templates/lineup_detail.html`
  - 阵容详情页

- `static/account.js`
  - 个人中心页面逻辑

- `static/lineup-detail.js`
  - 阵容详情页逻辑

- `static/history-store.js`
  - 本地 `localStorage` 最近浏览 / 最近复制存取与同步 helper

- `tests/test_history.py`
  - 历史记录与同步逻辑测试

- `tests/test_account.py`
  - 个人中心 API 测试

### Modified files

- `app.py`
  - 新增 `/me`
  - 新增 `/lineup/<id>` 详情页路由

- `db.py`
  - 新增 `recent_lineup_views`
  - 新增 `recent_lineup_copies`

- `lineups.py`
  - 新增详情视图相关接口
  - 新增用户历史与个人中心接口
  - 复制行为接入最近复制记录

- `templates/index.html`
  - 新增“个人中心”入口
  - 卡片增加“查看”入口
  - 挂载 `history-store.js`

- `templates/auth.html`
  - 挂载 `history-store.js`

- `static/app.js`
  - 新增“查看详情”跳转
  - 游客最近复制本地记录
  - 登录用户跳个人中心入口状态

- `static/auth.js`
  - 登录/注册成功后先同步游客历史，再跳转

- `static/styles.css`
  - 详情页、个人中心页、历史列表、状态标签样式

- `tests/test_ui_routes.py`
  - 新增 `/me`、`/lineup/<id>` 页面存在性和脚本断言

---

## Task 1: Add User-Owned Recent History Tables And Helper Module

**Files:**
- Create: `history.py`
- Modify: `db.py`
- Test: `tests/test_history.py`

- [ ] **Step 1: Write the failing schema and helper tests**

```python
from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_recent_history_tables_exist(app):
    with app.app_context():
        from db import table_names
        names = table_names()
        assert 'recent_lineup_views' in names
        assert 'recent_lineup_copies' in names


def test_record_recent_view_upserts_latest_timestamp(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='最近浏览阵容', code='#VIEW001').get_json()

    with client.application.app_context():
        from auth import current_user
        from history import record_recent_view, list_recent_views

        user = current_user()
        record_recent_view(user['id'], lineup['id'], created_at='2026-05-12 10:00:00')
        record_recent_view(user['id'], lineup['id'], created_at='2026-05-12 11:00:00')

        rows = list_recent_views(user['id'], limit=20)
        assert len(rows) == 1
        assert rows[0]['id'] == lineup['id']
        assert rows[0]['history_at'] == '2026-05-12 11:00:00'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_history.py -q -p no:cacheprovider`

Expected: FAIL，因为表和 helper 都还不存在。

- [ ] **Step 3: Write minimal implementation**

在 `db.py` 的 `SCHEMA` 中新增：

```sql
CREATE TABLE IF NOT EXISTS recent_lineup_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    lineup_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, lineup_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);

CREATE TABLE IF NOT EXISTS recent_lineup_copies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    lineup_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, lineup_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(lineup_id) REFERENCES lineups(id)
);
```

新增 `history.py`：

```python
from db import get_db, now_text
from lineups import _serialize
from scoring import score_map


def _upsert_history(table_name, user_id, lineup_id, created_at=None):
    timestamp = created_at or now_text()
    get_db().execute(
        f'''
        INSERT INTO {table_name} (user_id, lineup_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, lineup_id) DO UPDATE SET
            updated_at = excluded.updated_at
        ''',
        (user_id, lineup_id, timestamp, timestamp),
    )
    get_db().commit()


def record_recent_view(user_id, lineup_id, created_at=None):
    _upsert_history('recent_lineup_views', user_id, lineup_id, created_at=created_at)


def record_recent_copy(user_id, lineup_id, created_at=None):
    _upsert_history('recent_lineup_copies', user_id, lineup_id, created_at=created_at)
```

列表查询按 `updated_at DESC` 排序，并把 `updated_at AS history_at` 带回：

```python
def list_recent_views(user_id, limit=20):
    rows = get_db().execute(
        '''
        SELECT l.*, rv.updated_at AS history_at
        FROM recent_lineup_views rv
        JOIN lineups l ON l.id = rv.lineup_id
        WHERE rv.user_id = ? AND l.status != 'deleted'
        ORDER BY rv.updated_at DESC
        LIMIT ?
        ''',
        (user_id, limit),
    ).fetchall()
    scores = score_map()
    return [{**_serialize(row, scores, user=None), 'history_at': row['history_at']} for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_history.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db.py history.py tests/test_history.py
git commit -m "feat: add recent history tables and helpers"
```

---

## Task 2: Add Public Lineup Detail Page And Recent View Tracking

**Files:**
- Modify: `app.py`
- Modify: `lineups.py`
- Create: `templates/lineup_detail.html`
- Create: `static/lineup-detail.js`
- Modify: `templates/index.html`
- Modify: `static/app.js`
- Test: `tests/test_ui_routes.py`
- Test: `tests/test_history.py`

- [ ] **Step 1: Write the failing tests**

```python
from test_auth import register_user
from test_lineup_permissions import create_lineup, auth_headers


def test_lineup_detail_page_exists(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='详情页阵容', code='#DETAIL001').get_json()
    response = client.get(f"/lineup/{lineup['id']}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="lineupDetailApp"' in html
    assert 'lineup-detail.js' in html


def test_logged_in_view_endpoint_records_recent_view(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='浏览记录阵容', code='#DETAIL002').get_json()
    headers = auth_headers(client)

    response = client.post(f"/api/lineups/{lineup['id']}/view", headers=headers)

    assert response.status_code == 201
    history_payload = client.get('/api/me/recent-views', headers=headers).get_json()
    assert history_payload[0]['id'] == lineup['id']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py D:\1\codex\jcc\claude_project\tests\test_history.py -q -p no:cacheprovider -k "detail_page_exists or records_recent_view"`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `app.py` 中新增详情页路由：

```python
@app.get('/lineup/<int:lineup_id>')
def lineup_detail_page(lineup_id):
    return tracked_template_response('lineup_detail.html', 'lineup_detail', lineup_id=lineup_id)
```

在 `lineups.py` 中新增：

```python
from history import record_recent_view, list_recent_views


@lineups_bp.post('/api/lineups/<int:lineup_id>/view')
def record_lineup_view(lineup_id):
    user, error = login_required()
    if error:
        return error
    row = _lineup_row(lineup_id)
    if not row or row['status'] == 'deleted':
        return jsonify({'error': '阵容不存在'}), 404
    record_recent_view(user['id'], lineup_id)
    return jsonify({'ok': True}), 201


@lineups_bp.get('/api/me/recent-views')
def my_recent_views():
    user, error = login_required()
    if error:
        return error
    return jsonify(list_recent_views(user['id'], limit=20))
```

详情页模板挂载脚本：

```html
<main class="page-shell detail-page-shell">
  <div id="lineupDetailApp" data-lineup-id="{{ lineup_id }}">阵容加载中...</div>
</main>
<script src="{{ url_for('static', filename='history-store.js') }}" defer></script>
<script src="{{ url_for('static', filename='lineup-detail.js') }}" defer></script>
```

`static/lineup-detail.js` 的最小行为：

```javascript
const app = document.querySelector('#lineupDetailApp');
const lineupId = app?.dataset.lineupId;

async function bootDetail() {
  const me = await fetch('/api/me').then((response) => response.json());
  const lineup = await fetch(`/api/lineups/${lineupId}`).then((response) => response.json());
  renderLineup(lineup);
  if (me.user) {
    await fetch(`/api/lineups/${lineupId}/view`, { method: 'POST', headers: { 'X-CSRF-Token': me.csrf_token } });
  } else {
    window.jccHistoryStore.pushLocalView(lineup);
  }
}
```

首页列表补“查看”按钮：

```javascript
actions.append(button('查看', () => openLineupDetail(lineup.id)));

function openLineupDetail(lineupId) {
  window.location.href = `/lineup/${lineupId}`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py D:\1\codex\jcc\claude_project\tests\test_history.py -q -p no:cacheprovider -k "detail_page_exists or records_recent_view"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py lineups.py templates/lineup_detail.html static/lineup-detail.js templates/index.html static/app.js tests/test_ui_routes.py tests/test_history.py
git commit -m "feat: add lineup detail page and recent views"
```

---

## Task 3: Add Local Guest History Store And Login-Time Sync

**Files:**
- Create: `static/history-store.js`
- Modify: `static/app.js`
- Modify: `static/auth.js`
- Modify: `templates/index.html`
- Modify: `templates/auth.html`
- Modify: `lineups.py`
- Test: `tests/test_history.py`

- [ ] **Step 1: Write the failing sync tests**

```python
from test_auth import register_user, get_captcha
from test_lineup_permissions import create_lineup, auth_headers


def test_history_sync_merges_guest_views_and_copies_into_account(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup_a = create_lineup(client, name='浏览阵容', code='#SYNC001').get_json()
    lineup_b = create_lineup(client, name='复制阵容', code='#SYNC002').get_json()
    headers = auth_headers(client)

    payload = {
        'views': [{'lineup_id': lineup_a['id'], 'at': '2026-05-12 09:00:00'}],
        'copies': [{'lineup_id': lineup_b['id'], 'at': '2026-05-12 09:10:00'}],
    }
    response = client.post('/api/me/history/sync', json=payload, headers=headers)

    assert response.status_code == 200
    assert client.get('/api/me/recent-views', headers=headers).get_json()[0]['id'] == lineup_a['id']
    assert client.get('/api/me/recent-copies', headers=headers).get_json()[0]['id'] == lineup_b['id']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_history.py -q -p no:cacheprovider -k history_sync_merges_guest_views_and_copies_into_account`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `lineups.py` 中新增：

```python
from history import record_recent_copy, sync_recent_history, list_recent_copies


@lineups_bp.get('/api/me/recent-copies')
def my_recent_copies():
    user, error = login_required()
    if error:
        return error
    return jsonify(list_recent_copies(user['id'], limit=20))


@lineups_bp.post('/api/me/history/sync')
def sync_my_history():
    user, error = login_required()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    sync_recent_history(user['id'], payload.get('views', []), payload.get('copies', []))
    return jsonify({'ok': True})
```

在 `history.py` 中新增：

```python
def sync_recent_history(user_id, views, copies):
    for item in views[:20]:
        lineup_id = int(item['lineup_id'])
        record_recent_view(user_id, lineup_id, created_at=item.get('at'))
    for item in copies[:20]:
        lineup_id = int(item['lineup_id'])
        record_recent_copy(user_id, lineup_id, created_at=item.get('at'))
```

新增 `static/history-store.js`：

```javascript
(function () {
  const VIEW_KEY = 'jcc_guest_recent_views';
  const COPY_KEY = 'jcc_guest_recent_copies';
  const LIMIT = 20;

  function load(key) {
    try {
      return JSON.parse(localStorage.getItem(key) || '[]');
    } catch (_) {
      return [];
    }
  }

  function save(key, entries) {
    localStorage.setItem(key, JSON.stringify(entries.slice(0, LIMIT)));
  }

  function pushEntry(key, lineup) {
    const entries = load(key).filter((item) => item.lineup_id !== lineup.id);
    entries.unshift({ lineup_id: lineup.id, at: new Date().toISOString().slice(0, 19).replace('T', ' ') });
    save(key, entries);
  }

  async function syncToAccount(csrfToken) {
    const views = load(VIEW_KEY);
    const copies = load(COPY_KEY);
    if (!views.length && !copies.length) return;
    await fetch('/api/me/history/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
      body: JSON.stringify({ views, copies }),
    });
    localStorage.removeItem(VIEW_KEY);
    localStorage.removeItem(COPY_KEY);
  }

  window.jccHistoryStore = {
    pushLocalView(lineup) { pushEntry(VIEW_KEY, lineup); },
    pushLocalCopy(lineup) { pushEntry(COPY_KEY, lineup); },
    syncToAccount,
  };
})();
```

在 `static/app.js` 的复制成功路径中：

```javascript
if (state.user) {
  await api(`/api/lineups/${lineup.id}/copy`, { method: 'POST' });
} else {
  await fetch(`/api/lineups/${lineup.id}/copy`, { method: 'POST' });
  window.jccHistoryStore.pushLocalCopy(lineup);
}
```

在 `static/auth.js` 登录/注册成功后先同步游客历史：

```javascript
await window.jccHistoryStore.syncToAccount(state.csrfToken);
window.location.href = '/';
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_history.py -q -p no:cacheprovider -k history_sync_merges_guest_views_and_copies_into_account`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add history.py lineups.py static/history-store.js static/app.js static/auth.js templates/index.html templates/auth.html tests/test_history.py
git commit -m "feat: sync guest history after login"
```

---

## Task 4: Add Account Dashboard APIs

**Files:**
- Modify: `lineups.py`
- Create: `tests/test_account.py`

- [ ] **Step 1: Write the failing dashboard tests**

```python
from test_auth import register_user
from test_lineup_permissions import create_lineup, auth_headers


def test_account_dashboard_returns_creator_summary(client):
    register_user(client, username='creator', email='creator@example.com')
    lineup = create_lineup(client, name='作者阵容', code='#DASH001').get_json()
    headers = auth_headers(client)

    client.post(f"/api/lineups/{lineup['id']}/favorite", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/copy", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/like", headers=headers)
    client.post(f"/api/lineups/{lineup['id']}/report", json={'reason': '测试举报'}, headers=headers)

    payload = client.get('/api/me/dashboard', headers=headers).get_json()

    assert payload['published_lineups'] == 1
    assert 'received_likes' in payload
    assert 'received_favorites' in payload
    assert 'received_copies' in payload
    assert 'submitted_reports' in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_account.py -q -p no:cacheprovider -k account_dashboard_returns_creator_summary`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `lineups.py` 中新增：

```python
@lineups_bp.get('/api/me/dashboard')
def my_dashboard():
    user, error = login_required()
    if error:
        return error
    db = get_db()
    published_lineups = db.execute(
        "SELECT COUNT(*) AS c FROM lineups WHERE user_id = ? AND status != 'deleted'",
        (user['id'],),
    ).fetchone()['c']
    hidden_lineups = db.execute(
        "SELECT COUNT(*) AS c FROM lineups WHERE user_id = ? AND status = 'hidden'",
        (user['id'],),
    ).fetchone()['c']
    received_likes = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM likes
        JOIN lineups ON lineups.id = likes.lineup_id
        WHERE lineups.user_id = ?
        ''',
        (user['id'],),
    ).fetchone()['c']
    received_favorites = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM favorites
        JOIN lineups ON lineups.id = favorites.lineup_id
        WHERE lineups.user_id = ?
        ''',
        (user['id'],),
    ).fetchone()['c']
    received_copies = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM copy_events
        JOIN lineups ON lineups.id = copy_events.lineup_id
        WHERE lineups.user_id = ? AND copy_events.counted = 1
        ''',
        (user['id'],),
    ).fetchone()['c']
    submitted_reports = db.execute(
        'SELECT COUNT(*) AS c FROM reports WHERE reporter_user_id = ?',
        (user['id'],),
    ).fetchone()['c']
    pending_reports_on_my_lineups = db.execute(
        '''
        SELECT COUNT(*) AS c
        FROM reports
        JOIN lineups ON lineups.id = reports.lineup_id
        WHERE lineups.user_id = ? AND reports.status = 'pending'
        ''',
        (user['id'],),
    ).fetchone()['c']
    return jsonify({
        'published_lineups': published_lineups,
        'hidden_lineups': hidden_lineups,
        'received_likes': received_likes,
        'received_favorites': received_favorites,
        'received_copies': received_copies,
        'submitted_reports': submitted_reports,
        'pending_reports_on_my_lineups': pending_reports_on_my_lineups,
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_account.py -q -p no:cacheprovider -k account_dashboard_returns_creator_summary`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lineups.py tests/test_account.py
git commit -m "feat: add account dashboard api"
```

---

## Task 5: Add My Reports Feedback API

**Files:**
- Modify: `lineups.py`
- Modify: `tests/test_account.py`

- [ ] **Step 1: Write the failing reports-feedback test**

```python
from test_admin import login_admin
from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_my_reports_api_returns_status_after_admin_resolution(client):
    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='被举报阵容', code='#REPORT001').get_json()
    client.post('/api/logout')

    register_user(client, username='reporter', email='reporter@example.com')
    headers = auth_headers(client)
    report = client.post(
        f"/api/lineups/{lineup['id']}/report",
        json={'reason': '需要处理'},
        headers=headers,
    ).get_json()

    client.post('/api/logout')
    admin_headers = login_admin(client)
    client.post(
        f"/api/admin/reports/{report['id']}/resolve",
        json={'status': 'resolved', 'hide_lineup': True},
        headers=admin_headers,
    )

    client.post('/api/logout')
    client.post('/api/login', json={'account': 'reporter', 'password': 'abc123'})
    my_reports = client.get('/api/me/reports', headers=auth_headers(client)).get_json()

    assert my_reports[0]['status'] == 'resolved'
    assert my_reports[0]['lineup_status'] == 'hidden'
    assert my_reports[0]['handled_at'] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_account.py -q -p no:cacheprovider -k my_reports_api_returns_status_after_admin_resolution`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `lineups.py` 中新增：

```python
@lineups_bp.get('/api/me/reports')
def my_reports():
    user, error = login_required()
    if error:
        return error
    rows = get_db().execute(
        '''
        SELECT
            reports.id,
            reports.reason,
            reports.status,
            reports.created_at,
            reports.handled_at,
            lineups.id AS lineup_id,
            lineups.name AS lineup_name,
            lineups.status AS lineup_status
        FROM reports
        JOIN lineups ON lineups.id = reports.lineup_id
        WHERE reports.reporter_user_id = ?
        ORDER BY reports.id DESC
        ''',
        (user['id'],),
    ).fetchall()
    return jsonify([dict(row) for row in rows])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_account.py -q -p no:cacheprovider -k my_reports_api_returns_status_after_admin_resolution`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lineups.py tests/test_account.py
git commit -m "feat: add my reports feedback api"
```

---

## Task 6: Add Account Page UI And Navigation Entry

**Files:**
- Modify: `app.py`
- Create: `templates/account.html`
- Create: `static/account.js`
- Modify: `templates/index.html`
- Modify: `static/styles.css`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Write the failing page tests**

```python
from test_auth import register_user


def test_account_page_requires_login_and_contains_shell(client):
    assert client.get('/me').status_code == 401
    register_user(client, username='alice', email='alice@example.com')
    response = client.get('/me')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="accountApp"' in html
    assert 'account.js' in html
    assert '我的数据' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k account_page_requires_login_and_contains_shell`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `app.py` 中新增：

```python
from auth import login_required


@app.get('/me')
def account_page():
    user, error = login_required()
    if error:
        return error
    return tracked_template_response('account.html', 'account')
```

`templates/account.html`：

```html
<main class="page-shell account-page-shell">
  <nav class="nav-bar" aria-label="页面工具">
    <a class="ghost-link" href="/">返回阵容库</a>
    <button class="theme-toggle" id="themeToggle" type="button" aria-label="切换深浅色模式">
      <span id="themeIcon">☾</span>
      <span id="themeText">夜间模式</span>
    </button>
  </nav>

  <header class="hero">
    <p class="eyebrow">Account Center</p>
    <h1>个人中心</h1>
    <p class="hero-description">查看我的数据、最近浏览、最近复制和举报处理结果。</p>
  </header>

  <section class="panel">
    <div id="accountApp">个人中心加载中...</div>
  </section>
</main>
<script src="{{ url_for('static', filename='history-store.js') }}" defer></script>
<script src="{{ url_for('static', filename='account.js') }}" defer></script>
```

`static/account.js` 的初始结构：

```javascript
(async function () {
  const root = document.querySelector('#accountApp');
  if (!root) return;

  const me = await fetch('/api/me').then((response) => response.json());
  const headers = { 'X-CSRF-Token': me.csrf_token };
  const [dashboard, views, copies, reports, mine] = await Promise.all([
    fetch('/api/me/dashboard').then((response) => response.json()),
    fetch('/api/me/recent-views').then((response) => response.json()),
    fetch('/api/me/recent-copies').then((response) => response.json()),
    fetch('/api/me/reports').then((response) => response.json()),
    fetch('/api/lineups?view=mine&page=1&page_size=20').then((response) => response.json()),
  ]);
  renderAccount(dashboard, views, copies, reports, mine);
})();
```

首页导航加入口：

```html
<a class="ghost-link hidden" id="accountLink" href="/me">个人中心</a>
```

并在 `static/app.js` 的 `renderAuth()` 里控制显隐。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k account_page_requires_login_and_contains_shell`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py templates/account.html static/account.js templates/index.html static/styles.css tests/test_ui_routes.py
git commit -m "feat: add account center page"
```

---

## Task 7: Render Dashboard, History, My Reports And My Lineup Status In The Account Page

**Files:**
- Modify: `static/account.js`
- Modify: `static/styles.css`
- Test: `tests/test_account.py`
- Manual verify: `/me`

- [ ] **Step 1: Write the failing account-api coverage tests**

```python
def test_recent_copy_api_returns_latest_first(client):
    from test_auth import register_user
    from test_lineup_permissions import create_lineup, auth_headers

    register_user(client, username='creator', email='creator@example.com')
    first = create_lineup(client, name='旧复制', code='#COPY001').get_json()
    second = create_lineup(client, name='新复制', code='#COPY002').get_json()
    headers = auth_headers(client)

    client.post('/api/me/history/sync', json={
        'views': [],
        'copies': [
            {'lineup_id': first['id'], 'at': '2026-05-12 09:00:00'},
            {'lineup_id': second['id'], 'at': '2026-05-12 10:00:00'},
        ],
    }, headers=headers)

    payload = client.get('/api/me/recent-copies', headers=headers).get_json()
    assert payload[0]['id'] == second['id']
    assert payload[1]['id'] == first['id']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_account.py -q -p no:cacheprovider -k recent_copy_api_returns_latest_first`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`static/account.js` 中明确五个模块：

```javascript
function renderAccount(dashboard, views, copies, reports, minePayload) {
  const lineups = minePayload.items || minePayload;
  root.replaceChildren(
    renderSummaryCards(dashboard),
    renderHistorySection('最近浏览', views, '还没有最近浏览记录'),
    renderHistorySection('最近复制', copies, '还没有最近复制记录'),
    renderReportsSection(reports),
    renderMineSection(lineups),
  );
}
```

状态标签统一：

```javascript
const reportStatusText = {
  pending: '待处理',
  resolved: '已处理',
  dismissed: '已驳回',
};

const lineupStatusText = {
  normal: '正常',
  hidden: '已隐藏',
  deleted: '已删除',
};
```

样式 `static/styles.css` 增加：

```css
.account-page-shell {
  width: min(1180px, calc(100% - 36px));
}

.account-grid {
  display: grid;
  gap: 18px;
}

.account-section,
.history-card,
.report-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface-solid);
}

.status-pill.pending { color: #a46a12; }
.status-pill.resolved { color: #216a41; }
.status-pill.dismissed { color: #8b4d4d; }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_account.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Manual verification**

Run local server: `python D:\1\codex\jcc\claude_project\run_server.py`

Manual path A:
1. 未登录打开首页
2. 点击“查看”进入一套阵容详情
3. 不登录复制阵容码
4. 登录
5. 打开 `/me`
6. 能看到最近浏览和最近复制已同步到账号

Manual path B:
1. 登录用户发布 1-2 套阵容
2. 用另一个账号收藏、点赞、举报
3. 管理员处理其中一条举报
4. 返回举报账号的 `/me`
5. “我的举报”能看到最新状态与处理时间
6. 返回作者账号的 `/me`
7. “我的数据”中的收藏/点赞/复制统计正常

- [ ] **Step 6: Commit**

```bash
git add static/account.js static/styles.css tests/test_account.py
git commit -m "feat: render account dashboard and history"
```

---

## Task 8: Full Verification And Documentation Touch-Up

**Files:**
- Modify: `README.md` (only if route list changes need mention)
- Modify: `项目交接文档.md` (only if this phase is actually implemented)

- [ ] **Step 1: Run focused history tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_history.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 2: Run focused account tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_account.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 3: Run route and interaction tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py D:\1\codex\jcc\claude_project\tests\test_interactions.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 4: Run full suite serially**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Update docs if feature is actually implemented**

必须补充的文档项：

```markdown
- 新页面：`/me`、`/lineup/<id>`
- 新 API：
  - `GET /api/me/dashboard`
  - `GET /api/me/recent-views`
  - `GET /api/me/recent-copies`
  - `POST /api/me/history/sync`
  - `GET /api/me/reports`
  - `POST /api/lineups/<id>/view`
- 新表：
  - `recent_lineup_views`
  - `recent_lineup_copies`
```

- [ ] **Step 6: Commit**

```bash
git add README.md 项目交接文档.md
git commit -m "docs: document account history and dashboard"
```

---

## Why This Phase Matters

和 Phase 1 相比，Phase 2 解决的是“登录以后值不值得留下来”的问题。

### It creates durable account value

- 用户能找回最近看过的阵容
- 用户能找回最近复制过的阵容
- 用户能直观看到自己发布内容的表现
- 用户能知道自己举报的内容有没有被处理

### It turns the account from identity into utility

如果没有历史和面板，账号只是“一个能登录的东西”。  
有了历史和面板，账号才变成“一个能帮我记住、找回、同步和反馈”的东西。

### It prepares Phase 3 cleanly

做完这一步后，后续再加：

- 作者主页
- 热度趋势
- 转化漏斗埋点

都会更顺，因为：

- 已经有详情页
- 已经有个人中心
- 已经有历史模型

---

## Recommended Follow-Up After This Plan

下一份计划建议单独写：

- `2026-05-12-v3-phase-3-growth-and-discovery.md`

覆盖：

- 作者主页
- 热度趋势 / 上升榜
- 登录与转化漏斗事件埋点
- 首页推荐策略

