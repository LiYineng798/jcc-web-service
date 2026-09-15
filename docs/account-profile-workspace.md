# 个人中心 Profile 工作区

本次修改把 `/me` 从头像、概览、两段历史、反馈、阵容依次堆叠的长页面，改为可切换的个人空间。改动来自 Web 服务的 `codex/profile-workspace` 分支；用户已于 2026-09-15 验收并授权合并本地 main。公开作者页 `/author/<username>` 继续作为对外展示入口。

## 页面与行为

- **侧栏**：个人概览、我的阵容、我的收藏、最近浏览、最近复制、我的失效反馈。桌面侧栏独立于内容滚动，手机六个入口固定在底部并留出安全区。
- **个人概览**：条纹球头像、昵称、账号、角色、头像编辑、公开主页，以及原创 CSS 棋盘装饰。管理员不显示不可访问的公开作者页链接。
- **核心数据**：发布阵容、收到点赞、收到收藏、收到复制，全部来自 `/api/me/dashboard`。发布数保持现有口径，包含隐藏与封禁阵容；没有模拟趋势或百分比。
- **概览下半部分**：展示最近三条浏览记录和快捷复制；创作备忘显示隐藏阵容、自己阵容收到的待处理反馈、自己提交的反馈，并进入相应工作区或打开当前页的通知浮窗。
- **我的阵容、收藏**：使用原 `/api/lineups` 的 `view`、`q`、`page`、`page_size=4`，支持完整分页及搜索，不再只展示前 20 条。桌面采用两列、每页四条，使常规笔记本尺寸下的分页按钮也处于首屏。收藏提供复制和取消收藏；我的阵容提供编辑，编辑及封禁项均在当前页打开浮窗。
- **浏览、复制记录**：按现有接口保留的近期记录分页，每页四条，支持搜索。页面注明这不是完整历史归档。
- **失效反馈**：按全部、待处理、已处理、已驳回切换，可搜索名称和原因。保留完整原因、提交/处理时间和阵容状态；已不可访问的阵容不生成失效详情链接。现有接口返回全量自己的反馈，前端按四条分页。
- **通知浮窗**：顶部铃铛显示未读数，概览的“查看阵容处理通知”打开同一个浮窗。支持全部/未读/已读、每页六条、手动切换已读，点击后在窗内查看处理详情，再返回原通知筛选与页码。只把实际显示的版本标为已读；遇到更新冲突保留新通知的未读状态，并提供重新加载。
- **处理详情浮窗**：展示原因、处理说明、原阵容、提交的修改和历史。封禁/退回可进入窗内编辑，待审核不能重复修改，已删除阵容保留处理记录。
- **编辑浮窗**：可改名称、阵容码、赛季及普通阵容的隐藏状态；自动提取分享文案中的阵容码。普通保存后刷新当前列表，保留栏目、搜索和分页；重审提交后在窗内显示待审核状态及内容对照，审核通过前不替换原内容。旧赛季不可用时必须重新选择；并发冲突保留输入，重新加载需明确放弃草稿。
- **浮窗关闭**：关闭按钮、Escape、遮罩均回到原页面位置；有未保存修改时提供继续编辑/放弃，保存期间禁止重复提交和关闭。原生 dialog 限制背景交互，关闭后恢复焦点，长内容只在窗内滚动。兼容 `/me#lineup-notifications`，不会再跳转主页。
- **基础交互**：主题持久化、头像颜色保存同步、头像取消不写入、通知入口、退出登录、浏览器前进后退、栏目 hash 刷新恢复、方向键/Home/End 切换、减少动态效果偏好。

桌面 shell 随视口高度变化，内容过多只在内容区域滚动；1366×768、1440×900 为完整概览的主要验收尺寸。小屏幕允许内容自然滚动，底部导航持续可见；长昵称、反馈、阵容名会换行，不裁掉业务内容。

## 结构和依赖

工程已经提供 React 19、TypeScript、Tailwind 3、Vite、shadcn 配置与 `@/lib/utils`，因此不需要另建工程。`frontend/` 是前端工程根，`frontend/components/ui/` 即参考要求的 `/components/ui`；保留此位置便于使用现有别名和组件生成器。

