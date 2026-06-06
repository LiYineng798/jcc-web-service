# 站长留言（Guestbook）功能设计

## 概述

在首页底部新增"站长留言"功能，供所有访客向站长反馈建议。留言仅管理员在后台可见（意见箱模式）。

## 决策记录

| 决策点 | 选择 |
|---|---|
| 谁能留言 | 所有访客（游客 + 登录用户）|
| 表单字段 | 昵称 + 留言内容 |
| 可见范围 | 仅管理员后台可见 |
| 防刷机制 | IP 频率限制（每 IP 每 10 分钟限 1 条）|
| 管理操作 | 查看列表 + 删除 |

## 数据库

新建 `guestbook_messages` 表，纳入 `db_schema.py` 的 SCHEMA：

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

- `user_id` — 登录用户关联，游客为 NULL
- `nickname` — 游客填写的昵称（1-20 字），登录用户用 `users.nickname`
- `content` — 留言内容（1-500 字）
- `ip_address` — 记录来源 IP

## 后端

### 路由 — `guestbook.py`（新建 Blueprint）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| `POST` | `/api/guestbook` | 公开 | 提交留言 |
| `GET` | `/api/guestbook` | admin_required | 分页查看留言列表 |
| `DELETE` | `/api/guestbook/<id>` | admin_required | 删除单条留言 |

在 `app.py` 中注册 Blueprint。

### 服务层 — `guestbook_service.py`（新建）

- `create_message(user, data, ip)` — 校验昵称/内容长度 → 频率检查 → 写入 DB
- `list_messages(db, page, page_size)` — 分页查询，最新在前
- `delete_message(db, message_id)` — 删除单条

### 频率限制

沿用 `rate_limit.py`：`hit_limit('guestbook', ip, 1, 600)`

### CSRF 保护

POST 请求沿用 `auth.py` 的 `require_csrf()` 中间件（X-CSRF-Token 头）。

## 前端

### 首页表单（`index.html`）

在 `<main>` 结束之后、`</div>` (page-shell) 关闭之前，插入留言区块：

- 区块标题："给站长留言"
- 登录用户：昵称自动填充且只读，显示留言文本框 + 提交按钮
- 游客：显示昵称输入框 + 留言文本框 + 提交按钮
- 文本框限制 500 字
- 提交后 toast 提示"感谢留言，站长会尽快查看"

### 样式（`styles.css`）

新增 `.guestbook-section`、`.guestbook-form`、`.guestbook-field` 等样式，沿用现有 CSS 变量（`--surface`、`--radius-lg`、`--accent`）。

### 前端逻辑（`app.js`）

在 `boot()` 中调用 `renderGuestbookForm()`，根据 `state.user` 判断展示游客版还是登录版。

### 后台（`admin.html` + `admin.js`）

- Tab 栏新增 "留言管理" Tab
- 列表展示：昵称、内容、时间、IP、删除按钮
- 分页，默认 20 条/页
- 参照 "举报管理" Tab 的表格和分页模式

## 测试

- `tests/test_guestbook.py`：覆盖提交留言（游客/登录）、频率限制、管理员列表/删除
- `tests/test_ui_routes.py`：确认首页渲染包含留言表单

## 文件清单

| 操作 | 文件 |
|---|---|
| 新建 | `guestbook.py`（Blueprint 路由）|
| 新建 | `guestbook_service.py`（服务层）|
| 新建 | `tests/test_guestbook.py`|
| 修改 | `db_schema.py`（新增表定义）|
| 修改 | `app.py`（注册 Blueprint）|
| 修改 | `templates/index.html`（表单区块）|
| 修改 | `templates/admin.html`（Tab）|
| 修改 | `static/styles.css`（样式）|
| 修改 | `static/app.js`（渲染逻辑）|
| 修改 | `static/admin.js`（管理逻辑）|
