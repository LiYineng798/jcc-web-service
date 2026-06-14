# 数据库迁移版本化计划

## 目标

将当前 `db.py` 中的自动建表和补字段迁移，逐步升级为可追踪、可回放、可审计的版本化迁移机制。

第一阶段只做设计，不改变现有线上迁移行为。

## 当前状态

当前迁移入口：

```text
migrate.py
```

核心实现：

```text
db.py -> init_db()
db.py -> migrate_schema()
db.py -> ensure_indexes()
```

当前优点：

- 简单直接。
- 适合 SQLite 小型应用。
- 本地和服务器都能直接运行 `python migrate.py`。

当前不足：

- 不容易看出每次数据库结构变化发生在什么时候。
- 不容易回放完整迁移历史。
- 不容易区分初始化 schema 和后续 schema 变更。
- 随着功能增加，`db.py` 会继续变大。

## 目标表

后续新增迁移版本记录表：

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| `version` | 迁移文件版本，例如 `001_initial` |
| `applied_at` | 执行时间，ISO 字符串 |

## 目标目录

```text
migrations/
├─ 001_initial.sql
├─ 002_add_reports.sql
├─ 003_add_history.sql
├─ 004_add_growth_events.sql
├─ 005_add_live_comp_stats.sql
└─ 006_add_visibility_fields.sql
```

文件命名规则：

```text
三位数字_简短英文说明.sql
```

示例：

```text
007_add_user_daily_stats.sql
008_add_lineup_review_status.sql
```

## 执行流程

1. 打开 SQLite 连接。
2. 确保 `schema_migrations` 表存在。
3. 读取已执行的迁移版本。
4. 扫描 `migrations/*.sql`。
5. 按文件名顺序执行未执行的迁移。
6. 每执行成功一个文件，写入 `schema_migrations`。
7. 任一迁移失败，停止执行并返回错误。
8. 部署脚本停止后续重启流程。

## 上线策略

### 阶段 1：只引入版本表

- 新增 `schema_migrations` 表。
- 保留当前 `migrate_schema()`。
- 不改变当前业务表结构。
- 运行测试确认无影响。

### 阶段 2：建立 baseline

- 将当前线上 schema 记录为 baseline。
- 写入版本：`000_baseline_current_schema`。
- 仍保留现有兼容迁移逻辑。

### 阶段 3：新增迁移走 SQL 文件

- 后续新字段、新表、新索引通过 `migrations/*.sql` 实现。
- `db.py` 只负责连接、执行迁移和基础 bootstrap。

### 阶段 4：逐步瘦身 `db.py`

- 将 schema 常量移出 `db.py`。
- 将迁移执行逻辑移到 `db/migrations.py`。
- 将连接逻辑移到 `db/connection.py`。

## 验收标准

- `python migrate.py` 可重复执行。
- 已执行迁移不会重复执行。
- 新库可以从零初始化。
- 老库可以平滑升级。
- 迁移失败时不会继续重启服务。
- 测试覆盖新库初始化和老库升级场景。

## 风险控制

- 第一次上线前必须备份 `instance/lineups.sqlite3`。
- 第一轮只加迁移版本表，不改业务字段。
- 所有迁移 SQL 必须能重复检查状态或由版本表防重复。
- 不在同一次提交里同时改大量业务逻辑和数据库结构。
