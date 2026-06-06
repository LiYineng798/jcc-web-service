# V3 Phase 3 Growth And Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 V3 的第三阶段能力：作者主页、热度趋势/上升榜、首页推荐策略，以及后台可用的登录转化漏斗埋点与增长统计。

**Architecture:** 保持当前 Flask + SQLite + 原生前端结构，引入一层轻量 `analytics.py` 负责事件记录和增长聚合，引入一层 `recommendation.py` 负责“上升”和“推荐”的排序策略，并用独立作者页 `/author/<username>` 承载作者内容与公开数据。所有推荐与增长能力都采用可解释的规则，不引入外部分析平台、消息队列或模型服务。

**Tech Stack:** Flask、SQLite、Jinja2、Vanilla JS、Pytest

---

## Scope Decision

第三阶段只做“增长分析 + 内容发现”，明确包含：

- 作者主页
- 上升榜 / 热度趋势
- 首页推荐策略
- 登录与转化漏斗事件埋点
- 管理后台增长漏斗展示

明确不包含：

- 关注作者
- 私信
- 评论
- 站内通知
- 邮件推送
- 外部统计平台接入（GA、Mixpanel、神策等）

原因很直接：这些能力已经从“内容发现优化”跨到“社区系统”或“运营系统”，不应混在同一阶段。

---

## Assumptions And Dependencies

1. **推荐先做完 Phase 1**
   - Phase 1 提供更完整的登录动作和收藏行为
   - 第三阶段的转化漏斗要基于这些行为埋点才有意义

2. **推荐先做完 Phase 2**
   - Phase 2 提供最近浏览、最近复制和个人中心
   - 第三阶段的个性化推荐可以复用这些历史信号

3. **如果 Phase 2 尚未实施**
   - 第三阶段仍可落地
   - 但“推荐”必须退化为匿名版推荐，不能依赖用户最近浏览/最近复制历史

4. **仍然不引入外部服务**
   - 所有事件和聚合先放 SQLite
   - 先解决“能看、能用、能解释”，不解决“大数据规模”

---

## Current Code Map

### Existing scoring and discovery behavior

- `scoring.py`
  - 当前只有 `score_map()`
  - 权重逻辑基于最近 7 天点赞/复制
  - 当前没有“上升趋势”指标，也没有“推荐”策略

- `lineups.py`
  - 当前 `sort` 只支持：
    - `latest`
    - `hot`
    - `ss`
  - 没有：
    - `rising`
    - `recommended`
  - 卡片序列化里只有 `owner_nickname`
  - 没有 `owner_username`，因此前台暂时无法给作者做稳定链接

### Existing growth-related data

- `visit_events`
  - 目前用于日 UV
  - 适合继续提供“首页 UV / auth UV / admin UV”
  - 不适合表达具体点击行为

- `login_events`
  - 只记录登录是否成功
  - 适合继续作为登录成功统计基础

- `favorites` / `likes` / `copy_events`
  - 已经能表达核心互动结果
  - 但不能表达“用户有没有点登录入口”“游客有没有尝试收藏后去登录”

### Existing frontend

- `templates/index.html` + `static/app.js`
  - 是首页内容发现入口
  - 第三阶段需要在这里增加：
    - 作者链接
    - 新排序标签（上升 / 推荐）

- `templates/admin.html` + `static/admin.js`
  - 已有后台统计看板
  - 第三阶段需要新增增长漏斗模块

### Existing constraints

- SQLite 单库
- pytest 必须串行跑
- 当前没有 E2E 自动化
  - 第三阶段仍然使用接口测试 + 模板断言 + 本地手工验证

---

## Product Decisions Locked In For Phase 3

### 1. 作者页使用用户名路由，不用数字 ID

**本计划决定：**

- 作者主页路由使用 `/author/<username>`
- 所有阵容卡片和详情页作者信息都跳这个路由

原因：

- 用户名已经唯一
- URL 更可读
- 不需要暴露内部 ID

### 2. “上升榜”是趋势榜，不等于“最热榜”

**本计划决定：**

- `hot` 继续表示最近 7 天累计热度最高
- `rising` 表示最近 24 小时相对前 24 小时的增长更快

这样可以解决两个榜单重叠的问题：

- `hot` 适合看稳定强势内容
- `rising` 适合看刚刚起势的内容

### 3. “推荐”先做规则式推荐，不做黑盒推荐

**本计划决定：**

- 匿名用户推荐：基于热度 + 新鲜度 + 作者多样性
- 登录用户推荐：在匿名推荐基础上，额外使用收藏 / 最近浏览 / 最近复制做个性化加权

明确不做：

- 协同过滤
- 嵌入向量
- 模型训练

原因：

- 当前站点数据量和架构都不适合
- 可解释规则更容易调试、验证和交接

### 4. 埋点使用事件表 + 白名单事件名

**本计划决定：**

- 所有增长埋点都写入新表 `growth_events`
- 事件名必须来自后端 allowlist
- 匿名事件也要求 session 内 `csrf_token`

这样能避免：

- 任意事件名污染数据
- 完全开放匿名上报接口带来的垃圾数据

### 5. 后台增长模块先做“漏斗 + 核心比例”，不做复杂图表系统

**本计划决定：**

- 后台展示：
  - 首页 UV
  - 登录入口点击人数
  - 进入登录页人数
  - 注册成功人数
  - 登录成功人数
  - 游客收藏尝试数
  - 游客点赞尝试数
  - 登录后 10 分钟内发生收藏/点赞/上传/复制的人数

- 用卡片 + 简单列表展示
- 不引入复杂图表库

