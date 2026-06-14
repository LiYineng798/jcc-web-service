# V3 Phase 1 Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不重构站点架构的前提下，先落地 V3 中“登录触发点 + 登录收益表达 + 我的收藏”这批高性价比优化，提升游客转化率并增强账号价值感知。

**Architecture:** 保持当前 Flask + SQLite + 原生前端脚本结构，不引入新服务、不改部署方式。第一阶段复用现有 `/auth` 页面，通过前端 `sessionStorage` 保存待续操作，登录成功后回到首页自动续上动作；同时在现有 `/api/lineups` 基础上扩展 `view=favorites`，避免新开一套列表协议。

**Tech Stack:** Flask、SQLite、Jinja2、Vanilla JS、Pytest

---

## Scope Split

`修改V3.md` 涵盖多个相互独立的子系统，不能在一个实现批次里全部做完，否则测试和回归成本会失控。建议拆成三期：

1. **Phase 1：转化优化（本计划）**
   - 游客点击点赞 / 收藏时触发登录引导
   - 登录成功后自动继续刚才操作
   - 首页与登录页前置账号权益文案
   - “我的收藏”视图
   - “新增阵容 / 我的 / 我的收藏”登录续接

2. **Phase 2：账号价值增强**
   - 最近浏览
   - 最近复制
   - 登录弹层替代纯跳转
   - 我的数据面板
   - 举报处理结果反馈

3. **Phase 3：内容深度与增长分析**
   - 作者主页
   - 热度趋势 / 动态推荐
   - 登录转化漏斗埋点

本计划只覆盖 **Phase 1**。

---

## Current Code Map

### Frontend

- `static/app.js`
  - 首页列表、分页、复制、点赞、收藏、举报、登录状态渲染
  - 现状问题：游客看不到点赞 / 收藏 / 举报按钮，无法形成“高意图触发登录”
- `static/auth.js`
  - 登录注册页逻辑
  - 现状问题：登录成功后固定跳转 `/`，不会恢复被打断动作
- `templates/index.html`
  - 首页结构
  - 现状问题：没有“我的收藏”入口，账号权益文案偏弱
- `templates/auth.html`
  - 登录注册页结构
  - 现状问题：仅有基础文案，没有明确强调账号收益
- `static/styles.css`
  - 首页、登录页、后台统一样式
  - 本期需要补收藏标签、登录引导提示样式

### Backend

- `lineups.py`
  - 已有列表接口 `/api/lineups`
  - 已有收藏接口 `/api/lineups/<id>/favorite`
  - 已有点赞接口 `/api/lineups/<id>/like`
  - 已有举报接口 `/api/lineups/<id>/report`
  - 现状问题：没有“我的收藏”视图
- `auth.py`
  - 已有 `/api/login`、`/api/register`、`/api/me`
  - 现状问题：没有后登录续接动作的服务器状态，第一阶段建议前端存储解决
- `db.py`
  - 已有 `favorites` 表，足以支撑“我的收藏”
  - 当前没有适合“最近浏览 / 最近复制明细”的表；这部分推迟到 Phase 2

### Tests

- `tests/test_interactions.py`
  - 适合扩展收藏 / 点赞相关接口行为
- `tests/test_ui_routes.py`
  - 适合断言首页和登录页新增入口、文案、脚本引用
- 当前没有 JS 单元测试框架
  - 第一阶段对前端流程用“模板断言 + 接口测试 + 手工验证”组合覆盖

---

## UX Decisions Locked In For Phase 1

1. **不在 Phase 1 直接做内嵌登录弹层**
   - 仍然跳转到 `/auth`
   - 原因：当前项目没有前端组件系统，直接做 modal 登录会显著增大实现面

2. **待续操作存前端 `sessionStorage`**
   - 作用域只要求“同一浏览会话内能继续”
   - 不需要数据库、不需要服务器端 pending state

3. **“我的收藏”复用 `/api/lineups`**
   - 通过 `view=favorites`
   - 保持和 `view=all` / `view=mine` 一致的列表协议与分页协议

