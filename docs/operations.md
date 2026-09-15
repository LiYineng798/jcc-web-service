# Web 运维

此处是 Web 部署/恢复的唯一流程入口；DB 命令详见 [DB 运维](../../jcc-db-service/docs/operations.md)。
赛季资料发布走 [后台 ZIP 流程](season-maintenance-playbook.md)，无需每次代码部署。

## 已记录的生产拓扑

以下来自仓库截至 2026-09-15 的部署记录，**本文件不表示已经检查当前服务器**。
操作前核对 systemctl cat、监听端口、环境、Git 提交和任务队列，以实况为准。

| 项目 | 已记录配置 |
| --- | --- |
| 主机/站点 | 114.134.186.41 / https://jcc.np5.top |
| Web / DB 仓库 | /opt/jcc/jcc-web-service / /opt/jcc/jcc-db-service |
| Web 服务 | jcc.service，jcc:jcc，Gunicorn 127.0.0.1:5054 |
| PostgreSQL | 同机 PostgreSQL 15，127.0.0.1:5432/jcc，不公开数据库端口 |
| 共享环境 | /etc/jcc.env |
| 赛季任务 | jcc-season-worker.service，独立进程，与 Web 共用 DB/目录 |
| 私有赛季包 | JCC_SEASON_PACKAGE_ROOT=/opt/jcc/season-library |
| Nginx | /etc/nginx/sites-enabled/jcc.conf，Certbot TLS |
| 恢复点索引 | [部署记录](deployment-history.md) |

本地 run_server.py 使用 5000。部署 unit 示例明确覆盖 Gunicorn 的通用默认端口/超时为 5054/120 秒；
已有主机可能用 drop-in，不能直接覆盖 live unit、TLS 配置或环境。
旧 jcc_git 目录及旧分离主机地址不作为更新目标。

## 环境与首次配置

[.env.example](../.env.example) 列出进程环境。生产必设稳定随机 JCC_SECRET_KEY、真实数据库 URL，
按需设上传 token、Resend 密钥和 HTTPS Secure Cookie。环境文件限制读取权限，不入 Git。
管理员环境值是 SQLite 初次创建默认账号的输入，不会自动修改已有账号；PostgreSQL 不由 Web 自动建管理员。

先应用 DB 全部迁移，再安装 Web requirements。建立 jcc 可写的 instance 和私有包目录，
按 [Web unit](../deploy/jcc.service.example)、[worker unit](../deploy/jcc-season-worker.service.example)
配置进程；生产无 Node，React 产物在开发时构建提交。
worker 不放进 Gunicorn，ReadWritePaths 与真实包目录一致。

Nginx 按 [示例](../deploy/nginx.conf.example) 合入，保留现有证书与主机设置：

- 一般 /static/ 直接托管；模板资源用 static_v()。Nginx 必须可读静态文件。
- /static/season-data/ 和 /season-assets/ 代理 Flask，关闭代理缓存；不能用公共 alias 绕过赛季/候选包权限。
- 可变赛季 JSON 使用 max-age=0, must-revalidate；受保护资源沿用应用响应，不追加 immutable。
- /api/admin/season-packages 允许 257m multipart 请求体，上传/代理超时 120 秒。
- Session/API/账号/后台不做公共页面缓存；代理保留 Host、客户端 IP 和协议头。

配置修改先 nginx -t；systemd 修改后 daemon-reload。环境/共享 Python/依赖更新同时重启 Web 与 worker。

## 更新顺序

1. 本地完成测试/构建，确认两个仓库的候选提交在远端可取得。服务器 working tree 干净才快进，
   不覆盖临时修改；核对实际需要的新 migration。
2. 等待或处理后台上传/发布任务，停止管理写入；一致备份前停止 jcc 与 jcc-season-worker。
3. 生成 PostgreSQL dump，并归档 Web instance、私有包目录、旧代码/静态基准、环境及服务/Nginx 配置。
   文件与 DB 应属于同一停写窗口；检查 dump 目录、文件大小和校验和，保留异机副本。
4. 先更新 DB 并运行迁移/完整性检查，再更新 Web。用 git pull --ff-only，核对目标提交；
   按需安装依赖，恢复 Web 属主和 Nginx 静态读取权限，不替换运行目录。
5. 合入本次需要的配置差异，启动两个服务并验收。没有完成恢复验证前保留原备份。

数据库备份示例（停写窗口，先创建权限受限的目标目录）：

```bash
set -a
. /etc/jcc.env
set +a
pg_dump "$JCC_DATABASE_URL" -Fc -f /opt/jcc/postgres-backups/jcc-before.dump
pg_restore --list /opt/jcc/postgres-backups/jcc-before.dump
```

实际文件名使用独立时间戳，避免覆盖已有恢复点。
两仓库的 deploy/update.sh 只是“快进、依赖、迁移/重启、检查”辅助，
**不负责一致备份、停写、任务排空或文件恢复，不能代替上述流程**。

## 验收与排查

```bash
systemctl is-active jcc jcc-season-worker postgresql nginx
curl -fsS http://127.0.0.1:5054/api/health
curl -fsS https://jcc.np5.top/api/health
journalctl -u jcc -u jcc-season-worker --since '5 minutes ago' --no-pager
```

抽查首页、登录、普通/实时阵容、账号、后台、资料详情、模拟器和 JS/CSS。
验证访客无法读候选/隐藏资源，公开 catalog 与实际 release 一致，JSON 缓存重验证有效；
变更涉及的写操作在隔离环境演练，不把生产业务当测试夹具。

ZIP 卡住：检查 worker 心跳/日志、目录权限、空间、DB/包目录是否与 Web 一致。
/tools/lineup-simulator 返回 404 也可能是后台 simulator_enabled 关闭。
PostgreSQL schema 缺失必须先迁移；不要靠改 SQLite fallback 掩盖连接问题。

## 恢复与保留

- 仅代码回退：选与当前数据兼容的已验证提交，恢复权限后重启 Web/worker。
  已有封禁数据时不能退到缺少审核保护的旧 Web。
- 数据/文件恢复：停止两个服务及写入，先保存当前恢复点，再协调还原 DB、instance、包目录、
  静态基准、可见性配置及兼容代码，完整性检查通过后启动。
- 只回滚赛季资料：用后台选择已发布快照，不恢复整个用户数据库；发布版本与展示状态分离。
- 不删数据库仍引用的包/图片/回滚目标。当前没有带引用检查的自动清理工具。
- SQLite 备份用 sqlite3 backup API 或停服检查点后的完整备份；
  现有 backup_database.py 是简单 copy，WAL 在线时不足以保证一致性。

事件清理脚本 scripts/maintenance/prune_events.py 默认预览，加 --yes 才写入。
运行维护脚本前显式加载与 Web 相同的环境；清理前保留日报/恢复所需数据。
