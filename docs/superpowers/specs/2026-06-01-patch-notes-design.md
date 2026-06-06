# 更新公告功能设计

## 背景

网站需要同步《金铲铲之战》游戏官网的版本更新公告。公告内容包含两种形态：

- 原文：管理员从游戏官网公告复制粘贴，作为完整归档。
- 精简版：管理员使用 AI 或人工整理出重点数值调整，优先展示给用户。

第一版不实现自动抓取。管理员可以保存来源链接；如果粘贴了原文，就使用粘贴内容，不从来源链接抓取正文。

## 目标

1. 首页提供轻量入口，不干扰阵容浏览。
2. 公告详情页默认展示精简版，原文折叠展示。
3. 管理员可以在后台新增、编辑、发布、下线公告。
4. 精简版使用固定文本模板录入，系统负责解析为清晰的视觉展示。
5. 加强使用红色标注，削弱使用绿色标注，调整使用中性色或琥珀色。

## 非目标

- 不自动抓取游戏官网正文。
- 不解析或渲染游戏官网 HTML。
- 不在第一版做公告全文搜索。
- 不在第一版做结构化筛选，例如“只看英雄加强”或“只看装备削弱”。
- 不替换现有全站通知横幅。现有通知继续用于短消息，新公告功能独立存在。

## 前台信息架构

首页只放轻入口。入口建议放在顶部导航区域，与“阵容模拟器”同级，文案为“更新公告”。

新增页面：

- `/patch-notes`：公告列表页。
- `/patch-notes/<int:patch_note_id>`：公告详情页。

公告列表页按 `published_at` 倒序展示已发布公告。列表项显示标题、版本、发布日期和简短摘要入口。

公告详情页包含：

- 标题。
- 版本号。
- 发布日期。
- 来源链接，若管理员填写则显示“查看原公告”。
- 精简版内容，默认展开。
- 原文内容，默认折叠，通过按钮展开。

如果公告没有原文，则不显示原文折叠区，只保留精简版和来源链接。

## 后台管理

后台新增一个 tab：`更新公告`。

管理员能力：

- 查看公告列表。
- 新增公告。
- 编辑公告。
- 发布公告。
- 下线或隐藏公告。
- 删除公告时第一版使用软删除或状态隐藏，避免误删线上内容。

公告表单字段：

- `title`：标题，必填。
- `version`：版本号，选填但推荐填写，例如 `17.4`。
- `published_at`：公告发布日期，必填。
- `source_url`：游戏官网来源链接，选填。
- `summary_markdown`：精简版模板文本，必填。
- `original_text`：原文，选填。
- `status`：`draft`、`published`、`hidden`。

后台编辑器提供“插入模板”按钮，填入以下模板：

```markdown
## 英雄调整

- [buff] 名称：旧值 => 新值
- [nerf] 名称：旧值 => 新值
- [adjust] 名称：机制说明

## 羁绊调整

- [buff] 名称：旧值 => 新值

## 装备调整

- [nerf] 名称：旧值 => 新值
```

管理员可以把 AI 整理后的精简版直接粘贴到 `summary_markdown` 字段。系统不要求每条都有 `=>`，机制重做类内容可使用 `[adjust]` 纯文本说明。

## 数据模型

新增 SQLite 表 `patch_notes`：

