# 部署说明

## 服务器信息

当前生产环境约定：

| 项 | 值 |
|---|---|
| 业务域名 | `jcc.np5.top` |
| 源站 IP | `103.23.148.135` |
| SSH 端口 | `22` |
| 项目目录 | `/opt/jcc/jcc_git` |
| 服务名 | `jcc` |
| 更新脚本 | `/usr/local/bin/jcc-update` |
| 数据库路径 | `/opt/jcc/jcc_git/instance/lineups.sqlite3` |
| 备份目录 | `/opt/jcc/backups` |

敏感信息不要写入本文档，包括服务器密码、证书私钥、上传令牌、管理员密码。

## 首次部署

```bash
mkdir -p /opt/jcc
cd /opt/jcc
git clone <your-github-repo-url> jcc_git
cd /opt/jcc/jcc_git
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
python migrate.py
```

创建 systemd 服务时，可以参考：

```text
deploy/jcc.service.example
```

创建 Nginx 站点时，可以参考：

```text
deploy/nginx.conf.example
```

## 日常更新

推荐使用服务器固定更新脚本：

```bash
/usr/local/bin/jcc-update
```

仓库内模板为 `deploy/update.sh`。服务器上的 `/usr/local/bin/jcc-update` 应保持与该模板一致，或只修改路径变量。

标准流程：

1. 自动备份数据库。
2. 拉取 GitHub 最新代码。
3. 安装/更新依赖。
4. 执行数据库迁移。
5. 重启服务。
6. 调用健康检查接口。

## 数据库备份

部署更新脚本会先调用 `scripts/maintenance/backup_database.py` 自动备份线上数据库，再拉取 GitHub 最新代码。

手工备份命令：

```bash
mkdir -p /opt/jcc/backups
cp /opt/jcc/jcc_git/instance/lineups.sqlite3 /opt/jcc/backups/lineups.$(date +%Y%m%d-%H%M%S).sqlite3
```

如果要同时备份实时阵容图片缓存：

```bash
tar -czf /opt/jcc/backups/live-comps-assets.$(date +%Y%m%d-%H%M%S).tar.gz /opt/jcc/jcc_git/instance/live-comps-assets
```

## 回滚

代码回滚：

```bash
cd /opt/jcc/jcc_git
git log --oneline -5
git reset --hard <previous_commit>
source .venv/bin/activate
python migrate.py
systemctl restart jcc
curl -fsS https://jcc.np5.top/api/health
```

数据库回滚只有在数据库损坏或错误迁移时使用：

```bash
systemctl stop jcc
cp /opt/jcc/backups/lineups.YYYYMMDD-HHMMSS.sqlite3 /opt/jcc/jcc_git/instance/lineups.sqlite3
systemctl start jcc
curl -fsS https://jcc.np5.top/api/health
```

数据库回滚会丢失备份时间点之后的数据。

## 健康检查

```bash
curl -fsS https://jcc.np5.top/api/health
systemctl status jcc
journalctl -u jcc -f
```

健康检查正常时应返回：

```json
{"ok": true}
```

