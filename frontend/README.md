# Flask 页面 React 组件

本目录是独立的前端工程根目录。Flask/Jinja 继续负责后台页面，「赛季版本更新」和「审计日志」分别由 React 挂载到 `#seasonPackageRoot` 与 `#auditLogRoot`。使用 TypeScript、Tailwind 3、Vite 和用户提供的 FileUpload / InteractiveLogsTable 组件，依赖全部打入静态文件，不依赖 CDN。

个人中心 `/me` 也使用独立的 React 组件，挂载到 `#accountApp`。参考 BentoCard 已放在工程内 `/components/ui/bento-card.tsx`（仓库路径 `frontend/components/ui/bento-card.tsx`），替换演示内容后接入现有账号、阵容、收藏、历史和反馈 API。复用已有 `motion/react`、Lucide、`cn()`，无需 Hugeicons、Unsplash 图片或重复初始化 shadcn。`account-profile.tsx` 是入口，`account-ui.css` / `account-tailwind.config.cjs` 限制样式作用域；`npm run build:account --prefix frontend` 生成需要提交的 `static/account-profile/` 静态资源与许可证。默认 `npm run build --prefix frontend` 现在构建全部三个组件。详见 `../docs/account-profile-workspace.md`。

安装及构建：在仓库执行 `npm ci --prefix frontend` 和 `npm run build --prefix frontend`。已有 tsconfig、Tailwind/PostCSS 配置和 shadcn components.json，无需重新初始化。前端开发使用 Node 22.12+。

- 默认组件目录：`frontend/components/ui/`（相对于本工程就是 `/components/ui`）。保持此约定，便于组件生成器通过 `@/components/ui` 定位文件。
- 通用工具：`frontend/lib/utils.ts`，`@/lib/utils` 提供 `cn()`。
- 样式入口：`frontend/package-ui.css`；Tailwind 禁用全局 preflight，并限制在挂载根内，避免改动现有 Flask 站点。
- 工程入口：`frontend/season-packages.tsx`，导出 `mount/unmount` 供原后台调用。
- 产物：`static/admin/season-packages/`，包含 JS/CSS 及依赖许可证，需随代码提交，服务器无需 Node。

审计日志入口为 `audit-logs.tsx`，样式为 `audit-ui.css`（独立 `audit-tailwind.config.cjs` 作用域），组件为 `components/ui/interactive-logs-table-shadcnui.tsx`。其 Badge/Button/Input 遵循同一个 `@/components/ui` 路径，framer-motion 固定到已有 motion 使用的版本。默认 build 同时构建三个工作区；`npm run build:audit --prefix frontend` 可仅构建审计，产物为 `static/admin/audit-logs/`。不需要装饰图片，参考示例数据已替换为真实分页 API。见 `../docs/admin-audit-workspace.md`。

FileUpload 使用受控状态和真实 XHR 进度；后台任务通过持久 API 轮询。没有使用示例里的虚拟计时器或演示文件。组件本身只需要 Lucide 图标，不需要装饰性照片。独立 Vite 岛无需 React Server Component 的 `use client` 指令。

新增 shadcn 组件时，应从本目录运行组件 CLI，并保留现有配置与作用域。不要重新初始化覆盖已有后台主题或引入全站 CSS reset。

个人中心的通知、封禁与重审详情、编辑均使用 `components/ui/account-dialogs.tsx` 的页内浮窗；`lib/account-api.ts` 负责请求取消、重试及保存后刷新。对应样式在 `components/ui/account-dialogs.css`，沿用账号页的作用域与主题变量，不影响主页的通知入口。