---

## File Structure For This Phase

### New files

- `analytics.py`
  - 事件写入、事件聚合、漏斗统计 helper

- `recommendation.py`
  - 上升分、推荐分、作者多样性规则

- `templates/author.html`
  - 作者主页模板

- `static/author.js`
  - 作者主页逻辑

- `tests/test_growth.py`
  - 增长埋点与漏斗聚合测试

- `tests/test_author_page.py`
  - 作者页与作者 API 测试

- `tests/test_discovery.py`
  - `rising` / `recommended` 排序策略测试

### Modified files

- `db.py`
  - 新增 `growth_events`

- `app.py`
  - 新增 `/author/<username>` 页面路由

- `lineups.py`
  - 新增作者 API
  - 新增增长事件上报 API
  - 扩展 `sort=rising`
  - 扩展 `sort=recommended`
  - 扩展序列化字段 `owner_username`

- `auth.py`
  - 登录/注册成功后记增长事件

- `templates/index.html`
  - 新增“上升”“推荐”标签
  - 作者链接容器

- `static/app.js`
  - 新排序标签行为
  - 首页登录入口、游客点赞/收藏尝试埋点

- `templates/admin.html`
  - 后台新增增长概览模块挂载点

- `static/admin.js`
  - 请求并渲染增长漏斗数据

- `static/styles.css`
  - 作者页、增长模块、推荐标签样式

- `tests/test_admin.py`
  - 覆盖后台增长统计接口

- `项目交接文档.md`
  - 如果本阶段落地，需要补作者页、推荐策略、增长事件接口说明

---

## Event Model Locked In

### `growth_events` table

```sql
CREATE TABLE IF NOT EXISTS growth_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    user_id INTEGER,
    visitor_token TEXT,
    ip_address TEXT,
    ref_lineup_id INTEGER,
    page_key TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(ref_lineup_id) REFERENCES lineups(id)
);
```

### Allowed event names for this phase

- `click_login_entry`
- `open_auth_page`
- `guest_click_like`
- `guest_click_favorite`
- `guest_click_report`
- `register_success`
- `login_success`
- `post_login_like`
- `post_login_favorite`
- `post_login_copy`
- `post_login_create_lineup`

### Funnel definition

后台展示默认最近 7 天，按自然日聚合，并额外给出总转化漏斗：

1. 首页 UV
2. 登录入口点击人数
3. 登录页打开人数
4. 注册成功人数
5. 登录成功人数
6. 游客点赞尝试人数
7. 游客收藏尝试人数
8. 登录后 10 分钟内完成核心动作人数

“登录后 10 分钟内完成核心动作”定义为：

- `login_success` 或 `register_success` 后 10 分钟内，
- 出现任一事件：
  - `post_login_like`
  - `post_login_favorite`
  - `post_login_copy`
  - `post_login_create_lineup`

---

## Task 1: Add Growth Event Schema And Analytics Helper

**Files:**
- Create: `analytics.py`
- Modify: `db.py`
- Test: `tests/test_growth.py`

- [ ] **Step 1: Write the failing schema and helper tests**

```python
def test_growth_events_table_exists(app):
    with app.app_context():
        from db import table_names
        assert 'growth_events' in table_names()


def test_record_growth_event_persists_whitelisted_event(app):
    with app.app_context():
        from analytics import record_growth_event
        from db import get_db

        record_growth_event(
            event_name='click_login_entry',
            user_id=None,
            visitor_token='guest-token',
            ip_address='1.2.3.4',
            ref_lineup_id=None,
            page_key='home',
            payload={'source': 'header'},
            created_at='2026-05-12 09:00:00',
        )

        row = get_db().execute('SELECT * FROM growth_events').fetchone()
        assert row['event_name'] == 'click_login_entry'
        assert row['visitor_token'] == 'guest-token'
        assert row['page_key'] == 'home'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_growth.py -q -p no:cacheprovider -k "growth_events_table_exists or record_growth_event_persists_whitelisted_event"`

Expected: FAIL，因为表和 helper 尚不存在。

- [ ] **Step 3: Write minimal implementation**

在 `db.py` 的 `SCHEMA` 中新增：

```sql
CREATE TABLE IF NOT EXISTS growth_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    user_id INTEGER,
    visitor_token TEXT,
    ip_address TEXT,
    ref_lineup_id INTEGER,
    page_key TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(ref_lineup_id) REFERENCES lineups(id)
);
```

新增 `analytics.py`：

```python
import json

from db import get_db, now_text

ALLOWED_GROWTH_EVENTS = {
    'click_login_entry',
    'open_auth_page',
    'guest_click_like',
    'guest_click_favorite',
    'guest_click_report',
    'register_success',
    'login_success',
    'post_login_like',
    'post_login_favorite',
    'post_login_copy',
    'post_login_create_lineup',
}


def record_growth_event(event_name, user_id=None, visitor_token=None, ip_address=None, ref_lineup_id=None, page_key=None, payload=None, created_at=None):
    if event_name not in ALLOWED_GROWTH_EVENTS:
        raise ValueError('unsupported growth event')
    get_db().execute(
        '''
        INSERT INTO growth_events (
            event_name, user_id, visitor_token, ip_address, ref_lineup_id, page_key, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            event_name,
            user_id,
            visitor_token,
            ip_address,
            ref_lineup_id,
            page_key,
            json.dumps(payload or {}, ensure_ascii=False),
            created_at or now_text(),
        ),
    )
    get_db().commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_growth.py -q -p no:cacheprovider -k "growth_events_table_exists or record_growth_event_persists_whitelisted_event"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db.py analytics.py tests/test_growth.py
git commit -m "feat: add growth events schema and helper"
```

