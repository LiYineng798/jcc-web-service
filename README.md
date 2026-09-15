# 金铲铲阵容库 · Web

Flask/Jinja 网站与 JSON API：普通阵容分享、实时榜单、账号与审核后台，以及赛季资料库和阵容模拟器。
本地默认 SQLite；生产使用 PostgreSQL。数据库迁移与运维工具在独立的 [DB 仓库](../jcc-db-service/README.md)。

主要页面使用原生 JS/CSS；个人中心、审计日志和赛季版本上传使用三个 React 工作区。
实时榜单 JSON 和赛季包仍存放在 Web 主机文件系统，数据库不是全部运行状态。

## 本地启动

在本仓库运行（PowerShell）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:JCC_SECRET_KEY='local-development-only'
$env:JCC_ADMIN_USERNAME='admin'
$env:JCC_ADMIN_PASSWORD='LocalDev1234'
python run_server.py
```

访问 <http://127.0.0.1:5000>。启动会创建/升级本地 SQLite；通常不必另跑 `migrate.py`。
默认数据库为 `instance/lineups.sqlite3`。配置参考 [.env.example](.env.example)；
直接运行 Python **不会自动加载 .env**，请通过进程环境设置。

需要处理赛季 ZIP 时，在相同环境的第二个终端运行：

```powershell
python season_package_worker.py
```

已有构建产物可直接运行网站。修改 React 源码时才需要：

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
```

## 验证

```powershell
python -m pytest -q
python scripts/maintenance/check_deploy_safety.py
git diff --check
```

测试会导入应用并初始化默认 instance；已有运行数据时先使用干净副本。
浏览器测试、构建边界和已知验证限制见 [开发与验证](docs/development.md)。

## 按任务阅读

| 任务 | 文档 |
| --- | --- |
| 找到代码入口、理解存储/任务/接口边界 | [架构](docs/architecture.md) |
| 开发、测试、预览 | [开发与验证](docs/development.md)、[React 工程](frontend/README.md) |
| 页面交互与兼容约束 | [前端维护](docs/ui.md) |
| 部署、备份、恢复、缓存配置 | [运维](docs/operations.md) |
| 查找已有生产恢复点 | [部署记录](docs/deployment-history.md) |
| 新赛季、补丁、数据修订 | [赛季维护](docs/season-maintenance-playbook.md) |
| 资料结构与模拟器规则 | [赛季资料](docs/season-library.md)、[ZIP 协议](docs/season-package-format.md) |
| 实时榜单上传与图片 | [实时阵容](docs/live-comps.md) |
| 封禁、修改重审、站内通知 | [阵容审核](docs/lineup-moderation.md) |
| 运营指标与日报 | [统计口径](docs/daily-report.md) |
| 编辑官方更新公告 | [公告格式](docs/patch-notes.md) |

开发约束见 [AGENTS.md](AGENTS.md)。历史实施过程保存在 Git，不再维护重复计划和逐项接口目录。
