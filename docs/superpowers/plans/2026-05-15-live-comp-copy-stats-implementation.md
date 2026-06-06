# Live Comp Copy Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为实时阵容排行记录复制次数，并在管理员后台通过独立 Tab 查看复制统计。

**Architecture:** 保持现有 Flask + SQLite + 原生前端脚本结构。实时阵容仍然以 JSON 文件为内容源，只在 SQLite 中新增按 `live_comp_id` 聚合的复制统计表；首页复制动作新增统计接口调用，后台单独拉取实时阵容统计列表。

**Tech Stack:** Flask、SQLite、原生 JavaScript、Pytest

---

### Task 1: 文档和失败测试

**Files:**
- Modify: `tests/test_live_comps.py`
- Modify: `tests/test_admin.py`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: 写实时阵容复制接口失败测试**

```python
response = client.post('/api/live-comps/s-01/copy', headers={'X-CSRF-Token': csrf})
assert response.status_code == 200
assert response.get_json()['copy_count'] == 1
```

- [ ] **Step 2: 运行目标测试确认失败**

Run: `python -m pytest tests/test_live_comps.py tests/test_admin.py tests/test_ui_routes.py -q -p no:cacheprovider`
Expected: FAIL，提示缺少实时阵容复制接口或后台实时阵容接口/Tab

- [ ] **Step 3: 增加后台实时阵容接口与 Tab 的断言**

```python
assert 'data-admin-tab="live-comps"' in admin_html
assert '/api/admin/live-comps' in js
```

- [ ] **Step 4: 再跑一次目标测试**

Run: `python -m pytest tests/test_live_comps.py tests/test_admin.py tests/test_ui_routes.py -q -p no:cacheprovider`
Expected: FAIL，且失败点收敛到未实现功能

### Task 2: 后端复制统计

**Files:**
- Modify: `db.py`
- Modify: `live_comps.py`

- [ ] **Step 1: 新增实时阵容复制统计表**

```sql
CREATE TABLE IF NOT EXISTS live_comp_stats (
    live_comp_id TEXT PRIMARY KEY,
    copy_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

- [ ] **Step 2: 实现实时阵容复制接口**

```python
@live_comps_bp.post('/api/live-comps/<live_comp_id>/copy')
def copy_live_comp(live_comp_id):
    ...
```

- [ ] **Step 3: 运行目标测试确认通过**

Run: `python -m pytest tests/test_live_comps.py -q -p no:cacheprovider`
Expected: PASS

### Task 3: 后台独立 Tab

**Files:**
- Modify: `admin.py`
- Modify: `templates/admin.html`
- Modify: `static/admin.js`
- Modify: `static/app.js`

- [ ] **Step 1: 增加后台实时阵容分页接口**

```python
@admin_bp.get('/api/admin/live-comps')
def admin_live_comps():
    ...
```

- [ ] **Step 2: 后台新增独立 Tab 与工作台**

```html
<button class="admin-tab" data-admin-tab="live-comps" type="button">实时阵容</button>
```

- [ ] **Step 3: 首页实时阵容复制改为先复制再记数**

```javascript
actions.append(button('复制阵容码', () => copyLiveCompCode(item)));
await api(`/api/live-comps/${encodeURIComponent(item.id)}/copy`, { method: 'POST' });
```

- [ ] **Step 4: 运行后台与路由测试**

Run: `python -m pytest tests/test_admin.py tests/test_ui_routes.py -q -p no:cacheprovider`
Expected: PASS

### Task 4: 全量验证

**Files:**
- No code changes expected

- [ ] **Step 1: 跑完整测试**

Run: `python -m pytest tests -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 2: 记录结果并准备本地预览**

确认：

- 实时阵容复制会累计
- 管理员后台可见复制次数
- 现有普通阵容功能不受影响
