# 服务器更新手册（生产运维 Runbook）

> 本手册基于 2026-07-26 实际部署验证过的流程编写。任何步骤与服务器实况不符时，**以服务器实际状态为准**，先查清再动手。

## 一、服务器信息速查

| 项目 | 值 |
|---|---|
| 服务器 | `114.134.186.41`（Debian 12，2 核 / 2G 内存，web 与 PostgreSQL 同机） |
| SSH | root 用户，端口 22（密码/密钥自行保管，**不要写进任何仓库**） |
| Web 代码 | `/opt/jcc/jcc-web-service`（属主 `jcc` 用户） |
| DB 仓库 | `/opt/jcc/jcc-db-service`（属主 root） |
| systemd 服务 | `jcc.service`，以 `jcc` 用户运行 gunicorn，**监听 127.0.0.1:5054** |
| gunicorn 配置 | `deploy/gunicorn.conf.py`（2 worker × gthread 4 线程；端口由 unit 里 `--bind` 指定为 5054） |
| 环境变量 | `/etc/jcc.env`（含 `JCC_DATABASE_URL`、密钥等，所有敏感信息只放这里） |
| nginx 站点 | `/etc/nginx/sites-enabled/jcc.conf`（certbot 托管 TLS；gzip + `/static` 直接托管） |
| 数据库 | 本机 PostgreSQL 15，库名 `jcc` |
| 数据库备份目录 | `/opt/jcc/postgres-backups/`（root 专属） |
| 健康检查 | `curl http://127.0.0.1:5054/api/health` → `{"ok":true}` |
| 旧目录 | `/opt/jcc/jcc_git` 为历史遗留，**不要动也不要用** |

## 二、更新前必读

1. **顺序铁律**：如果本次更新包含数据库迁移（`jcc-db-service/migrations/` 有新文件），**必须先迁移数据库、再更新 web**。
2. **先备份再动手**：数据库备份 30 秒就能做完，没有理由跳过。
3. **确认 GitHub 上是最新的**：两个仓库都要推送。历史教训：曾出现只推了 web、忘推 db-service，导致服务器拉不到迁移文件。
4. 本机连不上 SSH 时先检查自己的代理/VPN（TUN 模式会拦截 SSH，症状是"连接立即被关闭"）——先给服务器 IP 加 DIRECT 规则或暂时退出代理。

## 三、标准更新流程

SSH 登录服务器后按顺序执行：

### 第 1 步：备份数据库

```bash
. /etc/jcc.env
pg_dump "$JCC_DATABASE_URL" -Fc -f /opt/jcc/postgres-backups/jcc-before-$(date +%Y%m%d-%H%M%S).dump
ls -lh /opt/jcc/postgres-backups/ | tail -3   # 确认新文件存在且大小合理
```

### 第 2 步：数据库迁移（仅当有新迁移文件时）

```bash
cd /opt/jcc/jcc-db-service
git pull origin main
. /etc/jcc.env
.venv/bin/python scripts/apply_migrations.py --database-url "$JCC_DATABASE_URL"

# 验证：确认最新迁移已记录
psql "$JCC_DATABASE_URL" -c 'SELECT version, applied_at FROM schema_migrations ORDER BY version DESC LIMIT 3;'
```

### 第 3 步：更新 Web 代码

```bash
cd /opt/jcc/jcc-web-service
git -c safe.directory=/opt/jcc/jcc-web-service pull origin main
chown -R jcc:jcc /opt/jcc/jcc-web-service        # root 拉取后归还属主
chmod -R a+rX /opt/jcc/jcc-web-service/static    # 严格 umask 下确保 Nginx 可读取静态资源
sudo -u jcc .venv/bin/pip install -r requirements.txt -q
git log --oneline -1                              # 确认到达预期提交
```

> 说明：GitHub 的 SSH 拉取权限配在 root 的密钥上，`jcc` 用户拉不了，所以用 root 拉 + `chown` 归还属主。

### 第 4 步：重启服务

```bash
systemctl restart jcc
sleep 3
systemctl is-active jcc                           # 应输出 active
curl -fsS http://127.0.0.1:5054/api/health        # 应输出 {"ok":true}
journalctl -u jcc --since '2 minutes ago' --no-pager | grep -iE 'error|traceback' || echo '日志无错误'
```

### 第 5 步：线上验证

