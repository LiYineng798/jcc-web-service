# 阵容失效反馈、手机后台与登录保持

## 工作范围

- Web worktree：`worktrees/feedback-mobile-session`，分支 `codex/feedback-mobile-session`，基于 Web main `3694036`。
- 只修改 Web 服务；DB 服务的迁移、生产数据库和运行数据未改动。
- 等用户验收后再合并 main；本次不部署生产。

## 逐项改动

1. **失效反馈**：依照截图，首页普通阵容卡片移除直接删除按钮，将原举报入口合并为唯一的“失效反馈”。点击填写原因，提交到原有管理员处理队列，不会删除阵容。作者页、个人反馈记录、后台桌面/手机导航、处理确认、概览和日报同步术语。原 DELETE API 的权限逻辑未改变。手机卡片两列排布，复制阵容码独占一行，长标签保持完整。
2. **手机后台顶部栏**：原先使用 sticky + backdrop-filter；截图显示 iPhone Safari 中顶部栏绘制到页面中间。改成固定在视口顶部、不透明背景、取消背景模糊，并预留等高内容空间和安全区。桌面维持原布局。桌面浏览器未复现原截图的偶发漂移，不能把 Safari 的具体内部原因认定为已经证实；修复后的 Chromium/WebKit 自动化涵盖滚动及视口高度变化，真实 iPhone 地址栏动画仍应由用户验收。
3. **保持登录**：注册及密码登录成功后启用 Flask 原生签名持久 Cookie，默认 30 天，访问时续期；退出清除浏览器会话。会话绑定当前密码凭据，密码变更使所有旧会话失效，禁用/删除账号不会继续显示为已登录。旧版本无凭据标记的会话升级后需重新登录一次。不会把密码放进 Cookie 或 localStorage。
4. **人数统计**：概览显示“登录用户活跃”，按自然日合并已登录页面访问和成功密码登录，按账号去重、排除管理员。说明中另列主动登录人数。日报同时显示两项。已有登录指标字段继续表示密码登录，不为自动恢复登录写入虚假的登录事件，也不更改最后密码登录时间。历史日报新字段显示“—”，重新生成后可从已有记录补算。

## 预览

仅在本机后台运行，工作目录为本 worktree：

- 首页：<http://127.0.0.1:5087/>，点击“最新”查看普通阵容卡片。
- 登录：<http://127.0.0.1:5087/auth>
- 后台：<http://127.0.0.1:5087/admin>
- 本地演示普通账号 `previewuser`、管理员 `previewadmin`，密码均为 `Preview1234`；仅用于这个隔离预览。
- 独立测试数据在 `instance/lineups.sqlite3`，含 25 个演示阵容和反馈记录，与主仓库/生产数据无关。
- 启动脚本 `instance/preview_server.py`；输出 `instance/preview.out.log` 和 `instance/preview.err.log`。它们属于忽略的本地运行文件，不进入提交。

## 验证

- `python -m pytest -q`：550 项通过。
- 图片补充后的卡片删除入口调整：再次运行 `python -m pytest -q tests/test_ui_routes.py tests/test_interactions.py`，110 项通过。
- `node tests/feedback_mobile_rendering.cjs`：Chromium、WebKit 各检查 320/390/768/1280px；检查上下滚动顶部坐标、手机视口高度变化、页面/按钮溢出、唯一反馈按钮及普通用户提交到后台待处理队列。
- 浏览器脚本依赖 Playwright、上述本地演示账号及正在运行的预览，可用 `PREVIEW_URL` 改端口。截图输出到 `instance/*-admin.png`、`*-card.png`、`*-feedback.png`。

## 后续部署配置

- 保持现有 `JCC_SECRET_KEY` 稳定，各进程使用同一密钥，否则重启或进程切换会丢失登录状态。
- 可设置 `JCC_SESSION_DAYS`（默认 `30`）。
- HTTPS 生产部署设置 `JCC_SESSION_COOKIE_SECURE=true`；本机 HTTP 预览保持 false。
- 仍使用 HttpOnly、SameSite=Lax Cookie。实现依据 [Flask 官方会话配置](https://flask.palletsprojects.com/en/stable/config/#permanent-session-lifetime)。
- 无新增数据库表、字段或迁移；本次只需部署 Web。部署前照常备份、部署后检查 health、登录和反馈流程。
