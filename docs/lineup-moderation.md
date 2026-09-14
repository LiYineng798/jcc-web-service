# 阵容封禁、修改重审与处理通知

## 现状与本次范围

Web 是 Flask/Jinja 应用，`admin.py` / `admin_lineup_service.py` 负责管理员阵容查询、隐藏和调分；`lineup_write_service.py` 负责用户发布、编辑和删除；`lineups_serialization.py` 统一返回操作权限。个人中心由 `templates/account.html` 与 `static/account.js` 渲染。PostgreSQL 的迁移、导入和完整性检查属于独立 DB 仓库。

原有隐藏只影响展示，没有封禁原因、用户通知或修改审核。通用管理员更新还能直接写入任意状态，用户编辑、删除以及举报处理也缺少封禁保护。本次补齐审核闭环，同时收紧这些旧入口。

Web、DB 分别在独立 worktree 的 `codex/lineup-moderation` 分支实现。用户验收前不合并 main，不部署生产。

## 页面与交互

1. **后台阵容查找**：紧凑表格显示名称/码预览、赛季、作者头像、状态、分数/点赞/复制和操作。保留服务端搜索、分页；新增状态、赛季和时间顺序筛选。状态数量为全站数量，表格按当前筛选取数据。
2. **封禁**：管理员填写 1–500 字原因后确认，阵容立即退出公开列表。原名称、阵容码和赛季保留。原因对作者可见。
3. **修改审核**：侧栏和手机 More 菜单均提供入口及待审数量。默认最早更新优先。原阵容和提交版本并排呈现，改变的字段高亮；手机纵向排列。审核支持通过或填写原因退回。
4. **必要的恢复能力**：封禁/退回状态可填写原因解除封禁，按原内容恢复。待审核记录必须通过审核或退回，避免误把“解除封禁”当成采用新版本。
5. **调分**：把连续浏览器 prompt 改成同一表单，集中填写点赞/复制修正总值，允许 -1000000 至 1000000 的整数。原始互动事件保留。
6. **个人中心**：数据概览后是“阵容处理通知”，支持未归档、未读、已读、归档和全部筛选、分页、显式标记与移出归档。归档不改变封禁/审核状态。封禁、审核通过、退回和解除封禁均重新置为未读并移出归档。
7. **用户修改**：“修改并提交重审”进入已有独立编辑页，可编辑名称、阵容码和赛季。退回后预填上次提交内容，原阵容直到通过审核才替换。待审时表单冻结，隐藏直接展示开关，提供返回处理通知的链接。
8. **处理记录**：管理员和作者均可查看自己的对应记录，每次提交内容和处理原因保留。公开列表、非作者详情、作者公开主页和历史列表不会向其他用户开放封禁内容。

UI 借鉴用户提供的表格示例：身份列、柔和状态标签、紧凑行内操作和响应式布局。使用项目现有 Flask/Jinja 与独立原生 JS 模块实现，主题、头像和通知复用现有组件。附件里的 React/shadcn 安装命令作为参考内容处理；本次没有增加 npm 或运行时依赖。

## 状态规则

| 当前状态 | 操作 | 结果 | 公开内容 |
| --- | --- | --- | --- |
| 正常或隐藏 | 管理员封禁 | `lineups.status=banned`, `state=banned` | 下架，原内容保留 |
| 封禁或退回 | 作者提交修改 | `state=pending` | 仍封禁，提交内容单独保存 |
| 待审核 | 管理员通过 | `state=approved` | 采用提交版本，恢复封禁前展示状态 |
| 待审核 | 管理员退回 | `state=rejected` | 仍封禁，允许再次提交 |
| 封禁或退回 | 管理员解除封禁 | `state=released` | 按原版本恢复封禁前展示状态 |

封禁前为隐藏的阵容在审核通过或解除封禁后仍为隐藏，避免意外公开。处于封禁、待审核或退回状态时，用户和管理员均不能通过旧接口删除、隐藏/恢复、直接编辑或调分；互动接口拒绝复制统计、点赞、收藏和重复反馈。作者重新发布相同封禁码、把该码写入自己的其他阵容也会被拒绝。规则针对具体阵容记录及作者原码；没有引入全站模糊文本黑名单。

## 实现边界

- `lineup_moderation.py`：登录/管理员/CSRF 保护的接口和 private/no-store 策略。
- `lineup_moderation_service.py`：状态转换、版本校验、通知状态、事件记录与批量附加管理数据。
- `lineup_moderation_schema.py`：SQLite 表结构，随 `SCHEMA` 初始化已有和新数据库；对应 PostgreSQL migration 0016。
- `static/admin/lineups.js`：后台表格和调分弹窗；`static/lineup-moderation.js`：共享处理详情、版本对比、确认表单与历史。
- `static/account-moderation.js`：个人中心通知；`static/moderation.css`：限定功能范围的响应式与深浅主题。

