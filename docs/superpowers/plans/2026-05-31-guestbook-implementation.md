# 站长留言（Guestbook）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在首页底部新增"站长留言"功能 — 访客可提交建议，管理员在后台查看/删除留言。

**Architecture:** 遵循项目现有模式：新建 `guestbook_messages` 表 → `guestbook_service.py` 服务层 → `guestbook.py` Blueprint 路由 → `app.py` 注册 → 首页 HTML/CSS/JS 表单 → admin 后台管理 Tab。

**Tech Stack:** Flask 3.x + SQLite + 原生 JavaScript + 原生 CSS（沿用现有设计系统变量）

---

### Task 1: 添加 guestbook_messages 表到数据库 schema

**Files:**
- Modify: `db_schema.py:315`（在 EXTRA_INDEX_STATEMENTS 之前追加 CREATE TABLE）

- [ ] **Step 1: 在 SCHEMA 字符串末尾追加重建表语句**

在 `db_schema.py` 的 `SCHEMA = '''` 字符串中，`CREATE TRIGGER IF NOT EXISTS trg_favorites_cache_state_delete` 结束后、`'''` 闭合之前，插入：

```sql

CREATE TABLE IF NOT EXISTS guestbook_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    nickname TEXT NOT NULL,
    content TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
```

具体位置：在 `END;` 行之后、`'''` 行之前。

- [ ] **Step 2: 运行现有测试确认 schema 变更不影响旧功能**

```bash
pytest tests/test_db_schema_module.py tests/test_db_migrations_module.py -v
```

- [ ] **Step 3: Commit**

```bash
git add db_schema.py
git commit -m "feat: add guestbook_messages table to schema"
```

---

### Task 2: 创建服务层 guestbook_service.py

**Files:**
- Create: `guestbook_service.py`

- [ ] **Step 1: 创建服务文件**

```python
from db import get_db, now_text
from rate_limit import hit_limit


def create_message(user, data, ip):
    db = get_db()

    if hit_limit('guestbook', ip, 1, 10):
        return None, '留言过于频繁，请稍后再试', 429

    if user:
        nickname = (user['nickname'] or '').strip()
    else:
        nickname = str(data.get('nickname', '')).strip()

    content = str(data.get('content', '')).strip()

    if not nickname or len(nickname) > 20:
        return None, '昵称需为 1-20 位', 400
    if not content or len(content) > 500:
        return None, '留言内容需为 1-500 字', 400

    db.execute(
        '''INSERT INTO guestbook_messages (user_id, nickname, content, ip_address, created_at)
           VALUES (?, ?, ?, ?, ?)''',
        (user['id'] if user else None, nickname, content, ip, now_text()),
    )
    db.commit()
    return {'ok': True}, None, 201


def list_messages(db, page, page_size):
    total = db.execute('SELECT COUNT(*) AS c FROM guestbook_messages').fetchone()['c']
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size
    rows = db.execute(
        'SELECT id, user_id, nickname, content, ip_address, created_at FROM guestbook_messages ORDER BY id DESC LIMIT ? OFFSET ?',
        (page_size, offset),
    ).fetchall()
    return {
        'items': [dict(row) for row in rows],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }


def delete_message(db, message_id):
    db.execute('DELETE FROM guestbook_messages WHERE id = ?', (message_id,))
    db.commit()
    return {'ok': True}, None, 200
```

---

### Task 3: 创建路由 Blueprint guestbook.py

**Files:**
- Create: `guestbook.py`

- [ ] **Step 1: 创建路由文件**

```python
from flask import Blueprint, jsonify, request

from admin_pagination import parse_page, parse_page_size
from auth import admin_required, current_user, get_client_ip
from db import get_db
from guestbook_service import create_message, delete_message, list_messages
from route_response import respond_service_result

guestbook_bp = Blueprint('guestbook', __name__)


@guestbook_bp.post('/api/guestbook')
def post_message():
    user = current_user()
    ip = get_client_ip()
    result, service_error, status_code = create_message(user, request.get_json(silent=True) or {}, ip)
    return respond_service_result(result, service_error, status_code)


@guestbook_bp.get('/api/guestbook')
def get_messages():
    admin, error = admin_required()
    if error:
        return error
    page = parse_page(request.args)
    page_size = parse_page_size(request.args, default=20, maximum=100)
    return jsonify(list_messages(get_db(), page, page_size))


@guestbook_bp.delete('/api/guestbook/<int:message_id>')
def delete_single_message(message_id):
    admin, error = admin_required()
    if error:
        return error
    result, service_error, status_code = delete_message(get_db(), message_id)
    return respond_service_result(result, service_error, status_code)
```

