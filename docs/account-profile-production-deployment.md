# 2026-09-15 个人中心与页内浮窗上线记录

站点：`https://jcc.np5.top`；服务器：`114.134.186.41`。用户验收个人中心与三处浮窗、合并 main 并自行推送 GitHub 后，授权执行本次更新。流程依据 [服务器更新手册](server-update-guide.md)。

## 已部署版本

| 项目 | 更新前 | 更新后 |
| --- | --- | --- |
| Web main | `bd82fdd97136020a0226364aff84f93a8c4771b4` | `2c82ed3557870b9dc131bfa343ce5bfcd31ce954` |
| DB 仓库 | `52cc22cf900b1d1207fb80e9cb326c95f41dd6bd` | 保持原版本 |
| PostgreSQL 迁移 | `0016_lineup_moderation` | 保持原版本 |

本地与服务器均从 GitHub 核对 Web main 的完整提交号，再在干净的服务器 main 上快进。DB GitHub main 新增的内容只有上一轮部署文档，没有新迁移。本次更新个人中心布局、通知/处理详情/编辑浮窗及已构建的静态资源；不需要 Node、数据库迁移、依赖升级或配置变更。Web 与 DB 虚拟环境的 `pip check` 均通过。

北京时间 2026-09-15 10:03:31 开始停止 `jcc` 与 `jcc-season-worker`，完成一致性备份后更新 Web，归还 `jcc:jcc` 所有权并确保静态资源可供 Nginx 读取，再启动两个服务。从停止操作开始至健康恢复共 **8.28 秒**。

## 验证结果

- 赛季导入及实时阵容上传均无 queued/running 任务才进入切换。
- 数据库原有 14 项完整性检查在更新前后通过。
- 停写切换期间，`users`、`lineups`、`likes`、`favorites`、`reports`、`lineup_moderation`、`lineup_moderation_events`、`season_release_packages`、`season_active_releases` 共 9 张表的行数和内容指纹完全一致。
- **35 项 HTTPS 检查通过**：公共页面/API、访客访问保护、登录后的个人中心 HTML、概览/阵容/收藏/历史/反馈 API、三种通知筛选、编辑数据与版本、重审详情、管理员页面和权限隔离。
- 个人中心 HTML 正确引用带版本号的新资源；新 JS/CSS、账号桥接脚本、头像编辑脚本的线上 SHA-256 与部署文件一致，静态缓存策略正常。通知和处理详情接口保持 private/no-store，生产不存在 `/__preview/login` 入口。
- 受保护接口通过只驻留维护进程内存的临时签名会话验证；没有创建测试用户或修改密码，也没有在生产执行编辑、提交重审、标记已读等业务写操作。具体交互已在部署前通过 Chromium/Edge、WebKit 和全量 **666 项 pytest**，见 [功能验收记录](account-profile-workspace.md)。
- 最终确认 Web、赛季 worker、Nginx、PostgreSQL 四个服务均 active，Web/worker `NRestarts=0`，切换后的服务日志无 error、traceback、critical。从本地网络独立请求公网 `/api/health` 也返回 200、`{"ok":true}`。

## 备份与回滚

服务器备份目录：`/opt/jcc/deploy-backups/profile-workspace-20260915-100252/`，目录为 root 专属权限。

| 文件 | 内容 | 字节数 |
| --- | --- | ---: |
| `database-before.dump` | 停写后的 PostgreSQL 备份，已通过 `pg_restore --list` | 1,257,777 |
| `runtime-before.tar.gz` | Web instance 与 `/opt/jcc/season-library` | 105,521,176 |
| `web-before.tar.gz` | 原 Web 已提交代码 | 153,358,913 |
| `db-before.tar.gz` | 原 DB 已提交代码 | 18,490 |
| `config-before.tar.gz` | 环境、systemd unit/drop-in、Nginx 配置 | 3,393 |

`release.json` 保存提交号、备份 SHA-256、业务表指纹、切换时间、完整性和最终服务状态；`https-smoke.json` 保存 35 项 HTTPS 验证结果。敏感配置及备份均留在服务器受限目录。

本次没有修改数据库 schema，代码回滚可退回上述 Web `bd82fdd`，修复所有权/静态权限后重启并检查服务；这个版本仍包含已生效的阵容封禁保护。只有数据库或运行文件确需恢复时，才按停写后的新恢复点协调还原，避免覆盖上线后的业务写入。这些备份位于同机。

本上线记录随后提交至本地 main，GitHub 推送仍由用户负责。线上功能代码保持已确认的 `2c82ed3`。
