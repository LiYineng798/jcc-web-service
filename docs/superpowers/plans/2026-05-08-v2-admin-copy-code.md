# V2 Admin Password And Lineup Code Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add admin-side password reset UI, add responsive copy-success feedback, and normalize messy lineup-code input before persistence.

**Architecture:** Keep the existing Flask + vanilla JS structure. Reuse the current admin user update API for password resets, add lineup-code extraction on both client and server so data is cleaned centrally, and add a lightweight toast UI on the public list page for copy feedback.

**Tech Stack:** Flask, SQLite, pytest, vanilla JavaScript, existing `styles.css`

---

### Task 1: Add lineup-code normalization tests

**Files:**
- Modify: `lineups.py`
- Test: `tests/test_lineup_permissions.py`

- [ ] **Step 1: Write failing tests for create/update normalization and invalid input**

```python
def test_create_lineup_extracts_hash_prefixed_code_from_messy_input(client):
    register_user(client)
    response = create_lineup(client, code='青青#【阵容码】#斗虫伊泽-金铲铲葡葡萄#MTEwMTIzABC987')
    assert response.status_code == 201
    assert response.get_json()['code'] == '#MTEwMTIzABC987'


def test_create_lineup_rejects_unparseable_code(client):
    register_user(client)
    response = create_lineup(client, code='这不是合法阵容码')
    assert response.status_code == 400
    assert '阵容码无法解析' in response.get_json()['error']


def test_update_lineup_normalizes_code_before_save(client):
    register_user(client)
    lineup = create_lineup(client, code='#ABC123').get_json()
    response = client.put(
        f"/api/lineups/{lineup['id']}",
        json={'name': lineup['name'], 'code': '分享文本#阵容#XYZ987', 'version': lineup['version']},
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    assert response.get_json()['code'] == '#XYZ987'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_lineup_permissions.py -q -p no:cacheprovider`
Expected: FAIL because dirty lineup code is persisted as-is and invalid input is not rejected.

- [ ] **Step 3: Implement server-side lineup-code extraction**

```python
LINEUP_CODE_PATTERN = re.compile(r'[＃#]([A-Za-z0-9]+)')


def _extract_lineup_code(raw_code):
    matches = LINEUP_CODE_PATTERN.findall(str(raw_code or ''))
    if not matches:
        return None
    best = max(matches, key=len)
    return f'#{best}'
```

- [ ] **Step 4: Re-run the lineup permission tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_lineup_permissions.py -q -p no:cacheprovider`
Expected: PASS

### Task 2: Cover admin password reset behavior

**Files:**
- Modify: `static/admin.js`
- Modify: `static/styles.css`
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write a failing admin password reset test**

```python
def test_admin_can_reset_user_password_and_new_password_takes_effect(client):
    register_user(client, username='alice', email='alice@example.com', password='abc123')
    client.post('/api/logout')
    headers = login_admin(client)
    users = client.get('/api/admin/users?q=alice', headers=headers).get_json()
    user_id = users[0]['id']

    response = client.put(
        f'/api/admin/users/{user_id}',
        json={'password': 'newabc123'},
        headers=headers,
    )
    assert response.status_code == 200

    client.post('/api/logout')
    assert client.post('/api/login', json={'account': 'alice', 'password': 'abc123'}).status_code == 401
    assert client.post('/api/login', json={'account': 'alice', 'password': 'newabc123'}).status_code == 200
```

- [ ] **Step 2: Run the admin test file to verify the new test fails or exposes the missing UI-only gap**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -q -p no:cacheprovider`
Expected: PASS or near-PASS for API behavior, confirming backend support already exists and implementation scope is frontend/admin UX.

- [ ] **Step 3: Add admin password reset UI**

```javascript
actions.append(button('修改密码', () => openPasswordDialog(user)));

async function submitPasswordReset() {
  await api(`/api/admin/users/${state.passwordUser.id}`, {
    method: 'PUT',
    body: JSON.stringify({ password: nextPassword }),
  });
}
```

- [ ] **Step 4: Re-run the admin test file**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -q -p no:cacheprovider`
Expected: PASS

### Task 3: Add responsive copy-success feedback

**Files:**
- Modify: `templates/index.html`
- Modify: `static/app.js`
- Modify: `static/styles.css`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Write a failing route-level test for the toast anchor**

```python
def test_index_contains_copy_feedback_toast_anchor(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="toast"' in html
```

- [ ] **Step 2: Run UI route tests to verify failure**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: FAIL because the toast anchor is missing.

- [ ] **Step 3: Implement toast markup, behavior, and responsive styles**

```html
<div class="toast" id="toast" aria-live="polite" aria-atomic="true"></div>
```

```javascript
showToast('复制成功！祝你把把吃鸡！');
```

```css
.toast {
  position: fixed;
  right: 20px;
  bottom: 20px;
}
@media (max-width: 768px) {
  .toast {
    left: 16px;
    right: 16px;
    bottom: 16px;
  }
}
```

- [ ] **Step 4: Re-run the UI route tests**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: PASS

### Task 4: Add client-side lineup-code cleanup before submit

**Files:**
- Modify: `static/lineup-editor.js`
- Modify: `templates/lineup_form.html`
- Modify: `static/styles.css`

- [ ] **Step 1: Reuse the same extraction rule on the client**

```javascript
function extractLineupCode(rawCode) {
  const matches = Array.from(String(rawCode || '').matchAll(/[＃#]([A-Za-z0-9]+)/g)).map((item) => item[1]);
  if (!matches.length) return '';
  return `#${matches.sort((left, right) => right.length - left.length)[0]}`;
}
```

- [ ] **Step 2: Normalize before request and show a clear inline error when extraction fails**

```javascript
const normalizedCode = extractLineupCode(elements.codeInput.value);
if (!normalizedCode) {
  showMessage('阵容码无法解析，请改成以 # 开头的阵容码后再提交');
  return;
}
body.code = normalizedCode;
```

- [ ] **Step 3: Add helper copy near the textarea so users understand the accepted format**

```html
<p class="field-hint">支持从分享文案中自动提取，保存时会只保留 `#` 开头的有效阵容码。</p>
```

### Task 5: Run full verification

**Files:**
- Modify: `admin.py`
- Modify: `lineups.py`
- Modify: `templates/index.html`
- Modify: `templates/lineup_form.html`
- Modify: `static/app.js`
- Modify: `static/admin.js`
- Modify: `static/lineup-editor.js`
- Modify: `static/styles.css`
- Modify: `tests/test_admin.py`
- Modify: `tests/test_lineup_permissions.py`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 2: Start the local preview service**

Run: `python D:\1\codex\jcc\claude_project\run_server.py`
Expected: app listens on `http://127.0.0.1:5000`

- [ ] **Step 3: Commit after review if requested**

```bash
git -C D:\1\codex\jcc\jcc_git add .
git -C D:\1\codex\jcc\jcc_git commit -m "feat: improve admin password reset and lineup code UX"
```
