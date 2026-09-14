# 2026-09-14 阵容封禁、修改审核与主页通知上线记录

站点：`https://jcc.np5.top`；服务器：`114.134.186.41`。用户确认验收、合并并自行推送 GitHub 后执行本次更新。

## 版本与切换

| 仓库 | 更新前 | 部署版本（已核对 GitHub main） |
| --- | --- | --- |
| Web | `004fee0582acc21298a84b79fcd5adfce833a73c` | `bd82fdd97136020a0226364aff84f93a8c4771b4` |
| DB | `92cac96f2a6f2435dc4de6df94e6e670d483c817` | `52cc22cf900b1d1207fb80e9cb326c95f41dd6bd` |

两个服务器仓库更新前后均为干净的 main。仅快进到已确认的提交，未覆盖服务器改动。依赖清单没有变化，两个虚拟环境的 `pip check` 通过，未升级依赖。

2026-09-14 15:07:27（北京时间）停止 `jcc` 和 `jcc-season-worker`，一致性备份完成后先应用 DB `0016_lineup_moderation`（15:07:33），再更新 Web，归还 `jcc:jcc` 文件所有权和静态资源读取权限，然后启动两个服务。停服至健康恢复共 **7.72 秒**。Nginx、环境变量和 worker 配置没有变更。

## 验证

- 更新前旧数据库完整性检查通过，赛季上传队列无 queued/running 任务。
- 将 GitHub 候选代码解包到独立目录，在同机临时 PostgreSQL 数据库执行 0001–0016 全部迁移；使用虚构用户和阵容验证真实 API 的封禁、不可删除、访问隔离、通知已读、修改提交、退回、重提、通过、过期版本冲突与隐藏状态恢复。完整性检查全部为零。验证数据库已删除，生产库未创建测试用户或测试阵容。
- 正式迁移后完整性检查全部为零。停止写入期间，users、lineups、likes、favorites、reports 和 season_release_packages 的行数及内容指纹在切换前后完全一致。
- **19 项生产 HTTPS 检查通过**：首页、普通阵容 API、新通知 JS/CSS、后台脚本、S18 资料页、更新公告、模拟器、站点配置、个人中心及管理页；通知 API 对访客返回 401，对作者返回 200 且 private/no-store；普通用户访问审核汇总返回 403，管理员汇总与筛选列表正常。
- 受保护接口通过仅驻留进程内存的临时维护会话检查；未修改用户密码，未保存会话凭据，未通过生产封禁操作验证功能。
- 15:11:12 最终确认 Web、赛季 worker、Nginx、PostgreSQL 均 active；Web/worker `NRestarts=0`，切换以来日志无 error、traceback 或 critical。另从本地网络请求公网健康检查返回 200、`{"ok":true}`。

## 备份与恢复

备份目录：`/opt/jcc/deploy-backups/lineup-moderation-20260914-150418/`，root 专属权限。

- `database-before.dump`：停止 Web/worker 后生成的 PostgreSQL 一致性备份，1,246,409 字节，已通过 `pg_restore --list`。
- `runtime-before.tar.gz`：Web instance 和 `/opt/jcc/season-library`，105,433,545 字节。
- `web-before.tar.gz`、`db-before.tar.gz`：更新前的已提交代码。
- `config-before.tar.gz`：环境文件、systemd unit/drop-in 与 Nginx 站点配置；包含敏感配置，只保留在服务器受限备份目录。
- `release.json`：前后版本、备份大小/SHA-256、业务数据指纹、时间、19 项 HTTPS 验证及临时库清理结果；另有 `postgres-smoke-ok.json` 和 `https-smoke.json`。

这些是同机备份。恢复时先停止 Web 和 worker，并核对是否已有真实封禁、修改提交或审核事件；不能只回滚到缺少封禁保护的旧 Web，让旧编辑入口绕过已生效的限制。必要时按停写后的最新备份恢复匹配的代码、数据库及运行文件，验证后再启动服务。常规更新流程见 [服务器更新手册](server-update-guide.md)。

本记录及状态说明在部署后保存于本地仓库；GitHub 推送仍由用户负责。线上功能代码保持表中已确认的 GitHub 提交。