```sql
CREATE TABLE IF NOT EXISTS patch_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    summary_markdown TEXT NOT NULL,
    original_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

建议索引：

```sql
CREATE INDEX IF NOT EXISTS idx_patch_notes_status_published_at
ON patch_notes (status, published_at DESC, id DESC);
```

状态含义：

- `draft`：草稿，后台可见，前台不可见。
- `published`：已发布，前台可见。
- `hidden`：已下线或软删除，前台不可见。

## 后端接口

新增模块：

- `patch_notes.py`：前台页面 API 和页面路由。
- `patch_note_service.py`：公告读写、校验、序列化、精简版解析。

后台 API 可先放在 `admin.py` 中调用 service；如果代码变大，再拆出 `admin_patch_note_service.py`。

前台 API：

- `GET /api/patch-notes`
  - 返回 `published` 公告列表。
- `GET /api/patch-notes/<int:patch_note_id>`
  - 只返回 `published` 公告。
  - 未发布或不存在返回 404。

后台 API：

- `GET /api/admin/patch-notes`
  - 返回所有状态公告，按更新时间或发布日期倒序。
- `POST /api/admin/patch-notes`
  - 创建公告。
- `PUT /api/admin/patch-notes/<int:patch_note_id>`
  - 更新公告内容和状态。
- `DELETE /api/admin/patch-notes/<int:patch_note_id>`
  - 第一版改为将状态置为 `hidden`。

所有后台接口复用现有 `admin_required()` 和 CSRF 机制。后台写操作记录审计日志。

## 精简版解析

第一版不引入完整 Markdown 渲染库，使用受控解析器，避免 XSS 和复杂依赖。

支持格式：

- `## 章节名`：解析为章节标题。
- `- [buff] 内容`：解析为加强条目。
- `- [nerf] 内容`：解析为削弱条目。
- `- [adjust] 内容`：解析为调整条目。
- 普通非空行：解析为普通说明文本。

视觉规则：

- `[buff]` 显示红色标签“加强”。
- `[nerf]` 显示绿色标签“削弱”。
- `[adjust]` 显示中性或琥珀色标签“调整”。
- 如果内容包含 `=>`，则 `=>` 左侧作为旧值，右侧作为新值。
- 旧值使用弱化样式。
- 新值按条目方向上色，加强为红色，削弱为绿色，调整为中性色。

原文只作为纯文本渲染。前端使用 `textContent` 或后端转义后的文本，保留换行，不允许 HTML 生效。

## 前端实现

模板：

- `templates/patch_notes.html`：公告列表页。
- `templates/patch_note_detail.html`：公告详情页。

脚本：

- 可新增 `static/patch-notes.js`，负责列表、详情加载和原文折叠。
- 也可以在模板中输出初始数据，但第一版建议使用 API，与现有首页和后台一致。

样式：

- 复用 `static/styles.css` 中现有页面壳、导航、panel、card、button 风格。
- 新增类名建议：
  - `.patch-note-list`
  - `.patch-note-card`
  - `.patch-note-summary`
  - `.patch-note-section`
  - `.patch-note-change`
  - `.change-tag-buff`
  - `.change-tag-nerf`
  - `.change-tag-adjust`
  - `.change-old-value`
  - `.change-new-value`
  - `.patch-note-original`

首页导航在 `templates/index.html` 增加 `更新公告` 链接。其他主要页面如详情页、编辑页、后台是否加入该入口可以后续统一导航时处理，第一版只要求首页入口存在。

## 错误处理

后台校验：

- 标题不能为空。
- 精简版不能为空。
- 发布日期不能为空。
- 状态必须是 `draft`、`published`、`hidden`。
- 来源链接如果填写，必须以 `http://`、`https://` 或 `/` 开头。

前台：

- 列表为空时显示空状态。
- 详情公告不存在或未发布时返回 404。
- API 加载失败时显示简短错误文案。

## 测试计划

新增测试文件建议：

- `tests/test_patch_notes.py`
- `tests/test_admin_patch_notes.py`

覆盖点：

1. 默认公告列表为空。
2. 管理员可以创建公告。
3. 管理员可以编辑公告。
4. 管理员可以发布和隐藏公告。
5. 非管理员不能访问后台公告 API。
6. 前台只展示 `published` 公告。
7. 未发布公告详情返回 404。
8. 首页包含 `更新公告` 入口。
9. 精简版解析识别 `[buff]`、`[nerf]`、`[adjust]`。
10. 原文 HTML 被安全转义，不会作为 HTML 渲染。

## 实施顺序

1. 新增 schema 和迁移补齐逻辑。
2. 新增 service 和解析器。
3. 新增前台 API 与页面路由。
4. 新增模板、前台 JS 和 CSS。
5. 在首页导航加入入口。
6. 新增后台 API。
7. 在 `static/admin.js` 增加“更新公告”工作台。
8. 补测试并运行相关测试。

