# 用户头像

## 行为与文件

- 所有头像均使用透明背景（包括深色模式和编辑预览）；普通阵容码框与下方操作按钮之间保留 12px 间距。

- 头像固定采用用户提供的 `yangshi/avatar.js` 条纹球体：保留几何、镂空和透明渐变，复制为无依赖的站内脚本 `static/avatar.js`。不依赖桌面源目录，也不接受上传、外部图片或形状参数。
- 新注册和管理员创建的账号随机分配八种系统颜色之一；颜色持久化，不在刷新时重新抽取。
- 个人中心展示头像和昵称，可通过“调整头像”打开原生 dialog；主页账号菜单直接进入 `/me#avatar`。
- 编辑器支持八种推荐颜色、系统选色器、六位 HEX 输入、随机配色、大/小尺寸预览、保存/取消、键盘 Escape。未保存预览不会修改账号。请求失败时保留草稿并显示错误。
- 首页仅登录时显示头像；普通阵容卡片、作者主页、阵容详情展示作者头像。卡片的作者身份与统计信息分组，适配手机和深浅主题。

## API 与数据

`PUT /api/me/avatar`，JSON 为 `{"color":"#7c3aed"}`，需要有效登录和 `X-CSRF-Token`。只允许当前账号修改；禁用账号返回 403，未登录返回 401（携带 CSRF），非法颜色、额外字段或非对象请求返回 400。响应返回更新后的公开 `user`，颜色统一小写。

`/api/me`、注册及登录响应新增 `user.avatar_color`；作者 API 新增 `profile.avatar_color`；阵容列表/详情新增 `owner_avatar_color`。颜色通过原有作者 JOIN 读取，避免列表逐条查询用户。保存后递增数据库中的 homepage cache revision，使其他 Web worker 的主页缓存失效。

## 部署顺序

1. 备份 PostgreSQL，先部署 DB 仓库并执行 `0014_user_avatars.sql`。迁移仅填充 NULL 颜色，不覆盖已有选择。
2. 再部署 Web 仓库；SQLite 本地启动自动添加并回填旧账号字段。
3. 沿用现有静态文件权限修复流程，检查头像 JS/CSS 可访问；登录、保存颜色，再以游客访问作者/阵容 API 验证一致。

不需要新增环境变量。预览使用独立 worktree 的 SQLite 和合成账号/阵容，不使用生产数据库。

## 本次验证（2026-09-06）

- Web worktree：`python -m pytest -q` → 544 passed。
- DB worktree：`python -m pytest -q` → 13 passed；本机没有 PostgreSQL 实例，因此 SQL 尚未在真实 PostgreSQL 上执行。
- Edge / Playwright：游客隐藏头像、登录展示、取消不写入、非法颜色禁用保存、保存与刷新持久化、公开作者及阵容卡片、请求失败保留草稿、Escape 关闭、390px 深浅主题、320px 弹窗无横向溢出均通过，未捕获浏览器脚本异常。
- 本地验证脚本位于协调目录 `worktrees/avatar_browser_check.cjs`，截图位于 `worktrees/avatar-review/`。这些是本地验收产物，不属于运行时依赖。
