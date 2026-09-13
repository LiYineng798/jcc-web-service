# 管理员资料赛季聚合

后台原来的「模拟器赛季」「资料库赛季」合并为「资料赛季」。宽屏左右两栏对照管理资料库、模拟器；1100px 及以下上下排列。桌面侧栏和手机「更多」菜单都只有一个入口；「管理资料版本」进入原有版本更新工作区。

## 操作与数据

- 两栏仍独立设置状态、排序；共享原有资料目录和当前发布版本。阵容分类、版本发布、公开页面访问规则保持原有职责。
- 启用展示、归档展示参与排序，公开序号连续为 1..N。
- 后台隐藏、停用收进默认折叠的「未展示赛季」，显示各状态数量，不提供序号或排序操作。展开状态在当前页面的保存、刷新和导航往返中保留。
- 下拉框立即保存状态；未展示条目也可点击「重新展示」，按启用状态追加到末尾。通过下拉框恢复成归档展示也追加到末尾。
- 模拟器保留「设为默认」和默认标记。默认赛季移出公开列表后自动选择剩余第一项；全关闭时为 null，首次恢复时自动成为默认。
- 保存期间禁用两栏写操作，避免同一页面重复提交；采用接口返回值更新页面。失败保持原服务端状态并显示共享错误通知。两栏加载失败分别提供重试。
- 移动端操作触点至少 44px；原生 select/details 支持键盘，保存后恢复可见控件焦点或回到对应栏标题；支持深浅色和减少动态效果设置。

## 兼容与影响

`season_visibility.py` 读取旧 `instance/season-visibility.json` 时保留公开条目的相对顺序，消除间隙，把非公开项的 order 归一为 null；只读请求不落盘，下一次管理写入保存规范化结果。不需要数据库迁移、修改正式环境变量或重新导入资料。

原 GET/PUT `/api/admin/season-display/<kind>[/<season_id>]` 路由保留。order 表示公开列表的位置；对非公开目标提交 order（包括同时关闭并排序）返回 400。模拟器和资料库的 order 独立。赛季发布包不改变这些配置。

资料库隐藏会使引用它的实时阵容站位详情无法取得公开资料目录；模拟器开放不等于资料库开放。共用资源只有在两个入口都不公开时才拒绝访客访问，沿用现有权限策略。

## 预览与验证

在 Web worktree 根目录运行：

```powershell
python tests/serve_season_display_preview.py --port 5100
```

访问 http://127.0.0.1:5100/admin，账号 `previewadmin`，密码 `Preview1234`。这是仅监听本机的临时 SQLite 预览，不读取或写入生产数据。初始公开 S18/S16.5，收纳 S17/S8，用来复现原截图；模拟器额外展示归档、隐藏的不同状态。预览只用于展示设置验收，不运行资料包 worker。关闭进程后临时设置清理，重启恢复演示初始状态。

验证命令：

```powershell
python -m pytest -q
# NODE_PATH 指向本机安装的 Playwright node_modules
node tests/season_display_rendering.cjs
node --check static/admin.js
node --check static/admin/season-display.js
git diff --check
```

浏览器脚本为 Chromium/WebKit 各启动一个临时服务，覆盖 320/390/768/1024/1440px、深浅色、侧栏与手机入口、折叠键盘操作、独立排序、恢复末尾、默认回退、全关闭、刷新持久化、失败保存和版本入口。截图存放在忽略提交的 `instance/season-display-checks`。移动端使用视口截图以避免原有固定底栏阴影影响整页截图；真实 iPhone Safari 仍需设备验收。

2026-09-13 验证结果：完整 Web suite `621 passed in 350.30s`；Chromium/WebKit 浏览器脚本均通过，包含额外的两栏加载失败重试和手动设置默认赛季检查。JS 语法、diff whitespace 和预览 `/api/health` 检查通过。分支 `codex/admin-season-hub` 在独立 worktree 实现，等待用户验收后合并 main。