---

### Task 4: 在 app.py 中注册 guestbook Blueprint

**Files:**
- Modify: `app.py:17-26`

- [ ] **Step 1: 导入并注册 Blueprint**

在 `app.py` 中，找到其他 Blueprint 的 import 区域，添加一行：

```python
from guestbook import guestbook_bp
```

在 `app.register_blueprint` 区域（`live_comps_bp` 之后），添加一行：

```python
app.register_blueprint(guestbook_bp)
```

- [ ] **Step 2: 运行测试验证注册成功**

```bash
pytest tests/test_app_pages_service.py -v
```

- [ ] **Step 3: Commit**

```bash
git add guestbook_service.py guestbook.py app.py
git commit -m "feat: add guestbook API routes and service layer"
```

---

### Task 5: 添加前端测试

**Files:**
- Create: `tests/test_guestbook.py`

- [ ] **Step 1: 创建测试文件**

```python
import pytest


def test_guest_can_post_message(client):
    resp = client.post('/api/guestbook', json={
        'nickname': '热心玩家',
        'content': '希望增加搜索功能',
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['ok'] is True


def test_logged_in_user_post_message(client, auth_client):
    client.post('/api/register', json={
        'username': 'testuser1',
        'email': 'test1@test.com',
        'nickname': '测试用户',
        'password': 'abc123',
        'captcha_token': 'test',
        'captcha_answer': '42',
    })
    resp = client.post('/api/guestbook', json={'content': '登录用户留言'})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['ok'] is True


def test_post_message_requires_nickname_for_guest(client):
    resp = client.post('/api/guestbook', json={'content': '无昵称留言'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert '昵称' in data['error']


def test_post_message_requires_content(client):
    resp = client.post('/api/guestbook', json={'nickname': 'test'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert '留言内容' in data['error']


def test_post_message_nickname_too_long(client):
    resp = client.post('/api/guestbook', json={
        'nickname': 'A' * 21,
        'content': 'test content',
    })
    assert resp.status_code == 400


def test_post_message_content_too_long(client):
    resp = client.post('/api/guestbook', json={
        'nickname': 'test',
        'content': 'A' * 501,
    })
    assert resp.status_code == 400


def test_rate_limit_guestbook(client):
    for _ in range(2):
        resp = client.post('/api/guestbook', json={
            'nickname': 'tester',
            'content': 'rate limit test',
        })
    assert resp.status_code == 429
    data = resp.get_json()
    assert '频繁' in data['error']


def test_admin_can_list_messages(client):
    client.post('/api/guestbook', json={'nickname': 'u1', 'content': 'msg1'})
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    resp = client.get('/api/guestbook')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total'] >= 1
    assert 'items' in data


def test_non_admin_cannot_list_messages(client):
    resp = client.get('/api/guestbook')
    assert resp.status_code == 401


def test_admin_can_delete_message(client):
    client.post('/api/guestbook', json={'nickname': 'u1', 'content': 'to be deleted'})
    client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    list_resp = client.get('/api/guestbook')
    msg_id = list_resp.get_json()['items'][0]['id']
    resp = client.delete(f'/api/guestbook/{msg_id}')
    assert resp.status_code == 200
    list_resp2 = client.get('/api/guestbook')
    assert all(item['id'] != msg_id for item in list_resp2.get_json()['items'])


def test_csrf_protects_guestbook_post(client):
    client.post('/api/register', json={
        'username': 'csrfuser',
        'email': 'csrf@test.com',
        'nickname': 'csrf',
        'password': 'abc123',
        'captcha_token': 'test',
        'captcha_answer': '42',
    })
    with client.session_transaction() as sess:
        sess['csrf_token'] = ''
    resp = client.post('/api/guestbook', json={'nickname': 'x', 'content': 'test'})
    assert resp.status_code == 403
```

- [ ] **Step 2: 运行测试确认全部通过**

```bash
pytest tests/test_guestbook.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_guestbook.py
git commit -m "test: add guestbook API tests"
```

---

### Task 6: 首页 HTML 添加留言表单区块

**Files:**
- Modify: `templates/index.html:105`（在 `</main>` 和 `</div>` 之间插入）
- Modify: `static/styles.css`（追加留言区块样式）
- Modify: `static/app.js`（追加渲染和提交逻辑）

- [ ] **Step 1: 在 index.html 添加留言表单 HTML**

