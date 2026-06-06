# 项目结构说明

## 唯一主仓库

`jcc_git` 是 JCC 项目的唯一主仓库。后续功能开发、缺陷修复、文档维护、部署脚本维护都应优先在 `jcc_git` 中完成。

历史目录和临时目录只作为参考，不作为长期事实源：

| 目录 | 定位 |
|---|---|
| `jcc_git` | 唯一主仓库 |
| `claude_project` | 历史开发目录或临时参考目录 |
| `webApplication` | 由脚本生成的服务器交付包，不手工维护 |
| `ssl-export` | 临时证书导出目录，不进入 Git |
| `日志` | 人工更新说明归档，运行日志不应进入代码仓库 |

## 目录职责

推荐主仓库结构：

```text
jcc_git/
├─ app.py                    # Flask 入口和页面路由
├─ app_pages.py              # 页面路由注册与测试辅助挂载
├─ admin.py                  # 管理员页面和管理员 API
├─ admin_audit_service.py    # 管理员审计日志分页逻辑
├─ admin_dashboard_service.py# 管理员仪表盘、概览、增长统计逻辑
├─ admin_live_comp_service.py# 管理员实时阵容管理与赛季配置逻辑
├─ admin_lineup_service.py   # 管理员阵容管理逻辑
├─ admin_report_service.py   # 管理员举报处理逻辑
├─ admin_user_service.py     # 管理员用户管理逻辑
├─ auth.py                   # 注册、登录、退出、当前用户 API
├─ lineups.py                # 阵容列表、详情、创建、编辑、互动 API
├─ lineup_account_service.py # 作者页和个人中心读取逻辑
├─ lineup_bridge_service.py  # 最近记录与增长事件桥接逻辑
├─ lineup_interaction_service.py # 点赞、复制、收藏、举报逻辑
├─ lineup_read_service.py    # 阵容列表和详情读取逻辑
├─ lineup_write_service.py   # 阵容创建、编辑、删除、隐藏逻辑
├─ lineups_query.py          # 阵容列表查询和 SQL 组装
├─ lineups_serialization.py  # 阵容输出结构和交互状态组装
├─ route_response.py         # 通用 service 结果转 HTTP 响应助手
├─ live_comps.py             # 实时阵容 API、图片缓存、复制统计
├─ db.py                     # SQLite 连接、建表、迁移、索引
├─ db_migrations.py          # SQLite 迁移与索引补齐逻辑
├─ db_schema.py              # SQLite 基础 schema、字段迁移常量、表辅助函数
├─ static/                   # 前端静态资源
├─ templates/                # Jinja 页面模板
├─ tests/                    # 自动化测试
├─ docs/                     # 项目文档
├─ scripts/local/            # 本地抓取/上传脚本，不进入服务器交付包
├─ scripts/maintenance/      # 导出、检查、备份等维护脚本
├─ deploy/                   # 部署模板和更新脚本
└─ instance/                 # 运行数据，禁止提交
```

## 可以提交的内容

| 类型 | 示例 | 说明 |
|---|---|---|
| 服务端代码 | `app.py`、`app_pages.py`、`admin.py`、`admin_audit_service.py`、`admin_dashboard_service.py`、`admin_live_comp_service.py`、`admin_lineup_service.py`、`admin_report_service.py`、`admin_user_service.py`、`lineups.py`、`lineup_account_service.py`、`lineup_bridge_service.py`、`lineup_interaction_service.py`、`lineup_read_service.py`、`lineup_write_service.py`、`lineups_query.py`、`lineups_serialization.py`、`route_response.py`、`live_comps.py`、`db.py`、`db_migrations.py`、`db_schema.py` | 线上运行需要 |
| 前端资源 | `static/`、`templates/` | 线上运行需要 |
| 测试 | `tests/` | 保障迭代质量 |
| 文档 | `docs/`、`README.md` | 交接和维护 |
| 部署模板 | `deploy/*.example`、`deploy/update.sh` | 不包含真实密码和私钥 |
| 维护脚本 | `scripts/maintenance/` | 可在开发或服务器安全运行，例如部署安全检查、数据库备份、交付包导出 |
| 本地脚本 | `scripts/local/` | 允许进入 Git，但默认不进入服务器交付包 |

## 禁止提交的内容

| 类型 | 示例 | 原因 |
|---|---|---|
| 数据库 | `instance/lineups.sqlite3` | 防止覆盖线上数据 |
| SQLite 运行文件 | `*.sqlite3-wal`、`*.sqlite3-shm` | 运行状态文件 |
| 日志 | `*.log` | 噪音、可能包含隐私信息 |
| 证书和私钥 | `*.pem`、`*.key`、`ssl-export/` | 严重安全风险 |
| 虚拟环境 | `.venv/`、`venv/` | 体积大且机器相关 |
| 缓存 | `__pycache__/`、`.pytest_cache/` | 无需版本控制 |
| 生成交付包 | `webApplication/` | 应由脚本生成，不手工维护 |

## 不进入服务器交付包的内容

以下内容即使存在于开发环境，也不应进入服务器交付包：

```text
scripts/local/
实时获取阵容码/
ssl-export/
.pytest_cache/
__pycache__/
instance/
*.sqlite3
*.db
*.log
*.pem
*.key
```

服务器交付包只应包含网站运行必要内容：后端代码、前端资源、模板、部署文档、必要测试和配置示例。

## 后续演进方向

第一阶段先保持当前 Flask 根目录结构，降低风险。后续当模块继续增多时，可以逐步演进为：

```text
src/jcc/
├─ routes/
├─ services/
├─ repositories/
├─ validators/
├─ db/
├─ templates/
└─ static/
```

演进原则：

- API 路径保持兼容。
- 页面路由保持兼容。
- 数据库迁移保持兼容。
- 每次只拆一个模块。
- 每次拆分前后都运行相关测试。

