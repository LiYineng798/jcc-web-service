# Live Comps Phase 3 Homepage Tab And UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在首页新增“实时阵容排行”专区 Tab，并按 `S/A/B/C/D` 分组展示上传后的实时阵容数据，每组每页 5 条，仅提供复制按钮。

**Architecture:** 复用现有首页外壳，但把实时阵容渲染视作独立模式：点击新 Tab 后不再走 `/api/lineups`，而是先取 `/api/live-comps/summary`，再按段位拉取分页数据并渲染新卡片。搜索框在该模式下禁用，避免暗示未实现的搜索功能。

**Tech Stack:** Jinja2 template, vanilla JavaScript, existing `styles.css`, current toast/copy helpers

---

### Task 1: 补齐首页结构与 Tab 顺序测试

**Files:**
- Modify: `templates/index.html`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: 先写首页新 Tab 与顺序的失败测试**

```python
def test_index_contains_live_comps_tab_before_latest(client):
    html = client.get('/').get_data(as_text=True)
    assert '实时阵容排行' in html
    assert html.index('实时阵容排行') < html.index('最新')


def test_index_contains_live_comps_mount_points(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="lineupList"' in html
    assert 'id="pagination"' in html
    assert 'data-view="live-comps"' in html
```

- [ ] **Step 2: 运行 UI 路由测试，确认模板尚未更新**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: FAIL，因为首页还没有 `实时阵容排行` Tab。

- [ ] **Step 3: 在首页模板中插入新 Tab，位置放到“最新”左侧**

```html
<div class="tabs" id="tabs">
  <button class="tab" data-sort="live" data-view="live-comps">实时阵容排行</button>
  <button class="tab active" data-sort="latest" data-view="all">最新</button>
  <button class="tab" data-sort="hot" data-view="all">最热</button>
  <button class="tab" data-sort="rising" data-view="all">上升</button>
  <button class="tab" data-sort="recommended" data-view="all">推荐</button>
  <button class="tab" data-sort="ss" data-view="all">SS</button>
  <button class="tab" id="favoritesTab" data-sort="latest" data-view="favorites">我的收藏</button>
  <button class="tab hidden" id="mineTab" data-sort="latest" data-view="mine">我的</button>
</div>
```

- [ ] **Step 4: 重跑 UI 路由测试**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: PASS

### Task 2: 为首页脚本增加“实时阵容排行”模式

**Files:**
- Modify: `static/app.js`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: 先写脚本层存在性测试**

```python
def test_app_js_contains_live_comps_mode_and_copy_only_actions():
    with open(r'D:\1\codex\jcc\claude_project\static\app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'live-comps' in js
    assert '/api/live-comps/summary' in js
    assert '/api/live-comps?tier=' in js
    assert '实时阵容排行' in js
    assert 'renderLiveComps' in js
```

- [ ] **Step 2: 运行测试，确认首页脚本还没有实时阵容模式**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: FAIL，因为 `app.js` 还没有 live comps 逻辑。

- [ ] **Step 3: 在 `app.js` 中新增状态、加载函数和模式切换**

```javascript
const state = {
  lineups: [],
  liveCompsSummary: null,
  liveCompsByTier: {},
  query: '',
  sort: 'latest',
  view: 'all',
  page: 1,
  pageSize: 10,
  total: 0,
  totalPages: 1,
};
```

```javascript
elements.tabs.addEventListener('click', (event) => {
  const tab = event.target.closest('.tab');
  if (!tab) return;
  setActiveTab(tab.dataset.sort, tab.dataset.view);
  loadCurrentView();
});
```

```javascript
async function loadLiveComps() {
  const summary = await fetch('/api/live-comps/summary').then((response) => response.json());
  state.liveCompsSummary = summary;
  state.liveCompsByTier = {};
  syncSearchInputState(true);
  await Promise.all((summary.tiers || []).map(async ({ tier }) => {
    const payload = await fetch(`/api/live-comps?tier=${encodeURIComponent(tier)}&page=1`).then((response) => response.json());
    state.liveCompsByTier[tier] = payload;
  }));
  renderLiveComps();
}


function syncSearchInputState(isLiveComps) {
  elements.searchInput.disabled = isLiveComps;
  elements.searchInput.placeholder = isLiveComps
    ? '实时阵容排行暂不支持搜索'
    : '搜索阵容名称，例如：九五、卡莎、斗士';
  if (isLiveComps) elements.searchInput.value = '';
}


function loadCurrentView() {
  syncSearchInputState(state.view === 'live-comps');
  if (state.view === 'live-comps') return loadLiveComps();
  return loadLineups();
}


async function boot() {
  await loadMe();
  applySavedMessage();
  await consumePendingIntent();
  await loadCurrentView();
}
```

- [ ] **Step 4: 重跑 UI 测试**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: PASS

### Task 3: 渲染分组卡片、分页器和复制动作

**Files:**
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: 先写样式与功能点测试**

```python
def test_styles_include_live_comps_sections_and_cards():
    with open(r'D:\1\codex\jcc\claude_project\static\styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.live-comps-shell' in css
    assert '.live-tier-section' in css
    assert '.live-comp-card' in css
    assert '.live-comp-hero-strip' in css
    assert '.live-comp-pagination' in css
```

- [ ] **Step 2: 运行测试，确认还没写新的 UI 结构**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: FAIL，因为样式类和新渲染函数还不存在。

