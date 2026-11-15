# 卡组投稿数据层接入

DB migrations `0029_orange_deck_submissions` / `0030_orange_deck_analytics` 已接入 Web，
并有对应 SQLite 镜像。字段定义以 DB migrations 为准，业务语义见
[DB 数据契约](https://github.com/LiYineng798/jcc-db-service/blob/codex/deck-submissions-data/docs/deck-submission-data.md)。
不要重新创建同名表或修改已应用迁移；结构调整需新增编号并同步两种数据库。

## 实现入口

- `deck_submission_service.py` / `deck_submissions.py`：双码投稿、私有进度、管理员认领/转派/补充/发布。
  提交者仅可修改待处理/待补充投稿；保存与发布使用投稿版本和草稿版本检查。
- `orange_deck_service.py`：供稿署名与权限分离、当前资料校验、近期互动衰减排行与冷启动补位。
  所有者仍为 `user_id`；投稿卡组公开供稿人取 `provided_by_user_id`，`published_by_user_id` 保留首次发布管理员。
- `insert_deck` / `apply_deck_update` 不提交事务；发布一次性写入卡组、投稿、版本事件、通知和审计。
  补交代码同步到已有关联草稿并推进草稿版本，保留管理员完善的卡片、站位和说明。
  发布代码与当前投稿不同时需显式确认，防止旧草稿无提示覆盖补交内容。
- `orange_deck_submission_events.payload_json` 保存必要快照；投稿人及管理员可在各自私有详情查看历史内容。
  API 只返回允许展示的字段，不把任意事件载荷透传给浏览器。
- 统一通知支持 `deck_submission` 分类、版本化已读与私有详情跳转；自身保存不新增通知。
- `deck_analytics_service.py` / `copy_action_service.py`：活动、双码复制、每日去重访问。
  首个事件同事务写入 `deck_analytics_started_at`，不补造旧行为数据。
- `deck_report_service.py` / `daily_report_service.py`：概览及日报 payload v2 的 `deck_*` 指标。
  动作数、五分钟有效复制、独立人数分别统计；缺失历史显示“未采集”。
  部分时段采集的行为指标不与全天直接计算差值，投稿和已有有效复制记录不受此限制。
- 后台卡组库展示首次发布人、复核版本和时间，并提供当前资料复核入口。
  内容修改会清除当前复核标记，资料版本变化显示待重新复核；历史复核事件保留。

页面和规则见 [卡组库](orange-decks.md)，统计口径见 [日报](daily-report.md)。

## 迁移与验证边界

`orange_deck_data_schema.py` 负责 SQLite 新库 schema 和旧库原子升级；通知表升级保留关联、
已读状态和自增序列。`db.py` 在 SQLite bootstrap 写入前调用升级，PostgreSQL 只检查所需表/列。

部署时先应用 DB `0029/0030`，再部署 Web，不能让生产启动代替迁移。
SQLite、路由和浏览器测试不等于真实 PostgreSQL 验收；生产部署/恢复需在隔离 PostgreSQL 验证。
Web 测试导入时会初始化默认 instance，应使用不含真实运行数据的干净副本。
