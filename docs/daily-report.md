# 统计与每日报告

`visits.py`、`auth_activity.py`、`copy_action_service.py` 记录行为；
`daily_report_service.py` 汇总到 `daily_admin_reports`，后台 `static/admin/daily-reports.js` 展示。

## 口径

- UV/PV 排除管理员与机器人 UA；访客身份与客户端 IP 不同，NAT 下一个 IP 可对应多人。
- 登录用户活跃按账号合并页面访问与成功密码登录；密码登录次数仍单独统计，不为 Cookie 恢复虚构登录事件。
- 成功复制取 `copy_action_events.success=1`，包含普通和实时阵容；五分钟去重后的公开计分是另一口径。
- 回访窗口取报告日之前的 3/7 天；差值比较最近一份更早报告，不假定每天已有快照。
- 报告是生成时的快照。事件清理后强制重算旧日期可能不完整。

## 生成与读取

每个 Web 进程的日报守护线程每 15 分钟检查昨日缺失报告，按日期唯一键幂等写入；
TESTING 或 Flask 配置 `DAILY_REPORT_WORKER_ENABLED=false` 关闭它。后者不是自动读取的环境变量。

`payload_json` 保存汇总、小时分布、页面排行、复制码/赛季排行、访客 IP 与变化量；
头部统计列便于列表读取。字段以 `build_daily_report_payload()` 为准。
访客 IP、复制细节和日报接口均只对管理员开放。

`GET /api/admin/daily-reports` 列日期；`GET /api/admin/daily-reports/<date>` 取详情；
`POST /api/admin/daily-reports/<date>/generate` 需 CSRF，强制生成并记审计。

```powershell
python scripts/maintenance/generate_daily_report.py --date 2026-09-01
# 只有需要覆盖现有快照时才加 --force
python -m pytest -q tests/test_daily_report.py
```

脚本需要与 Web 一致的数据库环境；无参数时生成昨日。后台线程属于 Web，
与独立的赛季 ZIP worker 无关。表结构对应 DB migration 0007。