- [ ] **Step 3: 实现实时阵容分组渲染、每组分页和复制按钮**

```javascript
function renderLiveComps() {
  elements.lineupList.replaceChildren();
  elements.pagination.replaceChildren();
  elements.pagination.classList.add('hidden');
  elements.lineupCount.textContent = (state.liveCompsSummary?.tiers || []).reduce((sum, item) => sum + item.total, 0);
  elements.emptyState.classList.toggle('hidden', elements.lineupCount.textContent !== '0');

  const shell = document.createElement('div');
  shell.className = 'live-comps-shell';
  shell.append(renderLiveCompsSummaryHeader());
  (state.liveCompsSummary?.tiers || []).forEach(({ tier, total }) => {
    shell.append(renderLiveTierSection(tier, total, state.liveCompsByTier[tier]));
  });
  elements.lineupList.append(shell);
}


function renderLiveTierSection(tier, total, payload) {
  const section = document.createElement('section');
  section.className = 'live-tier-section';
  section.append(renderLiveTierHeader(tier, total, payload.page, payload.total_pages));
  (payload.items || []).forEach((item) => section.append(renderLiveCompCard(item)));
  section.append(renderLiveTierPagination(tier, payload.page, payload.total_pages));
  return section;
}


function renderLiveCompsSummaryHeader() {
  const header = document.createElement('div');
  header.className = 'live-comps-summary';
  header.textContent = `实时阵容排行 · 最近更新 ${state.liveCompsSummary?.updated_at || '暂无数据'}`;
  return header;
}


function renderLiveTierHeader(tier, total, page, totalPages) {
  const header = document.createElement('div');
  header.className = 'live-tier-header';
  header.textContent = `${tier} 级阵容 · ${total} 套 · 第 ${page}/${totalPages} 页`;
  return header;
}


function renderLiveCompCard(item) {
  const card = document.createElement('article');
  card.className = `live-comp-card tier-${String(item.tier || '').toLowerCase()}`;
  const avatar = document.createElement('img');
  avatar.className = 'live-comp-avatar';
  avatar.src = item.mainAvatar;
  avatar.alt = item.title;
  card.append(avatar, liveCompBody(item));
  return card;
}


function liveCompBody(item) {
  const body = document.createElement('div');
  body.className = 'live-comp-body';
  const title = document.createElement('h3');
  title.className = 'live-comp-title';
  title.textContent = item.title;
  const tier = document.createElement('span');
  tier.className = 'live-comp-tier';
  tier.textContent = item.tier;
  const heroes = document.createElement('div');
  heroes.className = 'live-comp-hero-strip';
  (item.heroImages || []).forEach((src) => {
    const hero = document.createElement('img');
    hero.className = 'live-comp-hero';
    hero.src = src;
    hero.alt = item.title;
    heroes.append(hero);
  });
  const code = document.createElement('pre');
  code.className = 'code-preview';
  code.textContent = item.jccCode;
  body.append(title, tier, heroes, code, button('复制阵容码', () => copyLiveCompCode(item.jccCode)));
  return body;
}


function renderLiveTierPagination(tier, page, totalPages) {
  const pager = document.createElement('div');
  pager.className = 'live-comp-pagination';
  const prev = button('上一页', () => loadLiveTierPage(tier, page - 1), 'small-button', page <= 1);
  const next = button('下一页', () => loadLiveTierPage(tier, page + 1), 'small-button', page >= totalPages);
  pager.append(prev, next);
  return pager;
}
```

```javascript
async function loadLiveTierPage(tier, page) {
  const payload = await fetch(`/api/live-comps?tier=${encodeURIComponent(tier)}&page=${page}`).then((response) => response.json());
  state.liveCompsByTier[tier] = payload;
  renderLiveComps();
}


async function copyLiveCompCode(code) {
  await navigator.clipboard.writeText(code);
  showToast('阵容码已复制');
}
```

```css
.live-comps-shell {
  display: grid;
  gap: 18px;
}

.live-tier-section {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface-solid);
}

.live-comp-card {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255,255,255,0.06), transparent), var(--surface);
}

.live-comp-hero-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.live-comp-pagination {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 720px) {
  .live-comp-card {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: 重跑 UI 测试**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: PASS

### Task 4: 联调、文案修正与 Phase 3 收尾

**Files:**
- Modify: `templates/index.html`
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Modify: `README.md`
- Modify: `tests/test_live_comps.py`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: 做一次后端 + 首页联调测试**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 2: 本地启动并手工验收页面**

Run: `python D:\1\codex\jcc\claude_project\run_server.py`
Expected:
- 首页 Tab 顺序为“实时阵容排行 / 最新 / 最热 / 上升 / 推荐 / SS / 我的收藏 / 我的”
- 点击“实时阵容排行”后，看到 `S/A/B/C/D` 分组
- 每组每页最多 5 条
- 每张卡片只有复制按钮，没有查看详情按钮
- 手机端下卡片堆叠显示，分页按钮仍可操作

- [ ] **Step 3: 如用户确认，再同步到 `jcc_git`**

```bash
robocopy D:\1\codex\jcc\claude_project D:\1\codex\jcc\jcc_git /MIR /XD instance __pycache__ .pytest_cache
git -C D:\1\codex\jcc\jcc_git status --short
```
