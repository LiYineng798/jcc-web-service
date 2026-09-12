# 审计日志工作台

本次变更仅涉及 Web 服务，分支 `codex/admin-audit-logs`。Flask/Jinja 继续拥有后台外壳；审计工作区采用参考 InteractiveLogsTable 的搜索、侧栏筛选与可展开行，接入真实审计 API。数据库沿用已有 `audit_logs` 和 `users`，不需要 PostgreSQL migration 或新环境变量。

## 页面与数据

- 「操作记录」显示全部历史数量，列表以日志 ID 倒序分页，默认每页 20 条，可切换 30 / 50 条。
- 时间（精确到秒）、中文动作、原始动作名、目标类型/标识、操作人分别展示。操作类型为动作分类，不能解释为执行成功状态；仅明确的 `fail_*` 动作标为异常。
- 操作人的昵称/账号来自当前用户记录，不是历史身份快照。无 actor ID 显示“系统”，找不到原用户时保留用户 ID。数字 `target_id` 与文本 `target_key` 在详情中均保留。
- 搜索涵盖中文动作、原始动作、目标类型/标识以及操作人昵称、用户名、ID。SQL 使用参数和字面 LIKE 转义，搜索不遍历快照正文。
- 同组筛选多选为 OR，类型/对象/搜索/日期之间为 AND。日期使用服务端记录的本地日期，结束日包含当天，SQL 使用半开区间。筛选选项数量始终表示全历史数量。
- 变更条件会回到第 1 页；中文输入法组合输入完成后提交，普通搜索防抖 300ms。过期请求取消，读取中不展示旧查询结果。空数据、无匹配、错误重试分别处理。
- 单次展开一条记录；详情按需获取，展示“操作前记录”和“本次记录 / 提交内容”。历史 before 和 after 不保证完整或字段对称，不能把 after 缺少的字段解释为删除。
- 服务端递归隐藏密码、摘要、token、API key 等明确敏感字段，并处理敏感 setting_key/setting_value 对。无法解析的历史 JSON 不返回原文。不会修改已有审计存储。
- React 以文本渲染快照，不执行 HTML；支持键盘展开、减少动画偏好、手机卡片布局以及系统现有浅/深色主题。

## API

`GET /api/admin/audit-logs` 保留原分页字段，增加 `total_all`、`filters`、中文标签和操作人。参数：

- `q`（最多 200 字符）
- 可重复 `target_type`、`kind`
- `start` / `end`（ISO 日期）
- `page` / `page_size`（保留原 API 上限）

`GET /api/admin/audit-logs/<int:log_id>` 返回脱敏 `before` / `after`，不存在返回 404。两个接口均需要有效管理员权限，响应设置 `Cache-Control: private, no-store`。列表查询不读取 before_json/after_json 大字段。

## 构建与目录

复用已有 React 19、TypeScript、Tailwind 3、Vite 和 shadcn 配置，无需重新初始化工程。前端工程根为 `frontend/`，故约定的 `/components/ui` 对应 `frontend/components/ui/`。保留该目录与 `@/` 别名，使参考组件和后续 shadcn 组件路径一致。

- 组件：`frontend/components/ui/interactive-logs-table-shadcnui.tsx`，以及 Badge / Button / Input。
- 入口：`frontend/audit-logs.tsx` 导出 mount/unmount，切换工作区时卸载并取消请求。
- 样式：`frontend/audit-ui.css` 与独立 Tailwind 配置，全部限定在 `#auditLogRoot`，没有全局 reset。
- 动画：显式依赖 framer-motion 12.43.0，复用已有 motion 的相同版本。
- 编译：`npm ci --prefix frontend`，`npm run build --prefix frontend` 同时构建两处 React 工作区；只构建审计用 `npm run build:audit --prefix frontend`。
- 提交 `static/admin/audit-logs/` 内的 JS、CSS 与许可证，生产无需 Node，不使用外部图像/CDN。审计数据只在进入工作区时读取。

## 本地验收

`python tests/serve_admin_audit_preview.py` 默认在 [本地预览](http://127.0.0.1:5098/admin) 启动服务，登录 `previewadmin / Preview1234`，从侧栏进入审计日志。该账号只属于本地临时数据库；内置 67 条虚构记录用于分页、详情和异常演示。端口可用 `AUDIT_PREVIEW_PORT` 修改，所有预览运行数据位于系统临时目录。关闭进程后可重新启动生成同一组示例。

验证命令：

```powershell
python -m pytest -q
npm run build --prefix frontend
# NODE_PATH 指向本机已安装 Playwright 的 node_modules
node tests/admin_audit_rendering.cjs
```

浏览器脚本针对上面的临时服务，覆盖 Chromium/WebKit、320/390/640/768/820/821/900/1024/1200/1440 宽度、浅/深主题、无横向溢出、按需读取详情、搜索、类型筛选、翻页回到第一页、空结果、文本转义、脱敏、错误重试、键盘操作和工作区切换；组合筛选与日期边界由 API 测试覆盖。截图在忽略目录 `instance/audit-checks/`。这不等同于生产 PostgreSQL 实机验收，也不覆盖真实 iPhone Safari 动态工具栏动画。

2026-09-12 验证结果：Web 全量 `python -m pytest -q` 为 **609 passed**；两个 React 工作区完整构建通过，最后样式调整后的审计单独构建通过；上述 Chromium/WebKit 浏览器回归全部通过。本次没有合并 main 或部署生产。
