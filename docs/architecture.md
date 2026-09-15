# 架构与代码入口

## 请求路径

`run_server.py` / Gunicorn → `app.py:create_app()` → blueprint 或 `app_pages.py` → 业务 service → 数据库适配或文件仓库。

`create_app()` 加载配置、注册路由/静态资源保护、初始化数据库并启动进程内任务。
模块末尾的 `app = create_app()` 会在 import 时执行；这是测试和工具导入时需要注意的副作用。

页面以 Jinja + 原生 JS 为主，三个 React 工作区是局部组件，不是整站 SPA。
后端决定权限、状态、分页与统计；前端负责请求、显示和交互，不另维护业务真相。

## 按功能定位

| 功能 | 后端入口/实现 | 前端入口 |
| --- | --- | --- |
| 页面、SEO、导航、健康检查 | `app_pages.py`、`seo.py`、`assets_version.py` | `templates/`、`seo_head.html` |
| 登录、Session、CSRF、头像、重置密码 | `auth.py`、`captcha.py`、`password_reset_service.py`、`avatar_service.py` | `auth.js`、`avatar*.js` |
| 普通阵容与作者、账号数据 | `lineups.py`、`lineup_*_service.py`、`lineups_query.py`、`lineups_serialization.py` | `app.js`、`lineup-*.js`、`author.js`、账号 React |
| 阵容审核与作者通知 | `lineup_moderation.py` / `lineup_moderation_service.py` | `admin/lineups.js`、`lineup-moderation.js`、账号浮窗 |
| 实时榜单、图片、人工补码 | `live_comps.py`、`live_comps_helpers.py`、`live_comp_manual_codes.py`、`live_comp_upload_service.py` | 首页、`live-comp-detail.js`、后台上传 |
| 管理工作台 | `admin.py`、`admin_*_service.py` | `admin.js`、`admin/`、`admin.css` |
| 留言、公告、首页通知库 | `guestbook*.py`、`patch_note*.py`、`notice_service.py` | 首页弹窗、后台、`patch-notes.js` |
| 访问/增长/复制统计、日报 | `visits.py`、`analytics.py`、`auth_activity.py`、`copy_action_service.py`、`daily_report_service.py` | 后台概览/日报 |
| 资料读取与展示策略 | `season_data_repository.py`、`season_reference_service.py`、`season_visibility.py` | `season-reference.js`、弈子详情、模拟器 |
| 资料 ZIP 上传、校验、发布 | `admin_season_packages.py`、`season_package_*.py` | 赛季版本 React |
| 固定活动攻略 | `lucky_openings.py`、`app_pages.py` | `toolbox.*`、S8 工具与 S16.5 推荐页 |

上表中的 JS/CSS 在 `static/`。模板同名或近似命名；React 入口/产物映射见 [前端工程](../frontend/README.md)。

完整接口以路由装饰器和相应测试为准，不另复制易过时的清单：

```powershell
rg -n '@.*\.route' app_pages.py auth.py captcha.py lineups.py admin.py live_comps.py guestbook.py patch_notes.py lineup_moderation.py admin_season_packages.py
```

## 数据与后台任务

| 数据 | 来源与存储 | 关键边界 |
| --- | --- | --- |
| 用户、普通阵容、互动、审核、日志、设置 | SQLite（本地）/PostgreSQL（生产） | 统一由 `db.py`、`db_adapter.py` 访问 |
| 实时阵容主体、分类、补码、图片 | `instance/live-comps*` | 统计/上传任务在 DB，榜单 JSON 和图片在磁盘 |
| 赛季基础登记与静态基准 | `static/season-data/catalog.json` 和赛季目录 | 外部档案生成，随代码交付 |
| 已上传赛季资料 | `JCC_SEASON_PACKAGE_ROOT` 下 uploads/staging/releases | DB 保存任务、发布指针和历史；文件与 DB 共同恢复 |
| 资料库/模拟器公开状态与排序 | `instance/season-visibility.json` | 与实时阵容分类、数据版本分别管理 |
| 用户本地历史/模拟器草稿 | 浏览器存储 | 登录后历史同步；不是服务端完整归档 |

三类后台任务不可混淆：

- `daily_report_worker.py`：每个 Web 进程的守护线程，幂等生成昨日快照。
- `live_comp_upload_service.py`：Web 内后台线程，处理管理员 JSON 上传和图片缓存。
- `season_package_worker.py`：独立进程，处理完整 ZIP、租约与发布恢复。设置 `JCC_PROCESS_ROLE=season-worker` 避免启动前两类线程。

目前依赖单机共享磁盘；增加 Web 节点前需解决文件共享和可见性同步。

## 数据库边界

- SQLite schema/backfill 在 `db_schema.py`、`db_migrations.py`，另组合审核和赛季包的专项 schema。
- PostgreSQL 由 DB 仓库递增 migration 管理。Web 启动只检查部分必需表，不代表核验所有迁移/字段。
- `db_adapter.py` 转换占位符和部分 SQL 方言；新增查询同时考虑两种数据库。
- 业务显式 commit/rollback。连接池按 Web 进程创建；初始化/替换持锁，借用与 SQL 不持该锁。连接归还到上下文记录的原池 `g.db_pool`。
- 审计数字 ID 用 `target_id`，赛季/日期/UUID 等用 `target_key`；敏感快照必须脱敏后输出。
- 复制行为表记录每次成功动作，计分表按五分钟桶去重；不能把运营动作数与公开有效复制数当同一个指标。

## 访问与缓存

Session Cookie 为签名数据；密码变化、禁用/删除账号会使旧认证失效。修改接口通常要求 CSRF，
令牌上传与登录/注册等例外以代码为准。访问控制必须在服务端执行。

模板资源用 `static_v()` 追加版本。普通静态资源可长缓存；可变赛季 JSON 必须重新验证；
候选包、后台、账号和会话相关响应不可被公共缓存。隐藏赛季资源也要经过 Flask，
否则 Nginx alias 会绕过检查。具体规则见 [运维](operations.md)。

## 保留的技术债

这些问题经代码核对保留，避免在文档整理中改变数据兼容性：

- SQLite 连接使用 `config['DATABASE']`，而 `JCC_DATABASE_URL` 在 SQLite 模式只参与类型判断；改 URL 路径不会重定位本地数据库。若需程序化隔离，传入 `create_app({'DATABASE': ...})`；模块 import 仍会先初始化默认应用。
- 通用 pytest fixture 使用固定文件名；部分预览脚本虽配置了临时应用，首次 import 仍有上述副作用。测试应在无运行数据的副本执行，后续可专门整理应用工厂与 fixture。
- `scripts/maintenance/backup_database.py` 使用文件复制，不是 SQLite 在线备份 API；WAL 模式下不能把它当作可靠的在线一致备份。
- DB 的旧 SQLite 导入名单未覆盖所有表，详见 [DB 运维](../../jcc-db-service/docs/operations.md)。
- 旧模拟器生成器及 `static/tools/lineup-simulator/{data,webp,blur}` 已不被当前页面加载，但仍有工具/测试依赖；外部使用者不明，暂留。
- `scripts/upload_live_comps.py` 与 `scripts/local/upload_live_comps.py` 重复且参数不同；前者还被 S16 转换上传脚本调用，暂保留 CLI 兼容。
- `admin.js`、`static/tools/lineup-simulator/app.js` 和部分 React 组件较大。现有边界仍能定位功能，暂不为整理目录而拆分业务。
