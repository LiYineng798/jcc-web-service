# 首页卡片与 AnimatedIcon

## 工程位置

现有 `frontend/` 已配置 React 19、TypeScript、Tailwind 3、Vite 和 shadcn 的 `components.json`。
`@/` 映射到 `frontend/`，所以组件目录是 **`frontend/components/ui/`**（导入写作 `@/components/ui`），
不是 Flask 仓库根部的 `/components/ui`。这个约定让 shadcn 别名、TypeScript 和构建入口解析同一份组件；不要在根目录另建重复组件库，也不要重新执行 `shadcn init` 覆盖已有配置。

- 通用组件：`frontend/components/ui/animated-icon.tsx`。
- 用户提供的八种动效示例：`frontend/components/ui/animated-icon-demo.tsx`。
- 首页增强入口：`frontend/home-card-icons.tsx`。
- 首页卡片样式：`static/home-lineup-card.css`，所有规则限定 `.home-lineup-card`。
- 现有 Tailwind 主样式是 `frontend/package-ui.css`；各 React 工作区分别作用域隔离、关闭 preflight。
- `clsx`、`motion`、`tailwind-merge` 已在依赖和 lockfile 中，不另安装重复版本。

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
# 仅重建图标入口（仍检查全部 TypeScript）：
npm run build:home --prefix frontend
```

图标入口没有 Tailwind 样式导入，因为它只渲染 SVG、使用组件内局部 CSS；这样不会把其它工作区的工具类注入首页。
组件自身不要求 Provider；内部订阅减少动态效果、页面可见性和交互状态。

## 接入边界

普通阵容仍由 `static/app.js` 渲染，数据仍来自 `/api/lineups`。
图标入口使用一个 React root 和 portals，观察卡片图标槽的增删及名称变化；列表刷新、搜索、分页和切换实时榜单会卸载旧图标，释放监听和动画。
图标资源加载失败时按钮文字和原生业务仍可使用。

`name` 对应 copy、heart、bookmark、flag、arrow-up-right、pencil、eye-off 等操作；
`preset` 通常为 auto，`amplitude=0.7`、`duration=0.48`。旗子、隐藏和编辑使用 0.5 秒、幅度 0.35 的 pulse，保持笔画可见，避免快速摆动或描线造成闪烁感；复制次数使用静态图标。图标只作装饰，按钮的可见文字和 `aria-pressed` 表达动作及状态。
普通首页卡片的复制成功先更新「已复制」按钮和头像，再等待统计；统计返回后保留按钮确认约 1.6 秒再刷新，统计失败不改成复制失败。点赞、收藏与取消收藏用按钮状态确认，不再重复弹出成功通知；错误和登录提示仍保留，其他页面及实时榜单通知不变。按钮请求期间防重复提交，刷新保留对应操作焦点。
无新增 API、权限逻辑或数据库迁移。

原始单文件组件已进行宿主兼容适配：

- 保留图标几何、八种 preset、三种 treatment、动态可见性与减少动态效果逻辑。
- 删除库级全局主题、字体下载、无关展示间样式和文档根节点写入，防止影响导航、实时榜单及账号页面。
- 不清理宿主浏览器的旧库设置；已有设置读取仍可容错。
- 包装器以正常 React 子组件方式调用实现，避免直接调用带 hooks 的函数。
- 图标使用宿主 currentColor；卡片深色主题跟随现有 `data-theme`。
- 上游 CSS 注释含未转义反引号，替换为局部 CSS 后不再造成 TS 模板字符串语法冲突。
- 保留源码许可证，并将 Cojeev 与内嵌 Lucide 几何许可证输出到首页构建产物的 notices。

## 本地预览

只在无珍贵运行数据的 worktree 内启动：

```powershell
python tests/serve_home_cards_preview.py
```

默认地址 `http://127.0.0.1:5136/`，点击“最新”查看普通阵容。
`HOME_CARD_PREVIEW_PORT` 可指定独立端口。使用虚构用户和演示阵容码；不能在游戏里使用。
沿用 loopback 专用登录 `/__preview__/login/user` 和 `/__preview__/login/admin`；这些路由只存在于预览进程，不能公开部署。
数据写入该 worktree 的忽略目录 `instance/search-device-preview/`，不连接主目录数据库。

卡片直接复用主站的 surface、text、muted、line 和 accent 系列主题变量，复制按钮、评级与选中状态使用主站强调色，不另设灰色主题。
窄屏下作者与更新日期保持同一行，昵称过长时省略；时分秒仅在桌面展示，完整时间保留在 time 的 datetime/title 中。点赞、收藏与复制次数为三个等宽居中的位置，复制按钮占满代码区一行，管理操作自然换行；不截断阵容码，不隐藏操作。
浏览器验证须覆盖深浅主题、长标题/长码/大计数、键盘、减少动态效果、复制、收藏、每日点赞状态、反馈以及封禁卡片不泄漏码。