在 `templates/index.html` 的 `</main>` 之后、`</div>` (page-shell) 之前，插入：

```html
      <section class="guestbook-section" id="guestbookSection">
        <h2 class="guestbook-title">给站长留言</h2>
        <p class="guestbook-subtitle">有任何建议或想法？欢迎留言，站长会尽快查看。</p>
        <div class="guestbook-form" id="guestbookForm"></div>
      </section>
```

- [ ] **Step 2: 在 styles.css 末尾追加留言区块样式**

```css
.guestbook-section {
  max-width: 660px;
  margin: 48px auto 0;
  padding: 28px 32px;
  border-radius: var(--radius-xl);
  background: var(--surface);
  box-shadow: var(--shadow);
}

.guestbook-title {
  margin: 0 0 4px;
  font-size: 1.15rem;
  font-weight: 700;
}

.guestbook-subtitle {
  margin: 0 0 18px;
  color: var(--muted);
  font-size: 0.9rem;
}

.guestbook-form .field {
  margin-bottom: 14px;
}

.guestbook-form label {
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-size: 0.88rem;
  font-weight: 600;
}

.guestbook-form input,
.guestbook-form textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface-solid);
  color: var(--text);
  outline: none;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.guestbook-form input {
  height: 44px;
  padding: 0 14px;
}

.guestbook-form textarea {
  resize: vertical;
  min-height: 100px;
  padding: 12px 14px;
  line-height: 1.6;
}

.guestbook-form input:focus,
.guestbook-form textarea:focus {
  border-color: rgba(201, 100, 66, 0.78);
  box-shadow: 0 0 0 4px var(--accent-soft);
}

.guestbook-submit {
  width: 100%;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--accent);
  color: #fffaf5;
  padding: 12px 18px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 160ms ease, background 160ms ease;
}

.guestbook-submit:hover {
  background: var(--accent-strong);
  transform: translateY(-1px);
}

.guestbook-submit:disabled {
  opacity: 0.5;
  pointer-events: none;
}
```

- [ ] **Step 3: 在 app.js 中追加渲染和提交逻辑**

在 `app.js` 文件末尾追加两个函数，并在 `boot()` 函数末尾添加 `renderGuestbookForm()` 调用。

修改 `boot()` 函数，在末尾 `await loadCurrentView();` 之后添加：

```javascript
renderGuestbookForm();
```

在 `app.js` 文件末尾追加：

```javascript
function renderGuestbookForm() {
  const container = document.getElementById('guestbookForm');
  if (!container) return;
  container.replaceChildren();

  const nicknameField = el('div', 'field');
  const nicknameLabel = el('label', '', '昵称');
  const nicknameInput = el('input');
  nicknameInput.type = 'text';
  nicknameInput.maxLength = 20;
  nicknameInput.placeholder = '如何称呼你';
  nicknameInput.required = true;

  if (state.user) {
    nicknameInput.value = state.user.nickname || '';
    nicknameInput.readOnly = true;
    nicknameLabel.textContent = '昵称（已登录）';
  }
  nicknameField.append(nicknameLabel, nicknameInput);

  const contentField = el('div', 'field');
  const contentLabel = el('label', '', '留言内容');
  const contentInput = el('textarea');
  contentInput.placeholder = '写下你想对站长说的话...';
  contentInput.maxLength = 500;
  contentInput.required = true;
  contentInput.rows = 4;
  contentField.append(contentLabel, contentInput);

  const submitBtn = el('button', 'guestbook-submit');
  submitBtn.textContent = '提交留言';
  submitBtn.addEventListener('click', async () => {
    const nickname = nicknameInput.value.trim();
    const content = contentInput.value.trim();
    if (!nickname) { showToast('请填写昵称'); return; }
    if (!content) { showToast('请填写留言内容'); return; }
    submitBtn.disabled = true;
    try {
      const body = { content };
      if (!state.user) body.nickname = nickname;
      await api('/api/guestbook', { method: 'POST', body: JSON.stringify(body) });
      showToast('感谢留言，站长会尽快查看');
      contentInput.value = '';
      if (!state.user) nicknameInput.value = '';
    } catch (err) {
      showToast(err.message || '留言失败，请稍后再试');
    } finally {
      submitBtn.disabled = false;
    }
  });

  container.append(nicknameField, contentField, submitBtn);
}
```

- [ ] **Step 4: 启动本地服务，访问首页验证表单展示**

```bash
python run_server.py
```

