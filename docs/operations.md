# Web 运维

本文只提供可公开的部署契约，不记录真实主机、账号、环境文件位置或恢复点。
真实配置和验收记录存放在受控的私有运维系统；仓库内临时副本放被忽略的 `private/`，它不是可靠备份。
发布边界见 [仓库安全](repository-security.md)，DB 命令见 [DB 运维](../../jcc-db-service/docs/operations.md)。
赛季资料发布走 [后台 ZIP 流程](season-maintenance-playbook.md)，无需每次代码部署。

## 部署契约与示例

- Web 和独立赛季 worker 使用相同数据库、持久化目录和运行环境。
- PostgreSQL 不开放公网端口；同机使用 loopback，分离部署使用受控网络和访问规则。
- Nginx 终止 TLS，代理到 loopback 上的 Gunicorn。示例端口为 5054，本地开发为 5000。
- `deploy/*.example` 中的 `jcc.example.com`、`/srv/example-jcc`、`/etc/example-jcc.env`、服务名和用户均为示例，不能视作生产现况。
- 操作前核对服务单元、监听端口、环境、Git 提交与任务队列；不要覆盖现有 TLS 配置、drop-in 或环境文件。

## 环境与首次配置

[.env.example](../.env.example) 列出进程环境。生产必设稳定随机 `JCC_SECRET_KEY`、真实数据库 URL、
独立强管理员密码和 HTTPS Secure Cookie；按需设置上传 token、Resend API key **及已验证的 RESEND_FROM_EMAIL**。
默认密钥/账号/密码和示例邮箱只用于开发，不是生产凭据。Python 不会自动加载 `.env`。
环境文件限制读取权限，不入 Git；不要把完整环境或连接串贴到 issue、日志和截图。
管理员环境值仅是 SQLite 初次创建账号的输入，不会修改已有账号；PostgreSQL 不由 Web 自动建管理员。

先应用 DB 全部迁移，再安装 Web requirements。创建服务用户可写的 `instance/` 和私有包目录，
参照 [Web unit](../deploy/jcc.service.example)、[worker unit](../deploy/jcc-season-worker.service.example)
配置进程。React 产物在开发时构建提交，不要求生产安装 Node。
worker 不放进 Gunicorn，`ReadWritePaths` 必须与实际持久化目录一致。

Nginx 按 [示例](../deploy/nginx.conf.example) 合入，保留现有证书与主机设置：

- 一般 `/static/` 直接托管；模板资源用 `static_v()`。Nginx 必须可读静态文件。
- `/static/season-data/` 和 `/season-assets/` 代理 Flask，关闭代理缓存；不能用公共 alias 绕过赛季/候选包权限。
- 可变赛季 JSON 使用 `max-age=0, must-revalidate`；受保护资源沿用应用响应，不追加 immutable。
- `/api/admin/season-packages` 允许 257m multipart 请求体，上传/代理超时 120 秒。
- Session/API/账号/后台不做公共页面缓存；代理保留 Host、客户端 IP 和协议头。

配置修改先 `nginx -t`；systemd 修改后 `daemon-reload`。环境、共享 Python 或依赖更新同时重启 Web 与 worker。

## 更新顺序

1. 本地完成测试和仓库安全检查，确认候选提交已获准发布。服务器工作树干净才快进，不覆盖临时修改；核对新增 migration。
2. 等待或处理后台上传/发布任务，停止管理写入；一致备份前停止 Web 与赛季 worker。
3. 生成 PostgreSQL dump，并归档 Web instance、私有包目录、旧代码/静态基准、环境及服务/Nginx 配置。
   文件与 DB 属于同一停写窗口；校验内容和校验和，保留受控异机副本。
4. 先更新 DB 并迁移/检查完整性，再更新 Web。使用 `git pull --ff-only`，核对目标提交；按需安装依赖、恢复目录权限，不替换运行目录。
5. 合入所需配置差异，启动两个服务并验收。没有完成恢复验证前保留原备份。

