# 用户管理表格改造

- 分支：codex/admin-users-table，从 main 132c335 建立独立 worktree，等待用户验收后合并。
- 桌面：头像、昵称、账号、邮箱组成用户列；状态、角色、注册日期、操作独立排列。
- 手机：同一份 DOM 转成卡片，搜索与按钮适配窄屏；保留固定导航。
- 头像来自 users.avatar_color，复用 avatar.js，不使用示例人物或外部图片。
- 原有服务端每页 10 条、搜索防抖/取消请求、密码校验、禁用确认保持不变。未增加示例中的虚假邀请、批量删除等业务。
- 原项目没有 React、TypeScript、Tailwind 或 shadcn；此次将参考视觉移植到原生页面。现有组件归 static/admin/，样式归 static/admin.css，无需建立无运行用途的 components/ui。若未来独立迁移 React，可用 Vite react-ts、Tailwind Vite 插件、shadcn init 建立构建，再通过 components.json 指向 components/ui；这不属于本次运行依赖。
- 数据库仅多选取已有列，无数据库迁移、新环境变量或生产部署。

## 本地验收

预览地址 http://127.0.0.1:5091/admin ，账号 previewadmin，密码 Preview1234；仅用于本机隔离演示，使用 instance/preview.sqlite3 合成数据。

浏览器检查：设置 NODE_PATH 为本机 Playwright 安装目录，然后 node tests/admin_users_rendering.cjs。覆盖 Edge、WebKit，320/390/768/1440px，深浅色，头像加载、溢出、搜索/空状态/清空、密码不一致校验与取消。截图在 instance/users-checks（本地文件，不提交）。手机完整长截图可能包含已有固定底栏阴影延伸，验收采用视口截图；真实 iPhone 仍需设备确认。

预览重启：在 worktree 根目录运行 `python instance/preview_users.py`（端口 5091）。局域网可尝试 http://10.0.134.101:5091/admin ，实际访问取决于本机网络与防火墙。

最终验证：`python -m pytest -q` → 563 passed（145.60s）。`node tests/admin_users_rendering.cjs` → Edge / WebKit passed，包含分页往返验证。`git diff --check` 通过；预览 `/api/health` 返回 200。

注册时间完整显示为 YYYY-MM-DD HH:mm:ss（例如 2026-09-09 21:00:57），保留接口的时间值，不做浏览器时区转换。