4. **游客也显示“点赞 / 收藏”按钮**
   - 点击后不直接报错
   - 先弹轻量登录收益提示，再跳转 `/auth`
   - 这是第一阶段最核心的转化触发点

5. **“举报”先保持登录后使用**
   - 如果游客点击举报，也走同一套待续逻辑
   - 但 Phase 1 优先优化点赞 / 收藏 / 我的收藏 / 新增阵容

---

## Task 1: Add Favorites View To The Existing List API

**Files:**
- Modify: `lineups.py`
- Test: `tests/test_interactions.py`

- [ ] **Step 1: Write the failing test**

```python
from test_auth import register_user
from test_lineup_permissions import auth_headers, create_lineup


def test_favorites_view_returns_only_current_users_favorites(client):
    register_user(client, username='owner', email='owner@example.com')
    favorite_target = create_lineup(client, name='收藏目标', code='#FAVORITE1').get_json()
    non_favorite_target = create_lineup(client, name='普通阵容', code='#NORMAL1').get_json()
    headers = auth_headers(client)
    assert client.post(f"/api/lineups/{favorite_target['id']}/favorite", headers=headers).status_code == 200

    payload = client.get('/api/lineups?view=favorites&page=1&page_size=10').get_json()

    assert payload['total'] == 1
    assert payload['items'][0]['id'] == favorite_target['id']
    assert payload['items'][0]['is_favorited'] is True
    assert all(item['id'] != non_favorite_target['id'] for item in payload['items'])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_interactions.py -q -p no:cacheprovider -k favorites_view_returns_only_current_users_favorites`

Expected: FAIL，因为当前 `view=favorites` 还没有实现。

- [ ] **Step 3: Write minimal implementation**

在 `lineups.py` 中只做最小变更，复用现有列表协议：

```python
def _list_clauses(user, view, query):
    clauses = ["l.status = 'normal'"]
    params = []
    if view == 'mine':
        clauses.append('l.user_id = ?')
        params.append(user['id'])
    if view == 'favorites':
        clauses.append('EXISTS (SELECT 1 FROM favorites f WHERE f.lineup_id = l.id AND f.user_id = ?)')
        params.append(user['id'])
    if query:
        clauses.append('l.name LIKE ?')
        params.append(f'%{query}%')
    return clauses, params


@lineups_bp.get('/api/lineups')
def list_lineups():
    user = current_user()
    view = request.args.get('view', 'all')
    if view in {'mine', 'favorites'} and not user:
        page_size = _parse_positive_int(request.args.get('page_size'), 10)
        return jsonify({'items': [], 'total': 0, 'page': 1, 'page_size': page_size, 'total_pages': 1})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_interactions.py -q -p no:cacheprovider -k favorites_view_returns_only_current_users_favorites`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lineups.py tests/test_interactions.py
git commit -m "feat: add favorites lineup view"
```

---

## Task 2: Add Explicit Account Value Copy And Favorites Entry In Server-Rendered HTML

**Files:**
- Modify: `templates/index.html`
- Modify: `templates/auth.html`
- Modify: `static/styles.css`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_index_page_contains_account_value_copy_and_favorites_tab(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="favoritesTab"' in html
    assert '登录后可收藏阵容并跨设备同步' in html
    assert '登录后可查看我的收藏和我的阵容' in html


def test_auth_page_contains_account_benefits_copy(client):
    html = client.get('/auth').get_data(as_text=True)
    assert '登录后可收藏阵容并跨设备同步' in html
    assert '登录后可发布和管理自己的阵容' in html
    assert '登录后可查看我的收藏、我的阵容和个人记录' in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k "favorites_tab or account_benefits"`

Expected: FAIL，因为当前页面没有这些文案和入口。

- [ ] **Step 3: Write minimal implementation**

首页 `templates/index.html` 增加收藏标签与权益文案：