访问 `http://127.0.0.1:5000`，确认：
- 页面底部出现"给站长留言"区块
- 未登录时昵称输入框可编辑
- 登录后昵称自动填充且只读
- 留言提交流程正常

- [ ] **Step 5: Commit**

```bash
git add templates/index.html static/styles.css static/app.js
git commit -m "feat: add guestbook form to homepage"
```

---

### Task 7: 后台管理添加留言管理 Tab

**Files:**
- Modify: `templates/admin.html:43-51`（Tab 栏添加按钮）
- Modify: `static/admin.js`（状态、加载、渲染逻辑）

- [ ] **Step 1: 在 admin.html 添加 Tab 按钮**

在 `templates/admin.html` 的 Tab 栏中，"审计日志" Tab 之后、"设置" Tab 之前插入：

```html
          <button class="admin-tab" data-admin-tab="guestbook" type="button">留言管理</button>
```

- [ ] **Step 2: 在 admin.js 的 state 中添加 guestbook 状态**

在 `state` 对象中，`noticeData` 定义之后添加：

```javascript
    guestbook: { items: [], total: 0, page: 1, page_size: 20, total_pages: 1, loadedAt: 0 },
```

- [ ] **Step 3: 添加 loadGuestbook 函数**

在 `loadNotice` 函数之后添加：

```javascript
  async function loadGuestbook({ force = false } = {}) {
    if (!force && isFresh(state.guestbook.loadedAt)) return;
    const query = new URLSearchParams({
      page: String(state.guestbook.page),
      page_size: String(state.guestbook.page_size),
    });
    const payload = await api(`/api/guestbook?${query.toString()}`);
    state.guestbook = { ...state.guestbook, ...payload, loadedAt: Date.now() };
  }
```

- [ ] **Step 4: 在 activateTab 中添加 guestbook 分支**

在 `activateTab` 函数中，添加一行：

```javascript
    if (tabKey === 'guestbook') await loadGuestbook();
```

- [ ] **Step 5: 在 render 中添加 guestbook 分支**

```javascript
    if (state.activeTab === 'guestbook') root.append(renderGuestbookWorkspace());
```

- [ ] **Step 6: 在 pagination handler 中添加 guestbook 支持**

在 admin.js 中找到 pagination 的回调处理（搜索 `if (kind === 'reports')`），在那里添加：

```javascript
    if (kind === 'guestbook') await loadGuestbook({ force: true });
```

- [ ] **Step 7: 添加 renderGuestbookWorkspace 和 guestbookCard 函数**

在 `renderReportsWorkspace` 附近添加：

```javascript
  function renderGuestbookWorkspace() {
    const panel = workbenchPanel('留言管理', '访客提交的意见和建议');
    const body = panel.querySelector('.admin-workspace-body');
    const list = el('div', 'admin-list');
    if (!state.guestbook.items.length) {
      list.append(empty('暂无留言'));
    } else {
      state.guestbook.items.forEach((msg) => list.append(guestbookCard(msg)));
    }
    body.append(list, renderPagination('guestbook'));
    return panel;
  }

  function guestbookCard(msg) {
    const card = el('article', 'admin-card');
    const head = el('div', 'admin-card-head');
    head.append(el('h3', '', `#${msg.id} ${msg.nickname}`));
    const meta = el('p', 'admin-meta', `${msg.created_at} · IP: ${msg.ip_address}`);
    const content = el('p', 'admin-reason', msg.content);
    const actions = el('div', 'card-actions');
    const delBtn = button('删除留言', async () => {
      if (!confirm('确定要删除这条留言吗？')) return;
      await api(`/api/guestbook/${msg.id}`, { method: 'DELETE' });
      await loadGuestbook({ force: true });
      render();
      setNotice('留言已删除');
    }, 'small-button danger-button');
    actions.append(delBtn);
    card.append(head, meta, content, actions);
    return card;
  }
```

- [ ] **Step 8: 启动服务，登录管理后台验证留言管理 Tab**

访问 `http://127.0.0.1:5000/admin`，确认：
- "留言管理" Tab 可见
- 点击后显示留言列表
- 删除按钮可用

- [ ] **Step 9: Commit**

```bash
git add templates/admin.html static/admin.js
git commit -m "feat: add guestbook management tab to admin panel"
```

---

### Task 8: 运行全量测试验证

**Files:**
- 无新建/修改

- [ ] **Step 1: 运行全量测试**

```bash
pytest -v
```

- [ ] **Step 2: 确认无回归问题，如有失败则修复后重新运行**
```