数据库备份示例（变量由私有配置提供，停写后运行）：

```bash
: "${JCC_ENV_FILE:?Set the private environment file path}"
: "${BACKUP_DIR:?Set the private backup parent directory}"
set -a
. "$JCC_ENV_FILE"
set +a
umask 077
BACKUP_RUN="$(mktemp -d "$BACKUP_DIR/release-XXXXXXXX")"
pg_dump "$JCC_DATABASE_URL" -Fc -f "$BACKUP_RUN/database.dump"
pg_restore --list "$BACKUP_RUN/database.dump"
```

备份父目录必须已存在且权限受限；每次创建新目录，不覆盖已有恢复点。
完整恢复点还要包含上面列出的文件，并在私有运维系统记录对应提交、校验和与演练结果。

`deploy/update.sh` 在它所属的仓库运行，不再跳转到固定服务器路径。运行前显式设置
`JCC_WEB_SERVICE`、`JCC_SEASON_WORKER_SERVICE`、`JCC_HEALTH_URL`（完整健康检查 URL）。
DB 脚本还要求 `JCC_DB_ENV_FILE`；两个脚本均不负责备份、停写、任务排空或恢复，不能替代上述流程。

## 验收与排查

```bash
: "${JCC_WEB_SERVICE:?Set Web service name}"
: "${JCC_SEASON_WORKER_SERVICE:?Set worker service name}"
: "${JCC_HEALTH_URL:?Set health URL}"
: "${SITE_URL:?Set public site URL}"
systemctl is-active "$JCC_WEB_SERVICE" "$JCC_SEASON_WORKER_SERVICE"
curl -fsS "$JCC_HEALTH_URL"
curl -fsS "${SITE_URL%/}/api/health"
journalctl -u "$JCC_WEB_SERVICE" -u "$JCC_SEASON_WORKER_SERVICE" --since '5 minutes ago' --no-pager
```

另行核验 PostgreSQL 与 Nginx。抽查首页、登录、普通/实时阵容、账号、后台、资料详情、模拟器及 JS/CSS。
验证访客无法读候选/隐藏资源，公开 catalog 与实际 release 一致，JSON 缓存重验证有效；
写操作在隔离环境演练，不把生产业务当测试夹具。日志输出可能包含个人信息，只在受控环境查看。

ZIP 卡住：检查 worker 心跳/日志、目录权限、空间、DB/包目录是否与 Web 一致。
`/tools/lineup-simulator` 返回 404 也可能是后台 `simulator_enabled` 关闭。
PostgreSQL schema 缺失必须先迁移；不要靠改 SQLite fallback 掩盖连接问题。

## 恢复与保留

- 仅代码回退：选与当前数据兼容的已验证提交，恢复权限后重启 Web/worker；已有封禁数据时不能退到缺少审核保护的旧 Web。
- 数据/文件恢复：停止两个服务及写入，先保存当前恢复点，再协调还原 DB、instance、包目录、静态基准、可见性配置及兼容代码，完整性检查通过后启动。
- 只回滚赛季资料：用后台选择已发布快照，不恢复整个用户数据库；发布版本与展示状态分离。
- 不删数据库仍引用的包、图片、回滚目标。当前没有带引用检查的自动清理工具。
- SQLite 备份用 sqlite3 backup API 或停服检查点后的完整备份；现有 `backup_database.py` 是简单 copy，WAL 在线时不足以保证一致性。该工具要求显式传入 `--backup-dir`，不再写入固定服务器路径。
- 本地 `scripts/local/refresh_live_comps.py` 上传要求显式传入 `--url`，不能依赖默认生产站点。

`scripts/maintenance/prune_events.py` 默认预览，加 `--yes` 才写入。
维护脚本显式加载与 Web 相同的环境；清理前保留日报和恢复所需数据。