```bash
# 公网健康检查与页面抽查
for p in / /tools/seasons/s17 /patch-notes /api/health; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' https://jcc.np5.top$p) $p"
done

# 静态缓存与 gzip（应看到 immutable 与 encoding=gzip）
curl -sI https://jcc.np5.top/static/styles.css | grep -i cache-control
curl -s -H 'Accept-Encoding: gzip' -o /dev/null \
  -w 'encoding=%header{content-encoding}\n' https://jcc.np5.top/static/styles.css

# 赛季 JSON 会原地更新，必须重新验证，不能继承 /static 的 immutable
curl -sI https://jcc.np5.top/static/season-data/catalog.json | grep -i cache-control
# 预期包含：max-age=0, must-revalidate
```

再用浏览器打开首页、随便点一个赛季资料页和弈子详情页确认无异常。

## 四、配置文件变更时的额外步骤

仓库里的 `deploy/` 是**示例**，不会自动生效。只有当本次更新改了它们时才需要做：

### systemd（`deploy/jcc.service.example` 有变化时）

```bash
cp /etc/systemd/system/jcc.service /etc/systemd/system/jcc.service.bak.$(date +%Y%m%d-%H%M%S)
diff /etc/systemd/system/jcc.service /opt/jcc/jcc-web-service/deploy/jcc.service.example
# 手动合入差异。注意保留生产实际值：User=jcc、EnvironmentFile=/etc/jcc.env、--bind 127.0.0.1:5054
systemctl daemon-reload && systemctl restart jcc
curl -fsS http://127.0.0.1:5054/api/health
```

### nginx（`deploy/nginx.conf.example` 有变化时）

```bash
cp /etc/nginx/sites-enabled/jcc.conf /etc/nginx/jcc.conf.bak.$(date +%Y%m%d-%H%M%S)
# 注意：备份放 /etc/nginx/，千万不要留在 sites-enabled/ 里（会被 nginx 当配置加载）
diff /etc/nginx/sites-enabled/jcc.conf /opt/jcc/jcc-web-service/deploy/nginx.conf.example
# 手动合入差异。certbot 注释 "# managed by Certbot" 的行一律原样保留；
# 生产的 proxy_pass 端口是 5054（示例里是 5000）
nginx -t && systemctl reload nginx
```

## 五、回滚方法

| 出问题的环节 | 回滚操作 |
|---|---|
| Web 代码 | `cd /opt/jcc/jcc-web-service && git reset --hard <上一个正常提交>` → `systemctl restart jcc` |
| systemd 配置 | 用 `/etc/systemd/system/jcc.service.bak.*` 覆盖回去 → `daemon-reload` + `restart` |
| nginx 配置 | 用 `/etc/nginx/jcc.conf.bak.*` 覆盖回去 → `nginx -t && systemctl reload nginx` |
| 数据库迁移（加索引类） | 通常**无需回滚**（索引不影响正确性）；确要删则 `DROP INDEX <名字>;` |
| 数据损坏（极端情况） | `pg_restore -d "$JCC_DATABASE_URL" --clean /opt/jcc/postgres-backups/<备份文件>`（先停 jcc 服务） |

## 六、日常维护（按需手动执行，均不自动运行）

```bash
# 事件表清理（visit/growth/login/copy-action/rate-limits）——先 dry-run 看数量，确认后再加 --yes
cd /opt/jcc/jcc-web-service
sudo -u jcc .venv/bin/python scripts/maintenance/prune_events.py --days 180          # 预览
sudo -u jcc .venv/bin/python scripts/maintenance/prune_events.py --days 180 --yes    # 执行

# 磁盘与内存巡检
df -h / && free -h
du -sh /opt/jcc/postgres-backups/    # 备份多了手动清旧的
```

## 七、已知注意事项

- `/tools/lineup-simulator` 返回 404 不一定是故障：后台"设置"里有 `simulator_enabled` 开关（2026-07-04 起为关闭状态）。
- 赛季资料数据更新不走服务器：在本地维护 `ccmax资料/数据模版` 档案库 → 本地跑 `scripts/season_library/import_from_archive.py` → 提交推送 → 服务器按本手册标准流程 pull 即可（见 `docs/season-library.md`）。
- 2G 内存的机器**不要**把 gunicorn worker 数往上调，需要更高并发就加 threads。
- 修改 `/etc/jcc.env` 后需要 `systemctl restart jcc` 才生效。
- 服务器密码若曾在聊天/工单中传输过，事后应更换；长期建议改用 SSH 密钥登录。