---

## Task 2: Instrument Core Growth Events In Auth And Frontend

**Files:**
- Modify: `auth.py`
- Modify: `static/app.js`
- Modify: `static/auth.js`
- Modify: `templates/index.html`
- Modify: `templates/auth.html`
- Modify: `lineups.py`
- Test: `tests/test_growth.py`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
from test_auth import register_user, get_captcha


def test_register_and_login_success_write_growth_events(client):
    response = register_user(client, username='growth', email='growth@example.com')
    assert response.status_code == 201
    client.post('/api/logout')
    assert client.post('/api/login', json={'account': 'growth', 'password': 'abc123'}).status_code == 200

    with client.application.app_context():
        from db import get_db
        names = [row['event_name'] for row in get_db().execute('SELECT event_name FROM growth_events ORDER BY id').fetchall()]
        assert 'register_success' in names
        assert 'login_success' in names


def test_growth_event_ingest_endpoint_accepts_whitelisted_guest_event(client):
    me = client.get('/api/me').get_json()
    response = client.post(
        '/api/growth-events',
        json={'event_name': 'guest_click_like', 'page_key': 'home', 'ref_lineup_id': None, 'payload': {'source': 'lineup-card'}},
        headers={'X-CSRF-Token': me['csrf_token']},
    )
    assert response.status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_growth.py -q -p no:cacheprovider -k "register_and_login_success_write_growth_events or growth_event_ingest_endpoint_accepts_whitelisted_guest_event"`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `auth.py` 中接入事件：

```python
from analytics import record_growth_event
from visits import ensure_visitor_token


@auth_bp.post('/api/register')
def register():
    ...
    visitor_token, _ = ensure_visitor_token()
    record_growth_event(
        'register_success',
        user_id=cursor.lastrowid,
        visitor_token=visitor_token,
        ip_address=ip,
        page_key='auth',
        payload={'method': 'register'},
    )
    ...


@auth_bp.post('/api/login')
def login():
    ...
    visitor_token, _ = ensure_visitor_token()
    record_growth_event(
        'login_success',
        user_id=user['id'],
        visitor_token=visitor_token,
        ip_address=ip,
        page_key='auth',
        payload={'method': 'login'},
    )
```

在 `lineups.py` 中新增事件上报接口：

```python
from analytics import ALLOWED_GROWTH_EVENTS, record_growth_event
from visits import ensure_visitor_token


@lineups_bp.post('/api/growth-events')
def ingest_growth_event():
    payload = request.get_json(silent=True) or {}
    event_name = str(payload.get('event_name') or '')
    if event_name not in ALLOWED_GROWTH_EVENTS:
        return jsonify({'error': '不支持的事件'}), 400
    user = current_user()
    visitor_token, _ = ensure_visitor_token()
    record_growth_event(
        event_name=event_name,
        user_id=user['id'] if user else None,
        visitor_token=visitor_token,
        ip_address=get_client_ip(),
        ref_lineup_id=payload.get('ref_lineup_id'),
        page_key=payload.get('page_key'),
        payload=payload.get('payload') or {},
    )
    return jsonify({'ok': True}), 201
```

在 `static/app.js` 中新增上报 helper：

```javascript
async function trackGrowth(eventName, payload = {}) {
  if (!state.csrfToken) return;
  await fetch('/api/growth-events', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrfToken },
    body: JSON.stringify({
      event_name: eventName,
      page_key: 'home',
      ref_lineup_id: payload.lineupId || null,
      payload,
    }),
  }).catch(() => {});
}
```

在登录入口、游客点赞/收藏尝试时调用：

```javascript
elements.authLink.addEventListener('click', () => trackGrowth('click_login_entry', { source: 'header' }));
...
if (!state.user) {
  trackGrowth('guest_click_like', { source: 'lineup-card', lineupId: lineup.id });
}
if (!state.user) {
  trackGrowth('guest_click_favorite', { source: 'lineup-card', lineupId: lineup.id });
}
```

在 `templates/auth.html` 和 `static/auth.js` 中进入 auth 页面时上报：

```javascript
fetch('/api/growth-events', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrfToken },
  body: JSON.stringify({ event_name: 'open_auth_page', page_key: 'auth', payload: { source: document.referrer ? 'redirect' : 'direct' } }),
}).catch(() => {});
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_growth.py -q -p no:cacheprovider -k "register_and_login_success_write_growth_events or growth_event_ingest_endpoint_accepts_whitelisted_guest_event"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add auth.py lineups.py static/app.js static/auth.js templates/index.html templates/auth.html tests/test_growth.py tests/test_ui_routes.py
git commit -m "feat: instrument growth funnel events"
```

---

## Task 3: Add Growth Funnel Aggregation For Admin

**Files:**
- Modify: `analytics.py`
- Modify: `admin.py`
- Modify: `static/admin.js`
- Modify: `static/styles.css`
- Modify: `tests/test_admin.py`

- [ ] **Step 1: Write the failing admin growth test**

```python
from test_auth import register_user
from test_admin import login_admin


