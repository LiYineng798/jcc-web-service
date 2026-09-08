# 手机 Safari 后台底部导航修复与验收

## 范围和现状

- Web 分支：`codex/admin-safari-bottom-nav`，基于 `main` 的 `922b735`。
- Worktree：`D:\1\codex\jcc-new\worktrees\admin-safari-bottom-nav`。
- Web 是 Flask 页面/API 服务，后台由 `templates/admin.html`、`static/admin.css`、`static/admin.js` 及 `static/admin/` 子模块负责；DB 服务独立维护 PostgreSQL 迁移和运维工具。本次只涉及后台布局及模板参数，无 API、数据库、环境变量或部署流程变更。
- main 和生产服务保持原状；用户验收后才合并。

## 问题判断

截图显示底部导航与 Safari 地址栏之间露出正文。原导航已是 `position: fixed; bottom: 0`，并非缺少固定定位；原背景有 3% 透明度，页面 viewport 也未启用 `viewport-fit=cover`，虽然 CSS 已引用安全区变量。

Safari 动态工具栏可导致固定元素下方暴露页面或出现绘制偏移，WebKit 有相似报告：[312149](https://bugs.webkit.org/show_bug.cgi?id=312149)、[297779](https://bugs.webkit.org/show_bug.cgi?id=297779)。用户未提供 iOS 精确版本，桌面 WebKit 不能复现真实 iPhone 浏览器工具栏，因此不能把截图归因于某个已证实的特定引擎缺陷。本次是针对截图症状的安全区修正和绘制兼容处理，最终仍需真机验收。

## 改动和效果

1. **后台专用 viewport 参数**：共享 SEO 宏增加默认关闭的 `viewport_fit_cover` 参数，仅后台启用。让后台安全区布局能覆盖屏幕边缘，公开页面的 viewport 保持原样且不产生重复 meta。
2. **实色底栏**：使用当前主题的 `--admin-surface`，滚动正文不再透过底栏背景。
3. **底栏下方背景延伸**：零高度、不可点击的伪元素使用向下阴影覆盖 Safari 可能暴露的底部区域。只延伸绘制，不移动五个按钮，不猜测地址栏高度，不引入滚动监听，不增加文档滚动长度。深浅主题同步。
4. **横屏安全区**：顶部栏、正文、底栏和“更多”弹层补齐左右安全区；底栏继续保留原有底部安全区和等高正文占位。桌面布局保持原样。

## 运行中的隔离预览

- 电脑：[后台](http://127.0.0.1:5088/admin)。
- 同一 Wi-Fi 下的 iPhone：[登录](http://10.0.60.41:5088/auth)，[后台](http://10.0.60.41:5088/admin)。电脑 IP 变化后地址需更新；网络隔离或 Windows 入站策略可能影响手机访问，未修改系统防火墙。
- 管理员：`previewadmin`，密码：`Preview1234`。只用于独立演示库。
- 后台进程 PID：`14072`；启动脚本 `instance/preview_server.py`，输出 `instance/preview.out.log` / `instance/preview.err.log`。服务监听 5088，无 debug/reloader，运行数据在本 worktree 的 `instance/`，不会进入 Git。
- 真机检查：Safari 普通/无痕模式下，概览及“更多 → 每日报告”上下滚动，让地址栏展开/收起；检查底栏下方是否仍露正文，测试横竖屏、切换主题、五个导航及更多弹层，输入后收起键盘再返回底栏。

## 验证结果

- `python -m pytest -q`：**551 passed**。
- `node tests/admin_bottom_nav_rendering.cjs`：Chromium/WebKit，浅色/深色全部通过。
- 尺寸包括 320×640、390×844、390×640、390×920、768×844、812×375、1280×844；检查正反向滚动和页面底部、顶底栏坐标、页面宽度、导航切换、更多打开/关闭和日报入口。
- 用非零安全区替换测试样式中的 env 值，验证底栏高度及按钮左右/底部边界；这属于模拟安全区，不是实际设备测量。
- 人为抬高底栏 48px，像素断言暴露区域全部为主题背景色，同时断言滚动长度不增加。此项验证背景兜底，不代表复现了 iOS 引擎故障。
- 截图：`instance/nav-checks/{chromium,webkit}-{light,dark}.png`，已检查 WebKit 浅色截图。
- 浏览器测试需 `playwright`、`pngjs`，通过 `NODE_PATH` 指向本机可用 Node 包；可用 `PREVIEW_URL` 覆盖地址。依赖本页记录的预览账号和运行中的服务。
- 本机和局域网地址 `/api/health` 均返回 `{"ok":true}`。

无数据库迁移顺序和新增环境变量要求。本次未部署生产，也未合并 main。