```html
<div class="tabs" id="tabs">
  <button class="tab active" data-sort="latest" data-view="all">最新</button>
  <button class="tab" data-sort="hot" data-view="all">最热</button>
  <button class="tab" data-sort="ss" data-view="all">SS</button>
  <button class="tab" id="favoritesTab" data-sort="latest" data-view="favorites">我的收藏</button>
  <button class="tab hidden" id="mineTab" data-sort="latest" data-view="mine">我的</button>
</div>

<p class="hero-description">
  保存、搜索、点赞和复制阵容码。登录后可收藏阵容并跨设备同步，
  登录后可查看我的收藏和我的阵容。
</p>
```

登录页 `templates/auth.html` 调整为权益表达而不是纯动作页：

```html
<p class="hero-description">
  登录后可收藏阵容并跨设备同步，登录后可发布和管理自己的阵容，
  登录后可查看我的收藏、我的阵容和个人记录。
</p>
```

样式 `static/styles.css` 补收藏标签和权益区间距：

```css
.hero-benefits,
.auth-benefits {
  color: var(--muted);
  line-height: 1.8;
}

#favoritesTab::before {
  content: "★";
  margin-right: 6px;
  font-size: 0.82rem;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/index.html templates/auth.html static/styles.css tests/test_ui_routes.py
git commit -m "feat: add account value copy and favorites entry"
```

---

## Task 3: Introduce A Shared Pending-Intent Helper For Post-Login Resume

**Files:**
- Create: `static/auth-intent.js`
- Modify: `templates/index.html`
- Modify: `templates/auth.html`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Write the failing test**

```python
def test_index_and_auth_pages_include_auth_intent_script(client):
    index_html = client.get('/').get_data(as_text=True)
    auth_html = client.get('/auth').get_data(as_text=True)

    assert 'auth-intent.js' in index_html
    assert 'auth-intent.js' in auth_html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k auth_intent_script`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

新增 `static/auth-intent.js`，只做一件事：保存 / 读取 / 清理待续动作。

```javascript
(function () {
  const KEY = 'jcc_pending_auth_intent';

  function save(intent) {
    sessionStorage.setItem(KEY, JSON.stringify(intent));
  }

  function read() {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (_) {
      sessionStorage.removeItem(KEY);
      return null;
    }
  }

  function clear() {
    sessionStorage.removeItem(KEY);
  }

  window.jccAuthIntent = { save, read, clear };
})();
```

在 `templates/index.html` 和 `templates/auth.html` 的页面脚本前引入：

