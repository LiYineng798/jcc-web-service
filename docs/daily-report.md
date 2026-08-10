# 每日报告（Daily Report）

后台「数据与系统 → 每日报告」为管理员提供每日运营快照：每天凌晨自动生成
昨日的报告，包含访问量、复制行为、页面热度和热门阵容码排行，满足"数据党"
对站点流量的好奇心。

## 数据流

```text
visit_events / copy_action_events / users / login_events /
lineups / guestbook_messages / reports / likes / favorites
        │  daily_report_service.build_daily_report_payload()
        ▼
daily_admin_reports（report_date 主键，payload_json 存全量报告）
        │  GET /api/admin/daily-reports/<date>
        ▼
后台「每日报告」工作台（统计卡片 + 24 小时热力图 + 复制排行）
```

## 自动生成

- 每个 Flask 进程启动一个 `daily_report_worker` 守护线程，每 15 分钟检查一次
  **昨天**的报告是否缺失，缺失即生成（凌晨 00:00 后约 15 分钟内完成）。
- 多进程（gunicorn 多 worker）并发安全：写入使用
  `INSERT OR IGNORE` / `ON CONFLICT DO NOTHING`，同一 `report_date` 只会有一行。
- 测试环境（`TESTING`）或 `DAILY_REPORT_WORKER_ENABLED=false` 时不启动线程。
- 生产若希望脱离 Web 进程独立调度，可用 cron / systemd timer 执行：

  ```bash
  cd /opt/jcc/jcc-web-service
  .venv/bin/python scripts/maintenance/generate_daily_report.py
  ```

  该脚本幂等：报告已存在时不覆盖，加 `--force` 才重新生成。

## 报告内容

`payload_json` 结构：

| 字段 | 说明 |
|---|---|
| `summary` | UV、PV、新/老访客、新增注册、成功登录、复制（普通+实时）、新阵容、留言、举报、点赞、收藏 |
| `deltas` | 与最近一期更早报告的各指标差值（无更早报告时为 `null`） |
| `previous_date` | 参与差值对比的上期报告日期 |
| `hourly` | 24 小时数组：`uv` / `visits` / `copies`，供热力图使用 |
| `peak_visit_hour` / `peak_copy_hour` | 访问/复制高峰时段 |
| `top_pages` | 热门页面（次数、人数） |
| `top_copied` | 复制排行（普通阵容 + 实时阵容，含标题、赛季、次数、人数、阵容码） |

口径说明：

- 访问统计排除管理员与机器人 UA（与 `visits.py` 一致）。
- 复制统计以 `copy_action_events` 中 `success = 1` 的行为为准（与后台「今日复制排行」同源）。
- 小时提取只出现在 `SELECT/GROUP BY`（`substr(created_at, 12, 2)`），`WHERE`
  过滤保持半开区间 `created_at >= ? AND created_at < ?`，不破坏索引可用性。

## API

- `GET /api/admin/daily-reports?page_size=N`：报告日期列表（新→旧，含头部汇总列）。
- `GET /api/admin/daily-reports/<date>`：单日报告详情；不存在返回 404。
- `POST /api/admin/daily-reports/<date>/generate`：强制重新生成并返回报告；
  需要 CSRF，并写入 `audit_logs`（action=`generate_daily_report`）。

所有接口均要求管理员权限。

## 数据库对齐

- SQLite：表与索引定义在 `db_schema.py` 的 `SCHEMA` 中，老库由
  `db_migrations.migrate_daily_admin_reports_table()` 补齐。
- PostgreSQL：`jcc-db-service/migrations/0007_daily_reports.sql`（先于 Web 代码部署）。

## 手动验证

```powershell
python -m pytest -q tests/test_daily_report.py
python scripts/maintenance/generate_daily_report.py
python scripts/maintenance/generate_daily_report.py --date 2026-08-08
python scripts/maintenance/generate_daily_report.py --date 2026-08-08 --force
```
