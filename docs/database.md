# 数据库说明

## 数据库位置

默认数据库文件：

```text
instance/lineups.sqlite3
```

配置来源：

```text
config.py -> DATABASE
```

本地和生产环境都不应把数据库提交到 Git。

## 运行数据

| 路径 | 说明 |
|---|---|
| `instance/lineups.sqlite3` | 主 SQLite 数据库 |
| `instance/live-comps.json` | 当前实时阵容排行数据 |
| `instance/live-comps.previous.json` | 上一次实时阵容排行备份 |
| `instance/live-comps-assets/` | 实时阵容图片本地缓存 |

## 主要表

| 表名 | 作用 |
|---|---|
| `users` | 用户和管理员账号 |
| `lineups` | 用户上传阵容 |
| `likes` | 点赞记录 |
| `copy_events` | 普通阵容复制记录 |
| `favorites` | 收藏记录 |
| `reports` | 举报记录 |
| `recent_lineup_views` | 最近浏览 |
| `recent_lineup_copies` | 最近复制 |
| `login_events` | 登录事件 |
| `visit_events` | 每日 UV |
| `audit_logs` | 管理员审计日志 |
| `rate_limits` | 接口限流状态 |
| `growth_events` | 增长漏斗事件 |
| `live_comp_global_stats` | 实时阵容累计复制 |
| `live_comp_global_daily_stats` | 实时阵容当日复制 |

## 迁移

初始化或迁移数据库：

```powershell
python migrate.py
```

`migrate.py` 会创建 Flask app，并在应用上下文中调用 `db.init_db()`。

当前迁移逻辑位于：

```text
db.py
```

主要职责：

- 创建缺失的表。
- 初始化默认管理员。
- 补齐历史字段。
- 创建索引。
- 开启 SQLite WAL。

## 备份

生产环境更新前必须备份；标准更新脚本会自动执行以下维护脚本：

```bash
python scripts/maintenance/backup_database.py --database instance/lineups.sqlite3 --backup-dir /opt/jcc/backups
```

也可以手工备份：

```bash
mkdir -p /opt/jcc/backups
cp /opt/jcc/jcc_git/instance/lineups.sqlite3 /opt/jcc/backups/lineups.$(date +%Y%m%d-%H%M%S).sqlite3
```

建议定期备份实时阵容图片：

```bash
tar -czf /opt/jcc/backups/live-comps-assets.$(date +%Y%m%d-%H%M%S).tar.gz /opt/jcc/jcc_git/instance/live-comps-assets
```

## 注意事项

- 不要把本地测试数据库上传到服务器。
- 不要在部署时覆盖服务器 `instance/`。
- 修改 `db.py`、`migrate.py` 后必须运行相关测试。
- 如果未来数据库变更变多，应引入 `schema_migrations` 版本表。