所有审核操作必须提交整数 `version`，使用数据库条件更新锁定当前阵容版本。修改、状态变化、通知更新、处理事件和审计在同一事务内落库。重复审核、过期页面及并发旧编辑返回 409，不能覆盖新决定。读取/归档通知提交独立 `revision`，旧通知不能标记新审核结果为已读。

用户每次重审必须至少变更一项，待审核期间禁止重复提交。通过审核时重新校验赛季可用性；若赛季已经隐藏，管理员应退回，让用户选择可用赛季。原始互动数据、作者和阵容 ID 均保留。通知只在站内展示，没有邮件或外部消息发送。

## API

| 方法 | 地址 | 用途 |
| --- | --- | --- |
| GET | `/api/admin/lineups` | 新增 `status=all/normal/hidden/banned/pending`、`season`、`order=newest/oldest`，返回分组数量与当页处理状态 |
| GET | `/api/admin/lineup-moderation-summary` | 待审核数量 |
| GET | `/api/lineups/<id>/moderation` | 作者/管理员读取原内容、提交内容及记录 |
| POST | `/api/admin/lineups/<id>/moderation/ban` | 封禁，`version` + 必填 `reason` |
| POST | `/api/admin/lineups/<id>/moderation/approve` | 通过，`version` + 可选 `reason` |
| POST | `/api/admin/lineups/<id>/moderation/reject` | 退回，`version` + 必填 `reason` |
| POST | `/api/admin/lineups/<id>/moderation/release` | 按原版本解除封禁，`version` + 必填 `reason` |
| POST | `/api/lineups/<id>/revision` | 作者提交 `name/code/season_id/version` |
| GET | `/api/me/lineup-notifications` | `status=active/unread/read/archived/all` 和分页 |
| PUT | `/api/me/lineup-notifications/<id>` | `status=unread/read/archived` 与 `revision` |

## 本地预览与验收

运行 `python tests/serve_lineup_moderation_preview.py`，默认地址 `http://127.0.0.1:5112`，可用 `LINEUP_MODERATION_PREVIEW_PORT` 调整。进程绑定 loopback；使用独立临时 SQLite、赛季配置和虚构数据，重启会重新生成演示场景，测试和生产运行文件互不共享。

- 管理员：`previewadmin`；普通用户：`previewuser`；另一个用户：`previewother`。
- 演示密码均为 `Preview1234`，只用于隔离预览。
- 管理页 `/admin`，个人页 `/me#lineup-notifications`。可用不同浏览器/无痕窗口同时登录两种角色。
- 预置正常、隐藏、封禁、待审、退回和审核通过记录；名称“灵能卡莎”可用于手工修改重审。

验收建议：管理员封禁一条普通阵容 → 用户查看原因并标记/归档 → 用户修改三项内容后提交 → 管理员对比并退回 → 用户查看新的未读原因，再修改提交 → 管理员通过 → 用户看到通过通知及已恢复的内容。原先隐藏的记录应恢复隐藏。

自动验证：Web `python -m pytest -q`；DB `python -m pytest -q`；启动独立预览后，以已配置 Playwright 的 `NODE_PATH` 执行 `node tests/lineup_moderation_rendering.cjs`。浏览器覆盖 Chromium/Edge 和 WebKit、320/390/768/1440px、深浅主题、模态窗、归档、调分及完整封禁重审链路，截图在 `instance/moderation-checks/`。真机 Safari 的系统工具栏/触控仍以设备验收为准。

2026-09-14 本地最终结果：Web 全量 **660 passed**，DB 全量 **17 passed**，Chromium 与 WebKit 端到端均通过。最终预览已重置为初始虚构场景，保留后台进程供验收。`instance/moderation-preview.pid` 和对应 stdout/stderr 日志只属于本次本地预览，不提交。

效果截图：[后台表格](screenshots/lineup-moderation/admin-desktop.png)、[审核对比](screenshots/lineup-moderation/review-desktop.png)、[手机通知](screenshots/lineup-moderation/account-mobile.png)、[手机修改重审](screenshots/lineup-moderation/editor-mobile.png)。

## 合并与部署

先合并并部署 DB 的 `0016_lineup_moderation.sql`，然后部署 Web；Web 的 PostgreSQL 启动检查要求两个新表存在。无需新增生产环境变量或独立 worker。

部署前按现有运维流程备份，之后执行 `/api/health`、关键 API 和 DB 完整性检查。此次仅做本地预览，迁移尚未在生产 PostgreSQL 执行；DB 单元测试执行可移植 SQL 约束并验证导入/完整性工具，不等于真实 PostgreSQL 上线验收。回滚需使用相互匹配的 Web/DB 备份并先停止写入，避免旧 Web 的通用编辑路径绕过已经生效的封禁。
