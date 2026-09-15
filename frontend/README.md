# React 工作区

Flask/Jinja 拥有页面外壳；此工程只构建三个独立工作区，生产不需要 Node。

| 工作区 | 入口 | 挂载根 | 提交产物 |
| --- | --- | --- | --- |
| 赛季版本更新 | `season-packages.tsx` | `#seasonPackageRoot` | `../static/admin/season-packages/` |
| 审计日志 | `audit-logs.tsx` | `#auditLogRoot` | `../static/admin/audit-logs/` |
| 个人中心 | `account-profile.tsx` | `#accountApp` | `../static/account-profile/` |

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