```html
<script src="{{ url_for('static', filename='auth-intent.js') }}" defer></script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k auth_intent_script`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add static/auth-intent.js templates/index.html templates/auth.html tests/test_ui_routes.py
git commit -m "feat: add shared auth intent helper"
```

---

## Task 4: Show Like/Favorite Entry Points To Guests And Resume Them After Login

**Files:**
- Modify: `static/app.js`
- Modify: `static/auth.js`
- Modify: `static/styles.css`
- Test: `tests/test_ui_routes.py`
- Manual verify: browser flow on `/` and `/auth`

- [ ] **Step 1: Write the failing markup-level test**

```python
def test_index_page_contains_guest_action_prompt_shell(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="authPromptRoot"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k auth_prompt_shell`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

首页增加一个空容器供 JS 挂登录提示：

```html
<div id="authPromptRoot"></div>
```

`static/app.js` 中引入统一的待续动作流：

```javascript
function requireAuthIntent(intent, message) {
  if (state.user) return false;
  window.jccAuthIntent.save(intent);
  showAuthPrompt(message);
  return true;
}

async function likeLineup(lineup) {
  if (requireAuthIntent({ type: 'like_lineup', lineupId: lineup.id }, '登录后可点赞并保留个人记录')) return;
  await api(`/api/lineups/${lineup.id}/like`, { method: 'POST' });
  showMessage('点赞成功');
  loadLineups();
}

async function favoriteLineup(lineup) {
  if (requireAuthIntent({ type: 'favorite_lineup', lineupId: lineup.id }, '登录后可收藏阵容并跨设备同步')) return;
  await api(`/api/lineups/${lineup.id}/favorite`, { method: 'POST' });
  showMessage('收藏成功');
  loadLineups();
}
```

同时把首页按钮渲染逻辑改成游客也能看到点赞 / 收藏按钮：

```javascript
actions.append(button(lineup.is_liked_today ? '今日已赞' : '点赞', () => likeLineup(lineup), '', Boolean(state.user && lineup.is_liked_today)));
actions.append(button(lineup.is_favorited ? '已收藏' : '收藏', () => favoriteLineup(lineup), '', Boolean(state.user && lineup.is_favorited)));
if (state.user) {
  actions.append(button('举报', () => reportLineup(lineup)));
} else {
  actions.append(button('举报', () => requireAuthIntent({ type: 'report_lineup', lineupId: lineup.id }, '登录后可举报问题阵容并保留处理记录')));
}
```

`static/auth.js` 登录成功后增加统一续接：

```javascript
function resolvePostLoginRedirect() {
  const intent = window.jccAuthIntent.read();
  if (!intent) return '/';
  if (intent.type === 'open_create_lineup') return '/lineup/new';
  return '/?resume_intent=1';
}

async function login(event) {
  event.preventDefault();
  const data = await api('/api/login', { ... });
  state.user = data.user;
  state.csrfToken = data.csrf_token;
  window.location.href = resolvePostLoginRedirect();
}
```

`static/app.js` 的 `boot()` 中在 `loadMe()` 和 `loadLineups()` 后消费待续动作：

```javascript
async function consumePendingIntent() {
  const intent = window.jccAuthIntent.read();
  if (!intent || !state.user) return;
  window.jccAuthIntent.clear();
  if (intent.type === 'favorite_lineup') {
    await api(`/api/lineups/${intent.lineupId}/favorite`, { method: 'POST' });
    showMessage('已自动完成收藏');
  }
  if (intent.type === 'like_lineup') {
    await api(`/api/lineups/${intent.lineupId}/like`, { method: 'POST' });
    showMessage('已自动完成点赞');
  }
  if (intent.type === 'report_lineup') {
    showMessage('请重新输入举报原因');
  }
  if (intent.type === 'open_view_favorites') {
    state.view = 'favorites';
  }
  if (intent.type === 'open_view_mine') {
    state.view = 'mine';
  }
}
```

这里明确约束：
- 举报原因不在第一阶段自动续上，只续到“进入已登录状态”
- `report_lineup` 登录后只提示“重新输入举报原因”，不存未提交文本
- `createLineupLink`、`favoritesTab`、`mineTab` 在游客状态下点击时只存意图并跳 `/auth`

- [ ] **Step 4: Run the server-rendered tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Manual verification**

Run local server: `python D:\1\codex\jcc\claude_project\run_server.py`

Manual path A:
1. 未登录打开首页
2. 点击任意阵容的“收藏”
3. 页面弹出登录提示并跳转 `/auth`
4. 登录成功后返回首页
5. 原阵容自动完成收藏
6. 切到“我的收藏”能看到该阵容

Manual path B:
1. 未登录点击“点赞”
2. 登录成功后自动完成点赞
3. 首页卡片按钮变成“今日已赞”

Manual path C:
1. 未登录点击“新增阵容”
2. 登录成功后跳到 `/lineup/new`

- [ ] **Step 6: Commit**

```bash
git add static/app.js static/auth.js static/styles.css templates/index.html tests/test_ui_routes.py
git commit -m "feat: resume guest actions after login"
```

---

## Task 5: Add Favorites Tab Behavior And Empty-State UX

**Files:**
- Modify: `static/app.js`
- Modify: `templates/index.html`
- Modify: `static/styles.css`
- Test: `tests/test_ui_routes.py`
- Test: `tests/test_interactions.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_index_page_contains_favorites_empty_state_copy(client):
    html = client.get('/').get_data(as_text=True)
    assert '登录后可收藏阵容并随时找回' in html
```

补接口测试覆盖游客访问 `view=favorites`：

```python
def test_anonymous_favorites_view_returns_empty_payload(client):
    payload = client.get('/api/lineups?view=favorites&page=1&page_size=10').get_json()
    assert payload['total'] == 0
    assert payload['items'] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_interactions.py D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k "favorites"`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `static/app.js` 中让 `favoritesTab` 成为正式视图：

```javascript
function renderAuth() {
  const loggedIn = Boolean(state.user);
  elements.favoritesTab.classList.remove('hidden');
  elements.mineTab.classList.toggle('hidden', !loggedIn);
}

elements.tabs.addEventListener('click', (event) => {
  const tab = event.target.closest('.tab');
  if (!tab) return;
  if (!state.user && tab.dataset.view === 'favorites') {
    requireAuthIntent({ type: 'open_view_favorites' }, '登录后可收藏阵容并随时找回');
    return;
  }
  if (!state.user && tab.dataset.view === 'mine') {
    requireAuthIntent({ type: 'open_view_mine' }, '登录后可查看和管理你发布的阵容');
    return;
  }
  state.view = tab.dataset.view;
  state.sort = tab.dataset.sort;
  state.page = 1;
  loadLineups();
});
```

在空态文案中区分收藏视图：

```javascript
if (state.view === 'favorites' && !state.lineups.length) {
  elements.emptyState.querySelector('p').textContent = '登录后可收藏阵容并随时找回，收藏内容会跟随账号同步。';
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_interactions.py D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k "favorites"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add static/app.js templates/index.html static/styles.css tests/test_interactions.py tests/test_ui_routes.py
git commit -m "feat: add favorites tab behavior"
```

---

## Phase 2 Technical Notes (Not In This Batch)

### Recent Browsing

不要复用 `visit_events`：

- `visit_events` 是按天 UV 去重
- 它不能表示“最近浏览的具体 20 条阵容”

Phase 2 建议新表：

```sql
CREATE TABLE IF NOT EXISTS recent_lineup_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    visitor_token TEXT,
    lineup_id INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
```

### Recent Copies

不要直接把 `copy_events` 当最近复制列表：

- 当前 `copy_events` 有 10 分钟去重
- 它服务于热度计数，不适合做“完整复制历史”

Phase 2 建议新表：

```sql
CREATE TABLE IF NOT EXISTS recent_lineup_copies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    visitor_token TEXT,
    lineup_id INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
```

### Conversion Funnel Analytics

Phase 3 再做。SQLite 先从轻量事件表开始：

```sql
CREATE TABLE IF NOT EXISTS growth_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    user_id INTEGER,
    visitor_token TEXT,
    ip_address TEXT,
    ref_lineup_id INTEGER,
    payload_json TEXT,
    created_at TEXT NOT NULL
);
```

推荐事件名：
- `click_login_entry`
- `guest_click_like`
- `guest_click_favorite`
- `login_success`
- `register_success`
- `post_login_favorite`
- `post_login_like`
- `post_login_create_lineup`

---

## Verification Checklist For The Whole Phase

- [ ] Run focused interaction tests  
  `python -m pytest D:\1\codex\jcc\claude_project\tests\test_interactions.py -q -p no:cacheprovider`

- [ ] Run route/template tests  
  `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`

- [ ] Run full suite serially  
  `python -m pytest D:\1\codex\jcc\claude_project\tests -q -p no:cacheprovider`

- [ ] Manual mobile checks
  - 首页游客可见点赞 / 收藏入口
  - 登录页权益文案不换行错乱
  - 收藏标签在手机端不挤出屏幕
  - 登录后自动续操作在手机端也正常

---

## Why This Phase First

这一批改动满足四个条件：

1. **登录触发点最自然**
   - 点赞 / 收藏本来就是账号行为

2. **账号价值最容易被用户感知**
   - “我的收藏”比抽象账号体系更容易理解

3. **对现有架构侵入最小**
   - 不需要上新服务
   - 不需要替换认证方式
   - 不需要立即迁移数据库结构

4. **最容易看到转化改善**
   - 游客不再只能被动看到“登录 / 注册”
   - 而是在真正想收藏 / 点赞时触发登录

---

## Recommended Next Plan After This One

如果 Phase 1 验证效果不错，下一份计划建议直接写：

- `2026-05-12-v3-phase-2-history-and-dashboard.md`

覆盖：
- 最近浏览
- 最近复制
- 我的数据面板
- 举报反馈闭环

