# 官方更新公告

`patch_note_service.py` 校验、解析内容；`patch_notes.py` 提供公开页面/API，
`admin.py` 提供后台 CRUD。内容维护走后台或带管理员 Session + CSRF 的 API。

## 内容约定

- `original_text` 保存原文纯文本；`summary_markdown` 保存精简版，不覆盖原文。
- 保留版本、数值、名称和官方来源；不确定加强/削弱时用 adjust。
- 应用不自动采集官网。来源读取与内容编辑是不同工作，原文缺失不能编造。
- 状态为 draft/published/hidden；DELETE 管理接口实际隐藏记录。
- PUT 支持部分字段更新；发布应符合当前任务授权，不把编辑自动当作发布。

`summary_markdown` 是轻量格式，支持二级分组、三种标记和旧值 => 新值，不是完整 Markdown/HTML：

```text
## 英雄调整

- [buff] 英雄名：技能伤害 220 => 240
- [nerf] 英雄名：法力值 0/30 => 10/40
- [adjust] 英雄名：机制说明
```

解析结果在原有 `summary_items` 字段上补充 `subject`（冒号前的调整对象）、`detail` 与 `changes`
（按 `；` 拆分的 attribute/from/to 行），并提供按 `##` 分组的 `summary_sections` 和列表用的 `overview`
（计数、章节名、首段摘要、前几条要点）。`对象：属性 旧值 => 新值` 的写法能得到最清晰的数值对照。

公开列表与详情页均由服务端渲染（`templates/patch_notes.html`、`patch_note_detail.html`、`patch_note_macros.html`），
`static/patch-notes.css`/`patch-notes.js` 只负责样式、筛选与目录等增强；公开页只显示 published 记录。
本地预览：`python tests/serve_patch_notes_preview.py`（虚构公告与一条草稿，默认 5150 端口，数据写入被忽略的 `instance/`）。

创建字段为 title、version、source_url、summary_markdown、original_text、status、published_at；
必填/长度/来源 URL 校验以 `patch_note_service.py` 为准。
管理接口 `/api/admin/patch-notes` 及 `/<id>`，公开页面 `/patch-notes` 及 `/<id>`。

保存后检查草稿/隐藏不公开，发布内容可读，精简标记与纯文本原文正常。
相关测试：`tests/test_patch_notes.py`、`tests/test_admin_patch_notes.py`。
赛季 ZIP 的更新说明用于管理员审核，不会自动写入这里的公开公告。
