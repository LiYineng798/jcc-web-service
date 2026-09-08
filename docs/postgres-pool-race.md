# PostgreSQL 连接池初始化竞态修复

## 问题与原因

生产日志曾出现 `can't return connection to pool 'jcc-web', it comes from pool 'jcc-web'`。堆栈位于日报线程退出 Flask app context 时的 `db.close_db()`，不代表日报计算或写入一定失败。

`create_app()` 会依次启动日报和实时阵容上传后台线程，两者可并发执行首次数据库访问。原来的 `_postgres_pool()` 没有同步机制，多个线程可能同时创建不同的连接池并覆盖同一个全局引用。池名均为 `jcc-web`，但 Psycopg 按对象身份检查连接归属。旧代码只保存“来自连接池”的布尔标记，归还时读取全局池，因而可能把 A 池连接归还到 B 池。

该问题可在服务启动、Gunicorn worker 轮换后的冷启动时触发，不局限于日报业务。

## 修复范围

- `db.py` 使用进程内线程锁保护池的首次创建、替换及池/URL 的发布；连接借用、SQL 执行和归还不持有这把锁。
- `get_db()` 在成功借用后将实际所属池保存到 Flask `g.db_pool`。`close_db()` 从当前上下文取出并使用该池，即便全局池已经改变或清空也不会归还到其他池。
- 创建替代池的构造函数抛错时保留原池；构造成功后才替换并关闭旧池。这不等同于验证数据库连通性：Psycopg `open=True` 异步建立连接，连接超时仍按原有方式上报。
- 保留每个进程 `min_size=1`、`max_size=4`、10 秒借用超时、显式业务 commit/rollback、SQLite 与缺少池依赖时的直接连接路径。
- 没有修改日报计算、任务调度或数据库 schema，也没有吞掉真实 SQL/任务异常。

现有生产模式是 Gunicorn worker 内导入应用。本补丁不新增跨进程共享池或预加载支持；部署时继续保持现有 worker 启动方式。

## 验证

`tests/test_db_pool_lifecycle.py` 使用未设置 `TESTING` 的最小 Flask app，确实经过生产池路径。Psycopg 连接池保持 `open=False`，连接使用离线替身，归属判定复用 Psycopg 的真实检查，因此测试不会连接或写入数据库。

覆盖场景：8 个线程冷启动只创建一个池、所有借出连接归还、上下文重复取连接、全局池在借用期间被替换或清空、业务异常退出、重复 teardown、替代池构造失败、首次构造失败后重试、借用超时、缺少连接池依赖时直接连接与关闭。

新增并发和归属测试在修复前失败，复现同名不同池的异常；替代池构造失败测试也确认了旧池会被提前关闭的问题。

```powershell
python -m pytest -q tests/test_db_pool_lifecycle.py tests/test_db_connection_modes.py
python -m pytest -q
```

本次本地全套验证：`562 passed`，包含新增的 10 项池生命周期用例。

这组自动化验证不覆盖真实 PostgreSQL 网络、事务和 Gunicorn 进程生命周期。上线前应在独立 PostgreSQL 测试环境检查并发请求及后台线程、事务提交/回滚；部署后检查健康接口、日报记录和 worker 轮换期间的日志。

## 部署

仅需更新 Web 仓库，无数据库迁移、新增依赖或环境变量。按 `server-update-guide.md` 备份后部署并重启，使各 worker 使用修复后的池管理。`rolling back returned connection` 属于另一个事务清理日志，本次不通过全局自动提交或屏蔽日志改变其行为。
