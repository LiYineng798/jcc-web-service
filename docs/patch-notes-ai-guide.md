# 更新公告改写指南

本文档给后续接手的 AI 使用，目标是让 AI 能在不破坏现有数据和页面结构的前提下，帮管理员整理、改写、发布或隐藏“更新公告”。

## 功能位置

- 首页入口：顶部导航的“更新公告”。
- 公告列表页：`/patch-notes`。
- 公告详情页：`/patch-notes/<id>`。
- 后台入口：`/admin` 页面里的“更新公告”标签。
- 公开读取 API：
  - `GET /api/patch-notes`
  - `GET /api/patch-notes/<id>`
- 后台管理 API：
  - `GET /api/admin/patch-notes`
  - `POST /api/admin/patch-notes`
  - `PUT /api/admin/patch-notes/<id>`
  - `DELETE /api/admin/patch-notes/<id>`，实际效果是把公告状态改为 `hidden`，不是物理删除。

## 重要原则

1. 优先使用后台页面或后台 API 改写公告，不要直接改 SQLite 数据库。
2. 不要把游戏官网原文渲染成 HTML。原文应作为纯文本保存到 `original_text`。
3. 这一版不实现自动抓取。如果用户粘贴了原文，就使用用户提供的原文，不要主动联网抓取。
4. 改写只改公告内容，不要顺手改公告页 UI、颜色、路由、数据库结构或迁移逻辑。
5. 发布前确认移动端和桌面端都能阅读，特别是长数值、装备名、羁绊名不要挤出容器。

## 数据字段

后台保存公告时使用以下字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `title` | 是 | 公告标题，例如 `17.4 更新公告` |
| `version` | 否 | 版本号，例如 `17.4` |
| `source_url` | 否 | 来源链接，只允许 `http://`、`https://` 或站内 `/` 开头 |
| `summary_markdown` | 是 | 面向用户阅读的精简版内容 |
| `original_text` | 否 | 用户粘贴的原文，纯文本保存 |
| `status` | 是 | `draft`、`published`、`hidden` |
| `published_at` | 是 | 发布日期或发布时间文本，例如 `2026-06-01` |

状态含义：

- `draft`：草稿，后台可见，前台不可见。
- `published`：已发布，前台列表和详情页可见。
- `hidden`：已隐藏，后台保留记录，前台不可见。

## 精简版写法

`summary_markdown` 使用项目内置的轻量格式，不是完整 Markdown 渲染器。

支持的格式：

```text
## 英雄调整

- [buff] 英雄名：旧值 => 新值
- [nerf] 英雄名：旧值 => 新值
- [adjust] 英雄名：机制说明

## 羁绊调整

- [buff] 羁绊名：旧值 => 新值
```

显示规则：

- `## 标题` 会显示为分组标题。
- `- [buff] ...` 会显示为“加强”，红色倾向。
- `- [nerf] ...` 会显示为“削弱”，绿色倾向。
- `- [adjust] ...` 会显示为“调整”，中性色。
- 如果一行里包含 `=>`，前后会被拆成旧值和新值。
- 其他普通文本会按普通说明展示。

建议写法：

```text
## 英雄调整

- [buff] 亚索：技能伤害 220/330/520 => 240/360/560
- [nerf] 阿狸：法力值 0/30 => 10/40
- [adjust] 瑟提：技能会优先选择当前目标附近敌人

## 装备调整

- [buff] 巨人捕手：额外伤害 20% => 25%
```

不要这样写：

```text
- [加强] 亚索加强
- buff 亚索：220到240
<p>原文 HTML</p>
```

原因：

- 解析器只识别 `[buff]`、`[nerf]`、`[adjust]`。
- HTML 不会作为公告正文渲染，且不应该保存到精简版里。

## 改写流程

### 1. 先判断任务类型

- 如果用户要“整理公告”：根据原文提炼 `summary_markdown`，保留 `original_text`。
- 如果用户要“修改已发布公告”：先读取现有公告，确认要改的是哪一条，再更新。
- 如果用户要“隐藏公告”：调用删除接口或在后台点隐藏，不要物理删除数据库记录。
- 如果用户只给了版本和来源链接、没有原文：这一版不要抓取，向用户要原文或只创建草稿。

### 2. 改写内容

改写时优先做到：

- 保留版本、数值、英雄名、羁绊名、装备名的准确性。
- 把长篇说明拆成“英雄调整 / 羁绊调整 / 装备调整 / 系统调整”等分组。
- 对数值变化使用 `旧值 => 新值`。
- 对机制说明使用 `[adjust]`，不要硬拆成旧值新值。
- 不确定加强还是削弱时，用 `[adjust]`，不要猜。

### 3. 保存为草稿或发布

默认建议先保存为 `draft`，用户确认后再改为 `published`。

只有用户明确要求“发布”“上线”“前台可见”时，才设置：

```json
{
  "status": "published"
}
```

## 后台 API 示例

以下示例用于说明请求结构。真实操作时必须带管理员登录态和 CSRF Token，建议优先通过后台页面操作。

创建草稿：

```http
POST /api/admin/patch-notes
Content-Type: application/json

{
  "title": "17.4 更新公告",
  "version": "17.4",
  "source_url": "https://example.com/news/patch-17-4",
  "published_at": "2026-06-01",
  "status": "draft",
  "summary_markdown": "## 英雄调整\n\n- [buff] 亚索：技能伤害 220/330/520 => 240/360/560",
  "original_text": "这里粘贴用户提供的游戏官网原文。"
}
```

发布已有公告：

```http
PUT /api/admin/patch-notes/1
Content-Type: application/json

{
  "status": "published"
}
```

隐藏公告：

```http
DELETE /api/admin/patch-notes/1
```

注意：`PUT` 支持部分字段更新，未传字段会沿用原值。但如果要大幅改写公告，建议先读取完整记录，确认没有覆盖掉 `original_text`、`published_at` 等字段。

## 代码位置

- 数据校验和解析：`patch_note_service.py`
- 公开页面和公开 API：`patch_notes.py`
- 后台 API：`admin.py`
- 后台界面：`static/admin.js`、`templates/admin.html`
- 公告前台渲染：`static/patch-notes.js`
- 前台页面模板：`templates/patch_notes.html`、`templates/patch_note_detail.html`
- 样式：`static/styles.css`
- 表结构和迁移：`db_schema.py`、`db_migrations.py`

通常只改公告内容时，不需要改这些代码文件。

## 验证清单

改写或发布后至少检查：

1. 后台“更新公告”列表能看到目标公告。
2. 草稿或隐藏状态不会出现在 `/patch-notes`。
3. `published` 状态会出现在 `/patch-notes`。
4. 详情页 `/patch-notes/<id>` 能打开。
5. 精简版里的 `[buff]`、`[nerf]`、`[adjust]` 显示正常。
6. 原文在详情页折叠区域中作为纯文本显示。
7. 手机宽度下长文本、长数值、按钮不重叠。

可用测试命令：

```bash
pytest tests/test_patch_notes.py tests/test_admin_patch_notes.py tests/test_schema.py tests/test_ui_routes.py -k "patch_note or patch_notes or schema_creates_required_tables" -q
```

## 常见错误

- 把 `status` 写成 `publish`。正确值是 `published`。
- 把“削弱”写成 `[weak]` 或 `[削弱]`。正确值是 `[nerf]`。
- 把原文放进 `summary_markdown`，导致前台精简版过长。
- 直接改数据库，绕过审计日志和校验。
- 发布前忘记设置 `published_at`。
- 没有原文却主动抓取网页。这一版不做抓取。
