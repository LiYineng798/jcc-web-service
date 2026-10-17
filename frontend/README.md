# React 工作区

Flask/Jinja 拥有页面外壳；此工程构建三个独立工作区、首页卡片图标及不依赖 React 的共享头像运行包，生产不需要 Node。

| 工作区 | 入口 | 挂载根 | 提交产物 |
| --- | --- | --- | --- |
| 赛季版本更新 | `season-packages.tsx` | `#seasonPackageRoot` | `../static/admin/season-packages/` |
| 审计日志 | `audit-logs.tsx` | `#auditLogRoot` | `../static/admin/audit-logs/` |
| 个人中心 | `account-profile.tsx` | `#accountApp` | `../static/account-profile/` |
| 首页普通卡片图标 | `home-card-icons.tsx` | `#homeCardIcons`，portal 限于 `.home-lineup-card` | `../static/home-card-icons/` |
| 共享用户头像 | `avatar.ts` | 原生 `window.jccAvatar`，非 React | `../static/avatar-lab/` |

头像运行包可用 `npm run build:avatar --prefix frontend` 单独构建；参数、性能和 AGPL 源码交付见 [头像系统](../docs/avatar-system.md)。

首页图标入口仅管理装饰性 SVG，不接管列表和业务事件；组件路径、样式隔离与演示见 [AnimatedIcon 接入](../docs/home-card-icons.md)。

在 Web 仓库根目录使用 Node 22.12+：

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
```

`build` 先执行 TypeScript 检查，再构建全部工作区。
`build:audit` / `build:account` 可单独构建对应产物；它们仍检查整个工程的类型。
提交每个受影响产物目录的 `app.js`、`app.css` 和 `THIRD_PARTY_NOTICES.txt`。

- `components/ui/` 放组件，`lib/` 放共享工具/API；`@/` 指向本目录。
- 使用已有 React、Motion、Lucide、Tailwind 配置；不重新初始化工程。
- 每个工作区有独立 CSS/Tailwind 作用域，禁用全局 preflight。
- 管理页通过 mount/unmount 管理生命周期；卸载取消请求/监听，上传组件等待会话 CSRF 就绪。
- 不直接编辑打包文件。原生页面逻辑仍放在 `../static/`。
- 浏览器验证入口见 [开发与验证](../docs/development.md)，交互约束见 [前端维护](../docs/ui.md)。