def test_admin_growth_stats_returns_funnel_fields(client):
    client.get('/')
    me = client.get('/api/me').get_json()
    client.post(
        '/api/growth-events',
        json={'event_name': 'click_login_entry', 'page_key': 'home', 'payload': {'source': 'header'}},
        headers={'X-CSRF-Token': me['csrf_token']},
    )
    register_user(client, username='growth', email='growth@example.com')
    client.post('/api/logout')

    headers = login_admin(client)
    data = client.get('/api/admin/growth?days=7', headers=headers).get_json()

    assert 'home_uv' in data
    assert 'login_entry_clicks' in data
    assert 'auth_page_opens' in data
    assert 'register_successes' in data
    assert 'login_successes' in data
    assert 'guest_like_attempts' in data
    assert 'guest_favorite_attempts' in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -q -p no:cacheprovider -k admin_growth_stats_returns_funnel_fields`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `analytics.py` 中新增聚合：

```python
def growth_summary(days=7):
    db = get_db()
    rows = db.execute(
        '''
        SELECT event_name, COUNT(*) AS c
        FROM growth_events
        WHERE created_at >= datetime('now', ?)
        GROUP BY event_name
        ''',
        (f'-{int(days)} day',),
    ).fetchall()
    event_counts = {row['event_name']: row['c'] for row in rows}

    home_uv = db.execute(
        "SELECT COUNT(DISTINCT visitor_key) AS c FROM visit_events WHERE page_key = 'home' AND created_at >= datetime('now', ?)",
        (f'-{int(days)} day',),
    ).fetchone()['c']

    return {
        'home_uv': home_uv,
        'login_entry_clicks': event_counts.get('click_login_entry', 0),
        'auth_page_opens': event_counts.get('open_auth_page', 0),
        'register_successes': event_counts.get('register_success', 0),
        'login_successes': event_counts.get('login_success', 0),
        'guest_like_attempts': event_counts.get('guest_click_like', 0),
        'guest_favorite_attempts': event_counts.get('guest_click_favorite', 0),
    }
```

在 `admin.py` 中新增：

```python
from analytics import growth_summary


@admin_bp.get('/api/admin/growth')
def admin_growth():
    admin, error = admin_required()
    if error:
        return error
    days = int(request.args.get('days', 7))
    return jsonify(growth_summary(days=days))
