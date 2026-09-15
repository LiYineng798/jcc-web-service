# 开发与验证

启动命令见 [README](../README.md)。Python 依赖在 `requirements.txt`；
React 依赖与锁文件在 `frontend/`。仓库没有统一 lint 配置或独立 typecheck 命令，类型检查包含在前端 build 中。

## 日常检查

```powershell
python -m pytest -q
npm run build --prefix frontend
python scripts/maintenance/check_deploy_safety.py
git diff --check
```

只改原生 JS 时不必构建 React，可针对文件运行 `node --check static/admin.js` 等。
只改文档无需新增逐句断言测试；检查相对链接、旧路径引用和示例命令。
若只运行部分测试，交付时写明命令和未覆盖范围。

### 测试隔离

`app.py` 在导入时创建默认应用；通用 fixture 在仓库内使用固定临时文件。
同一目录不能同时启动两轮 pytest，也不应在带珍贵 `instance/` 的目录直接测试。
使用干净的临时副本或独立 worktree；包含正在验证的未提交改动，排除运行数据与凭据。
不要靠改 SQLite URL 来隔离文件，见 [已知边界](architecture.md#保留的技术债)。

Python 全量测试主要验证 SQLite、路由、权限、序列化、文件任务与静态模板。
PostgreSQL 相关用例含连接替身和可移植 SQL，不能替代实际 PostgreSQL 部署/备份恢复验证。

## 浏览器验证

`tests/*.cjs` 使用 Playwright；部分像素测试另用 `pngjs`。这些依赖未列入前端生产工程，
需本机安装并通过 `NODE_PATH` 使脚本可解析，同时安装 Chromium/WebKit。
以脚本顶部的环境变量和启动方式为准，不复用历史文档里的 PID、IP 或运行中预览。

| 修改范围 | 预览/浏览器入口（均在 tests/） |
| --- | --- |
| 个人中心 | `serve_account_profile_preview.py` → `account_profile_rendering.cjs`；默认 5113 |
| 账号编辑/通知浮窗 | 同一预览设置 `ACCOUNT_PROFILE_PREVIEW_PORT=5114` → `account_dialogs_rendering.cjs` |
| 审计日志 | `serve_admin_audit_preview.py` → `admin_audit_rendering.cjs` |
| 审核/通知 | `serve_lineup_moderation_preview.py` → `lineup_moderation_rendering.cjs`、`lineup_notifications_rendering.cjs` |
| 后台上传/导入赛季选择 | `serve_admin_season_picker_preview.py` → `admin_season_picker_rendering.cjs` |
| 资料/实时赛季展示 | `season_display_rendering.cjs` 自行启动服务器；手工用 `serve_season_display_preview.py` |
| 赛季上传 | `serve_season_package_preview.py` → 设置输出的 `SEASON_PACKAGE_FILE` → `season_packages.browser.cjs` |
| 完整新季/更新/回滚 | `season_lifecycle.browser.cjs` 自行启动服务器；手工用 `serve_season_lifecycle.py` |
| 工具箱/开局推荐 | `serve_lucky_openings_preview.py` → `lucky_openings_rendering.cjs` |
| 共享通知、头像、移动布局、棋盘导出 | 对应 `notifications_rendering.cjs`、`avatar_rendering.cjs`、`*_rendering.cjs`、`board_portraits.browser.cjs` |

预览的快捷登录、虚构账号和写入演练只属于测试入口，不能注册到正式应用或公开部署。
启动预览同样受 import 初始化限制，使用干净副本。截图/日志输出到被忽略的 `instance/`。
浏览器脚本参数有差异，先读目标脚本，不假设所有脚本都能自行启动服务。

UI 改动按实际受影响范围覆盖深浅主题、窄屏、键盘、错误/重试、迟到请求和权限。
桌面 WebKit 不等于真实 iPhone Safari；动态工具栏、软键盘和游戏内阵容码有效性仍需相应设备验证。

## 交付工具

`scripts/maintenance/export_web_application.py` 将服务器文件导出到相邻 `webApplication/`，
**会覆盖该目录**；它不是主仓库、数据库备份或完整开发环境。
根目录 Python 模块按文件类型纳入，避免新增模块后手工白名单漏项；静态文件、模板、文档、
部署示例与维护/赛季工具保留，运行数据、凭据和本地采集目录排除。

常规部署优先使用服务仓库的已验证 Git 提交，见 [运维](operations.md)。
依赖许可证与已构建产物需要保留；不清理其他任务的 worktree 或未提交草稿。