- `templates/account.html`：账号页壳、无 JS 提示和经 `static_v()` 引用的专属资源。
- `frontend/components/ui/bento-card.tsx`：适配参考的实际工作区组件；复用 Motion 和已有 Lucide，不引入示例团队/文件数据。
- `frontend/components/ui/account-dialogs.tsx` / `.css`：通知、处理详情、编辑的浮窗及内部导航。
- `frontend/lib/account-api.ts`：可取消的请求、重试、返回页面后重新校验与保存后的数据刷新。
- `frontend/account-profile.tsx`、`account-ui.css`、`account-tailwind.config.cjs`：入口与页面范围内的样式。没有全局 Tailwind reset。
- `static/account.js`：网络请求、剪贴板降级、复制行为同步；复制成功但同步失败给出独立提示。
- `static/avatar-editor.js`：继续使用原对话框与 `PUT /api/me/avatar`；支持外部触发按钮与保存回调，组件卸载时清理。
- `static/account-profile/`：提交后的 JS、CSS、第三方许可证。仅 `/me` 加载该 bundle，生产 Flask/Nginx 无需 Node。

首次只加载当前登录用户、概览、最近浏览及未读通知计数。其他栏目按需请求；切换栏目或离开页面会取消旧请求，避免迟到响应覆盖新内容。请求错误有重试，登录失效提供重新登录入口；不把失败数据伪装成零值。现有登录、CSRF、收藏/复制权限、封禁重审和反馈 API 保持原实现。

## 本机验收

在 worktree `D:\1\codex\jcc-new\worktrees\profile-workspace` 运行：

```powershell
npm ci --prefix frontend
npm run build:account --prefix frontend
python tests/serve_account_profile_preview.py
```

- 预览：`http://127.0.0.1:5113/__preview/login`，自动进入有数据的演示账号。
- 空账号：`http://127.0.0.1:5113/__preview/login?user=empty`。
- 管理员：`http://127.0.0.1:5113/__preview/login?user=admin`。
- 普通登录也可用 `previewuser` / `Preview1234`，以上全部为虚构的本地演示账号。
- 预览独占临时 SQLite、运行文件及 loopback 端口；不读取生产数据库、不调用邮件服务。账号与阵容会在重启预览时重置。测试复制码只用于验证网页复制行为，不代表游戏内可导入阵容。
- `/__preview/login` 只定义在预览脚本内，正常应用不存在此入口。

验证命令：

```powershell
python -m pytest -q
# NODE_PATH 指向本机安装了 Playwright 的 node_modules
node tests/account_profile_rendering.cjs
# 为写入验收另启临时预览（另一个终端），保护 5113 的演示数据
$env:ACCOUNT_PROFILE_PREVIEW_PORT="5114"
python tests/serve_account_profile_preview.py
# 另一个终端运行，浏览器脚本默认连接 5114
node tests/account_dialogs_rendering.cjs
```

浏览器脚本检查 Chromium/Edge 和 WebKit，320/390/768/1024/1366/1440px、深浅主题、视口与内容边界、真实统计、超过二十条的分页、搜索、收藏写入、剪贴板、反馈状态、失败重试、迟到请求隔离、头像保存、键盘导航、hash、空账号及管理员退出。截图写入忽略的 `instance/profile-checks/`。真实 iPhone Safari 系统工具栏与触控体验仍可在验收时检查。

新增浮窗脚本在隔离预览中使用真实 API 检查普通保存、隐藏状态、阵容码提取、冲突保留草稿、重审后原内容不变、待审核锁定、已读版本竞争、通知筛选/分页返回、三处入口不导航、Escape/遮罩/焦点/未保存保护，以及 320/390px 深浅主题边界。截图写入 `instance/profile-dialog-checks/`。

## 合并与发布边界

本地验证记录（2026-09-15）：`python -m pytest -q` 全量 **666 passed**（445.91 秒）；`npm run build --prefix frontend` 三个组件构建成功，最终浮窗调整后 `npm run build:account --prefix frontend` 也通过。`node tests/account_profile_rendering.cjs` 与 `node tests/account_dialogs_rendering.cjs` 的 Chromium/Edge 和 WebKit 均通过上述检查，包括已读请求失败重试及不可用赛季。后台已有静态 bundle 重建后无内容变化。演示截图为 `instance/profile-dialog-checks/preview-notifications.png`、`preview-moderation.png`、`preview-edit.png`。

本次只有 Web 仓库变更。无需 PostgreSQL 迁移、环境变量或额外 worker。2026-09-15 已按用户确认将个人中心重设计与页内浮窗一并合并至本地 main；合并时仅补充验收记录，功能代码与上述已验证的分支一致。保留 worktree 预览，GitHub 推送由用户执行，本次未部署生产。未来发布沿用仓库既有备份、静态资源权限修复、健康检查流程。