```

在 `static/admin.js` 中加载并渲染新模块：

```javascript
[state.stats, state.growth, state.reports, state.lineups, state.users, state.logs] = await Promise.all([
  api('/api/admin/stats'),
  api('/api/admin/growth?days=7'),
  ...
]);
```

新增 `renderGrowth()`：

```javascript
function renderGrowth() {
  const { section, body } = createModule('增长漏斗', '最近 7 天的登录与转化表现');
  const list = el('div', 'admin-list compact');
  [
    ['首页 UV', state.growth.home_uv || 0],
    ['登录入口点击', state.growth.login_entry_clicks || 0],
    ['登录页打开', state.growth.auth_page_opens || 0],
    ['注册成功', state.growth.register_successes || 0],
    ['登录成功', state.growth.login_successes || 0],
    ['游客点赞尝试', state.growth.guest_like_attempts || 0],
    ['游客收藏尝试', state.growth.guest_favorite_attempts || 0],
  ].forEach(([label, value]) => {
    const card = el('article', 'admin-row-card');
    card.append(el('strong', '', label), el('span', 'admin-meta', String(value)));
    list.append(card);
  });
  body.append(list);
  return section;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -q -p no:cacheprovider -k admin_growth_stats_returns_funnel_fields`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analytics.py admin.py static/admin.js static/styles.css tests/test_admin.py
git commit -m "feat: add admin growth funnel stats"
```

---

## Task 4: Add Author API And Public Author Page

**Files:**
- Modify: `app.py`
- Modify: `lineups.py`
- Create: `templates/author.html`
- Create: `static/author.js`
- Create: `tests/test_author_page.py`
- Modify: `static/styles.css`

- [ ] **Step 1: Write the failing author-page tests**

```python
from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_author_page_exists_and_uses_username_route(client):
    register_user(client, username='author1', email='author1@example.com', nickname='作者一号')
    create_lineup(client, name='作者阵容', code='#AUTHOR001')

    response = client.get('/author/author1')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="authorApp"' in html
    assert 'author.js' in html


def test_author_api_returns_profile_and_public_lineups(client):
    register_user(client, username='author2', email='author2@example.com', nickname='作者二号')
    create_lineup(client, name='阵容A', code='#AUTHOR002')
    create_lineup(client, name='阵容B', code='#AUTHOR003')

    payload = client.get('/api/authors/author2').get_json()
    assert payload['profile']['username'] == 'author2'
    assert payload['profile']['nickname'] == '作者二号'
    assert payload['summary']['published_lineups'] == 2
    assert len(payload['lineups']) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_author_page.py -q -p no:cacheprovider`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `app.py` 中新增：

```python
@app.get('/author/<username>')
def author_page(username):
    return tracked_template_response('author.html', 'author', username=username)
```

在 `lineups.py` 的序列化中补作者用户名：

```python
select_fields = [
    'l.*',
    'owner.username AS owner_username',
    'owner.nickname AS owner_nickname_raw',
    'owner.role AS owner_role',
]

data = {
    ...
    'owner_username': _row_value(row, 'owner_username'),
    ...
}
```

新增作者 API：

```python
@lineups_bp.get('/api/authors/<username>')
def author_profile(username):
    author = get_db().execute(
        "SELECT id, username, nickname, role, created_at FROM users WHERE username = ? AND role != 'admin'",
        (username,),
    ).fetchone()
    if not author:
        return jsonify({'error': '作者不存在'}), 404

    rows = get_db().execute(
        '''
        SELECT l.*, users.username AS owner_username, users.nickname AS owner_nickname_raw, users.role AS owner_role
        FROM lineups l
        JOIN users ON users.id = l.user_id
        WHERE l.user_id = ? AND l.status = 'normal'
        ORDER BY l.updated_at DESC, l.id DESC
        ''',
        (author['id'],),
    ).fetchall()
    scores = score_map()
    lineups = [_serialize(row, scores, user=None) for row in rows]
    summary = {
        'published_lineups': len(lineups),
        'total_likes': sum(item['like_count'] for item in lineups),
        'total_copies': sum(item['copy_count'] for item in lineups),
    }
    return jsonify({
        'profile': {'username': author['username'], 'nickname': author['nickname'], 'created_at': author['created_at']},
        'summary': summary,
        'lineups': lineups,
    })
```

模板 `templates/author.html`：

```html
<main class="page-shell author-page-shell">
  <section class="panel">
    <div id="authorApp" data-username="{{ username }}">作者主页加载中...</div>
  </section>
</main>
<script src="{{ url_for('static', filename='author.js') }}" defer></script>
```

`static/author.js`：

```javascript
(async function () {
  const root = document.querySelector('#authorApp');
  if (!root) return;
  const username = root.dataset.username;
  const payload = await fetch(`/api/authors/${encodeURIComponent(username)}`).then((response) => response.json());
  renderAuthor(payload);
})();
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_author_page.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py lineups.py templates/author.html static/author.js static/styles.css tests/test_author_page.py
git commit -m "feat: add public author page"
```

---

## Task 5: Add Rising Ranking In Discovery

**Files:**
- Modify: `scoring.py`
- Modify: `lineups.py`
- Create: `tests/test_discovery.py`

- [ ] **Step 1: Write the failing rising-sort test**

```python
from test_auth import register_user
from test_lineup_permissions import create_lineup, auth_headers


def test_rising_sort_prioritizes_recently_accelerating_lineups(client):
    register_user(client, username='owner', email='owner@example.com')
    rising = create_lineup(client, name='上升阵容', code='#RISING001').get_json()
    stable = create_lineup(client, name='稳定阵容', code='#RISING002').get_json()
    headers = auth_headers(client)

    for _ in range(3):
        client.post(f"/api/lineups/{rising['id']}/like", headers=headers)

    payload = client.get('/api/lineups?sort=rising&page=1&page_size=10').get_json()
    assert payload['items'][0]['id'] == rising['id']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_discovery.py -q -p no:cacheprovider -k rising_sort_prioritizes_recently_accelerating_lineups`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

在 `scoring.py` 中新增：

```python
def rising_map(db=None, now=None):
    db = db or get_db()
    now = now or datetime.now()
    recent_cutoff = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    previous_cutoff = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    rows = db.execute(
        '''
        SELECT
            l.id AS lineup_id,
            COALESCE(recent_likes.c, 0) AS recent_likes,
            COALESCE(recent_copies.c, 0) AS recent_copies,
            COALESCE(previous_likes.c, 0) AS previous_likes,
            COALESCE(previous_copies.c, 0) AS previous_copies
        FROM lineups l
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS c FROM likes WHERE created_at >= ? GROUP BY lineup_id
        ) recent_likes ON recent_likes.lineup_id = l.id
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS c FROM copy_events WHERE counted = 1 AND created_at >= ? GROUP BY lineup_id
        ) recent_copies ON recent_copies.lineup_id = l.id
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS c FROM likes WHERE created_at >= ? AND created_at < ? GROUP BY lineup_id
        ) previous_likes ON previous_likes.lineup_id = l.id
        LEFT JOIN (
            SELECT lineup_id, COUNT(*) AS c FROM copy_events WHERE counted = 1 AND created_at >= ? AND created_at < ? GROUP BY lineup_id
        ) previous_copies ON previous_copies.lineup_id = l.id
        WHERE l.status = 'normal'
        ''',
        (recent_cutoff, recent_cutoff, previous_cutoff, recent_cutoff, previous_cutoff, recent_cutoff),
    ).fetchall()
    data = {}
    for row in rows:
        recent_score = row['recent_likes'] * 5 + row['recent_copies']
        previous_score = row['previous_likes'] * 5 + row['previous_copies']
        data[row['lineup_id']] = recent_score - previous_score
    return data
```

在 `lineups.py` 的 `list_lineups()` 中新增 `sort == 'rising'`：

```python
from scoring import rising_map
...
if sort == 'rising':
    trend_scores = rising_map()
    lineup_ids = _matching_lineup_ids(clauses, params)
    lineup_ids.sort(key=lambda lineup_id: (-trend_scores.get(lineup_id, 0), -scores.get(lineup_id, {}).get('score', 0), lineup_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_discovery.py -q -p no:cacheprovider -k rising_sort_prioritizes_recently_accelerating_lineups`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scoring.py lineups.py tests/test_discovery.py
git commit -m "feat: add rising lineup sort"
```

---

## Task 6: Add Deterministic Recommendation Strategy

**Files:**
- Create: `recommendation.py`
- Modify: `lineups.py`
- Modify: `tests/test_discovery.py`

- [ ] **Step 1: Write the failing recommendation tests**

```python
from test_auth import register_user
from test_lineup_permissions import create_lineup, auth_headers


def test_anonymous_recommended_sort_returns_items(client):
    register_user(client, username='owner', email='owner@example.com')
    create_lineup(client, name='推荐阵容A', code='#REC001')
    create_lineup(client, name='推荐阵容B', code='#REC002')

    payload = client.get('/api/lineups?sort=recommended&page=1&page_size=10').get_json()
    assert payload['total'] == 2
    assert len(payload['items']) == 2


def test_logged_in_recommended_sort_deprioritizes_own_lineups(client):
    register_user(client, username='owner', email='owner@example.com')
    own = create_lineup(client, name='自己的阵容', code='#REC003').get_json()
    other_user = client.post('/api/logout')
    register_user(client, username='other', email='other@example.com')
    other = create_lineup(client, name='别人的阵容', code='#REC004').get_json()

    payload = client.get('/api/lineups?sort=recommended&page=1&page_size=10').get_json()
    assert payload['items'][0]['id'] == other['id']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_discovery.py -q -p no:cacheprovider -k recommended`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

新增 `recommendation.py`：

```python
from datetime import datetime, timedelta

from db import get_db
from scoring import score_map


def recommended_scores(user=None):
    db = get_db()
    scores = score_map()
    fresh_cutoff = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    rows = db.execute(
        '''
        SELECT id, user_id, created_at, updated_at
        FROM lineups
        WHERE status = 'normal'
        '''
    ).fetchall()
    data = {}
    for row in rows:
        base = scores.get(row['id'], {}).get('score', 0)
        freshness_bonus = 12 if row['updated_at'] >= fresh_cutoff else 0
        own_penalty = -20 if user and row['user_id'] == user['id'] else 0
        data[row['id']] = base + freshness_bonus + own_penalty
    return data
```

在 `lineups.py` 中新增：

```python
from recommendation import recommended_scores
...
if sort == 'recommended':
    rec_scores = recommended_scores(user=user)
    lineup_ids = _matching_lineup_ids(clauses, params)
    lineup_ids.sort(key=lambda lineup_id: (-rec_scores.get(lineup_id, 0), -scores.get(lineup_id, {}).get('score', 0), lineup_id))
```

这一步先只做基础推荐：

- 匿名：热度 + 新鲜度
- 登录用户：热度 + 新鲜度 - 自己阵容惩罚

等 Phase 2 的最近浏览 / 最近复制稳定后，再补“已看过内容降权”“偏好作者加权”。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_discovery.py -q -p no:cacheprovider -k recommended`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add recommendation.py lineups.py tests/test_discovery.py
git commit -m "feat: add deterministic recommended sort"
```

---

## Task 7: Surface Rising / Recommended Tabs And Author Links On The Homepage

**Files:**
- Modify: `templates/index.html`
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Write the failing route/template tests**

```python
def test_index_page_contains_rising_recommended_and_author_link_shell(client):
    html = client.get('/').get_data(as_text=True)
    assert 'data-sort="rising"' in html
    assert 'data-sort="recommended"' in html
    assert 'author-link' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k rising_recommended_and_author_link_shell`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

首页标签补两项：

```html
<button class="tab" data-sort="rising" data-view="all">上升</button>
<button class="tab" data-sort="recommended" data-view="all">推荐</button>
```

在 `static/app.js` 卡片作者渲染中改成链接：

```javascript
const meta = document.createElement('div');
meta.className = 'card-time';
meta.innerHTML = `由 <a class="author-link" href="/author/${encodeURIComponent(lineup.owner_username)}">${lineup.owner_nickname}</a> 上传 · 赞 ${lineup.like_count} · 复制 ${lineup.copy_count} · ${lineup.updated_at}`;
```

样式：

```css
.author-link {
  color: var(--accent-strong);
  text-decoration: none;
  font-weight: 600;
}

.author-link:hover {
  text-decoration: underline;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider -k rising_recommended_and_author_link_shell`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/index.html static/app.js static/styles.css tests/test_ui_routes.py
git commit -m "feat: expose rising and recommended discovery tabs"
```

---

## Task 8: Full Verification And Documentation Touch-Up

**Files:**
- Modify: `README.md` (if route list needs mention)
- Modify: `项目交接文档.md` (if phase is implemented)

- [ ] **Step 1: Run focused growth tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_growth.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 2: Run focused author-page tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_author_page.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 3: Run focused discovery tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_discovery.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 4: Run admin and route verification**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_admin.py D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Run full suite serially**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 6: Update docs if implemented**

必须补充：

```markdown
- 新页面：
  - `/author/<username>`
- 新 API：
  - `POST /api/growth-events`
  - `GET /api/admin/growth`
  - `GET /api/authors/<username>`
- 新排序：
  - `sort=rising`
  - `sort=recommended`
- 新表：
  - `growth_events`
```

- [ ] **Step 7: Commit**

```bash
git add README.md 项目交接文档.md
git commit -m "docs: document growth analytics and discovery features"
```

---

## Why This Phase Matters

第三阶段的价值不在“再多几个页面”，而在于把站点从一个可用工具页推进到一个能持续优化的内容产品。

### It closes the growth loop

做完这一期后，后台终于能回答这些问题：

- 有多少人看了首页？
- 有多少人想登录？
- 有多少人真的登录或注册了？
- 登录以后有没有完成核心动作？

如果没有这套漏斗，后续任何“优化登录率”的工作都只能靠猜。

### It improves discovery quality

只靠“最新 / 最热 / SS”会让内容发现越来越单一。  
加上“上升”和“推荐”后：

- 新内容更容易被看见
- 稳定强内容继续保留
- 用户更容易发现符合自己兴趣的新阵容

### It gives creators public identity

作者主页是内容平台从“阵容码堆积页”转向“作者驱动内容库”的关键一步。  
即使还没有关注系统，作者主页也已经能让用户识别“谁持续产出高质量内容”。

---

## Recommended Follow-Up After This Plan

如果第三阶段完成并跑稳，下一步不建议继续堆功能，而建议开一份“优化与校准计划”，重点做：

- 推荐权重校准
- 漏斗指标阈值与异常告警
- 作者页样式与信息层级优化
- 首页推荐与上升榜的去重 / 多样性优化

---

## Detailed Delivery Order Inside Phase 3

第三阶段虽然被归成同一期，但真正落地时不能并行乱做。正确顺序应当固定，否则会出现“前台按钮先埋点、后台还没有接收表”“推荐页先上线、作者链接字段还没补”的半成品状态。

### Delivery Slice 1: Event foundation first

必须先完成：

- `db.py` 中 `growth_events` 表
- `analytics.py` 中白名单校验与写入 helper
- `lineups.py` 中 `/api/growth-events`
- `auth.py` 中注册成功 / 登录成功埋点

原因：

- 这是第三阶段所有增长统计的底座
- 如果先做后台增长看板，没有事件源，页面只能显示全 0
- 如果先做前端交互埋点，接口还没准备好，会直接产生 400 / 404 噪音

### Delivery Slice 2: Admin growth dashboard second

在埋点链路通了以后，第二块优先做后台增长概览：

- `admin.py` 新增增长接口
- `static/admin.js` 渲染增长模块
- `static/styles.css` 补后台增长卡片样式

原因：

- 这一步能最快验证埋点是否有实际业务价值
- 一旦数据展示跑通，后续再做推荐和作者页，就能同时观察用户行为是否发生变化

### Delivery Slice 3: Author identity third

第三块做作者主页：

- `app.py` 新增 `/author/<username>`
- `lineups.py` 新增作者查询接口
- `templates/author.html` 与 `static/author.js`
- 首页和详情页作者链接接入

原因：

- 这部分不依赖推荐逻辑
- 但它依赖 `owner_username` 字段补齐
- 先把作者身份链路建立起来，后续推荐位和榜单都可以稳定跳转作者页

### Delivery Slice 4: Rising and recommended fourth

第四块再做发现层：

- `scoring.py` 新增 `rising_map()`
- `recommendation.py` 新增推荐规则
- `lineups.py` 扩展 `sort=rising` 和 `sort=recommended`
- `templates/index.html` 新增排序标签

原因：

- 这是阶段内最容易“看起来能用，但实际体验不稳定”的部分
- 必须等作者链接、基础统计和已有排序都稳定后再接入

### Delivery Slice 5: Full verification and docs last

最后统一做：

- focused tests
- full pytest serial run
- 接口与交接文档更新
- 手工回归首页 / 作者页 / 后台 / 手机端

这一顺序不能颠倒。第三阶段真正危险的不是代码量，而是埋点、排序、后台统计之间的依赖链。

---

## API Contracts Locked For Phase 3

这一节不是“可以参考”，而是第三阶段实施时建议直接按这个契约走，避免前后端各写各的。

### `POST /api/growth-events`

**Purpose**

- 接收前端匿名或登录态的增长埋点事件

**Request body**

```json
{
  "event_name": "guest_click_like",
  "page_key": "home",
  "ref_lineup_id": 12,
  "payload": {
    "source": "lineup-card"
  }
}
```

**Success response**

```json
{
  "ok": true
}
```

**Validation rules**

- `event_name` 必填，且必须命中 allowlist
- `page_key` 允许值先限定为：
  - `home`
  - `auth`
  - `author`
  - `me`
- `ref_lineup_id` 可为空；有值时必须是整数
- `payload` 必须是 JSON object；不是 object 时按空对象处理
- 需要 `X-CSRF-Token`

**Failure responses**

```json
{
  "error": "不支持的事件"
}
```

状态码：`400`

```json
{
  "error": "未通过校验"
}
```

状态码：`403`

### `GET /api/admin/growth?days=7`

**Purpose**

- 提供后台最近 N 天的增长漏斗总览

**Success response shape**

```json
{
  "days": 7,
  "home_uv": 128,
  "login_entry_clicks": 39,
  "auth_page_opens": 34,
  "register_successes": 11,
  "login_successes": 18,
  "guest_like_attempts": 22,
  "guest_favorite_attempts": 15,
  "post_login_core_actions": 17,
  "conversion_rates": {
    "entry_to_auth_open_pct": 87.18,
    "auth_open_to_login_or_register_pct": 85.29,
    "login_or_register_to_core_action_pct": 58.62
  }
}
```

**Rules**

- `days` 缺省值为 `7`
- `days` 最小值为 `1`
- `days` 最大值为 `30`
- 返回比例统一保留两位小数
- 分母为 0 时比例返回 `0`

### `GET /api/authors/<username>`

**Purpose**

- 提供作者主页公开数据

**Success response shape**

```json
{
  "profile": {
    "username": "author1",
    "nickname": "作者一号",
    "created_at": "2026-05-12 10:00:00"
  },
  "summary": {
    "published_lineups": 5,
    "total_likes": 24,
    "total_copies": 73
  },
  "lineups": [
    {
      "id": 10,
      "name": "阵容A"
    }
  ]
}
```

**Rules**

- 不返回作者邮箱、IP、登录信息、举报信息
- 不返回已隐藏阵容
- 作者不存在时返回 `404`

---

## Query And Index Requirements

当前 `db.py` 只有建表，没有显式索引。第三阶段虽然用户规模不大，但新增查询比以前更偏“按时间范围聚合”，不加索引会让后台统计和榜单排序越来越慢。

### Required indexes for this phase

建议在 `db.py` 的 schema 里一起加上以下索引：

```sql
CREATE INDEX IF NOT EXISTS idx_growth_events_name_created_at
ON growth_events (event_name, created_at);

CREATE INDEX IF NOT EXISTS idx_growth_events_user_created_at
ON growth_events (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_growth_events_visitor_created_at
ON growth_events (visitor_token, created_at);

CREATE INDEX IF NOT EXISTS idx_lineups_user_status_updated_at
ON lineups (user_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_likes_lineup_created_at
ON likes (lineup_id, created_at);

CREATE INDEX IF NOT EXISTS idx_copy_events_lineup_created_at
ON copy_events (lineup_id, created_at);
```

### Why these indexes are worth adding now

- `growth_events(event_name, created_at)`：后台按事件名和时间段聚合时会直接受益
- `growth_events(user_id, created_at)`：做“登录后 10 分钟内核心动作”时要按登录用户回查
- `growth_events(visitor_token, created_at)`：游客事件到登录后行为串联时要用
- `lineups(user_id, status, updated_at)`：作者页按作者和状态拉阵容时要用
- `likes` / `copy_events` 的时间索引：`rising` 排序按时间窗统计时要用

第三阶段还不需要为了 100 人规模做复杂分库分表，但加这些索引是低成本、稳定收益。

---

## Acceptance Criteria

第三阶段不是“页面看起来有了”就算完成。下面这些验收口径建议在交付时逐项过。

### A. Growth event ingestion

- 游客从首页点击右上角登录入口，会写入 `click_login_entry`
- 打开 `/auth` 页面，会写入 `open_auth_page`
- 游客点击点赞，会写入 `guest_click_like`
- 游客点击收藏，会写入 `guest_click_favorite`
- 注册成功后，写入 `register_success`
- 登录成功后，写入 `login_success`
- 所有非白名单事件会被拒绝，返回 `400`

### B. Admin growth dashboard

- 管理员打开后台时能看到独立“增长概览”模块
- 模块在桌面端与手机端都不溢出
- 最近 7 天数据在无事件时显示 `0`，不显示空白或 `NaN`
- 转化百分比显示两位小数，分母为 0 时稳定显示 `0%`

### C. Author page

- 首页卡片作者名可以点击
- 跳转到 `/author/<username>` 后可看到作者资料和公开阵容
- 作者名不存在时返回 404 页面或错误态，不出现白屏
- 作者被隐藏的阵容不应展示

### D. Discovery ranking

- 首页新增“上升”“推荐”标签
- `hot` 排序与上线前保持兼容，结果不因第三阶段被破坏
- `rising` 排序能把最近 24 小时明显增长的阵容排前
- `recommended` 至少保证：
  - 匿名用户有结果
  - 登录用户不会把自己的阵容长期顶在最前面
  - 返回结果总数、分页和现有列表接口一致

### E. Regression safety

- 现有 `latest` / `hot` / `ss` 排序仍可正常使用
- 现有新增阵容、编辑阵容、删除阵容、举报阵容不受影响
- 后台用户管理、阵容管理、举报处理不受影响

---

## Manual QA Checklist

第三阶段完成后，建议至少做下面这组手工回归。它们比单纯看接口更接近真实线上行为。

### Guest flow

1. 打开首页
2. 点击右上角登录按钮
3. 确认后台产生 `click_login_entry`
4. 返回首页，点击任意阵容点赞
5. 确认游客被引导登录，同时后台产生 `guest_click_like`
6. 点击任意阵容收藏
7. 确认后台产生 `guest_click_favorite`

### Auth flow

1. 从首页进入 `/auth`
2. 注册一个新账号
3. 确认后台增长模块中的注册成功数增加
4. 退出登录
5. 再登录同一账号
6. 确认登录成功数增加

### Author flow

1. 用普通账号发布 2 条阵容
2. 回到首页点击作者名
3. 确认进入作者主页
4. 确认作者主页阵容数量、点赞、复制汇总正确

### Discovery flow

1. 准备至少 3 条阵容
2. 对其中 1 条在短时间内制造更多点赞/复制
3. 打开“上升”标签
4. 确认该阵容明显前置
5. 登录为作者本人再打开“推荐”
6. 确认自己的阵容没有永远置顶

### Admin mobile flow

1. 手机端打开后台
2. 检查增长概览卡片是否换行合理
3. 检查数值是否完整可见
4. 检查没有横向滚动导致关键信息被截断

---

## Rollout And Rollback Notes

第三阶段涉及数据库 schema、新接口和排序逻辑，虽然仍然是单机 SQLite，但上线时建议按下面方式推进。

### Rollout order

1. 先备份线上数据库
2. 部署后端代码和模板
3. 首次启动时让应用完成 schema 初始化
4. 用管理员账号进入后台，确认增长模块能打开
5. 用游客和普通账号各走一遍关键路径
6. 最后再对外开放正式访问

### Rollback rule

如果第三阶段上线后出现以下任一情况，应直接回滚代码：

- 首页列表接口报错
- 新增阵容失败
- 后台首页无法打开
- `/api/lineups` 任意排序返回 500

回滚时不要删除线上数据库；`growth_events` 表即使保留也不会影响旧版本核心功能。也就是说，这一期 schema 变更是“向前兼容”的，回滚风险相对可控。

---

## Phase 3 Exit Standard

第三阶段要视为“完成”，建议同时满足下面 6 条：

1. `growth_events` 表已落地，白名单校验通过
2. `/api/admin/growth` 已可返回稳定数据
3. `/author/<username>` 页面与 `/api/authors/<username>` 可正常工作
4. `sort=rising` 和 `sort=recommended` 已接入首页
5. 手机端后台增长概览可完整显示
6. 串行 pytest 与关键手工回归全部通过

如果只有页面、没有数据；或者只有数据、没有稳定回归，都不应算第三阶段完成。
