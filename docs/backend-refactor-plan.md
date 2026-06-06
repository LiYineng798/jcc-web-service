# 后端模块拆分计划

## 目标

将当前根目录中的大模块逐步拆分为职责更清晰的 routes、services、repositories、validators，同时保持现有 API、页面路由和数据库兼容。

第一阶段只写计划，不立即移动业务代码。

## 原则

- API 路径保持不变。
- 页面路由保持不变。
- 数据库结构保持兼容。
- 每次只拆一个模块。
- 每次拆分前先补回归测试。
- 拆分过程中前端不应感知变化。
- 服务端重构不和 UI 改版混在同一次提交中。

## 目标职责分离

| 层 | 职责 |
|---|---|
| Routes | HTTP 请求解析、权限入口、响应 JSON 或模板 |
| Services | 业务规则、权限判断、流程编排 |
| Repositories | SQL 查询和数据库写入 |
| Validators | 请求参数校验、错误消息 |

## 推荐顺序

1. `live_comps.py`
2. `lineups.py`
3. `admin.py`
4. `db.py`

这个顺序由低风险到高风险。实时阵容模块相对独立，适合作为第一轮拆分试点。

## 实时阵容拆分目标

目标结构：

```text
routes/live_comp_routes.py
services/live_comp_service.py
repositories/live_comp_stats_repo.py
validators/live_comp_validator.py
```

建议迁移职责：

| 当前职责 | 目标文件 |
|---|---|
| `/api/live-comps*` 路由 | `routes/live_comp_routes.py` |
| JSON 读取、分页、图片重写 | `services/live_comp_service.py` |
| 全局复制统计 SQL | `repositories/live_comp_stats_repo.py` |
| 上传 JSON 校验、文件名校验 | `validators/live_comp_validator.py` |

验收：

```powershell
pytest tests/test_live_comps.py
```

## 阵容模块拆分目标

目标结构：

```text
routes/lineup_routes.py
services/lineup_service.py
services/visibility_service.py
services/interaction_service.py
repositories/lineup_repo.py
repositories/interaction_repo.py
validators/lineup_validator.py
```

重点是把隐藏阵容权限集中到：

```text
services/visibility_service.py
```

必须覆盖规则：

- 普通用户只能隐藏自己的阵容。
- 作者本人可见自己的隐藏阵容。
- 管理员可见所有隐藏阵容。
- 其他用户在列表、收藏、最近浏览、最近复制中不可见隐藏阵容。

验收：

```powershell
pytest tests/test_lineup_permissions.py tests/test_interactions.py tests/test_history.py
```

## 管理员模块拆分目标

目标结构：

```text
routes/admin_routes.py
services/admin_user_service.py
services/admin_lineup_service.py
services/admin_report_service.py
services/admin_dashboard_service.py
```

建议迁移职责：

| 当前职责 | 目标文件 |
|---|---|
| 用户管理 | `services/admin_user_service.py` |
| 阵容管理 | `services/admin_lineup_service.py` |
| 举报处理 | `services/admin_report_service.py` |
| 后台统计 | `services/admin_dashboard_service.py` |

验收：

```powershell
pytest tests/test_admin.py tests/test_growth.py tests/test_visits.py
```

## 数据库模块拆分目标

目标结构：

```text
db/connection.py
db/schema.py
db/migrations.py
```

拆分顺序：

1. 先移动 schema 常量。
2. 再移动连接管理。
3. 最后移动迁移执行逻辑。

验收：

```powershell
pytest tests/test_schema.py tests/test_migration_bug.py
python migrate.py
```

## 通用验收标准

每次拆分后必须满足：

- 所有现有测试通过或相关测试通过后再跑全量测试。
- API 响应字段不变。
- 前端无需修改，或仅做 import/路径调整。
- 数据库无需手工处理。
- 线上部署仍然只需拉代码、迁移、重启。

## 不在本阶段处理

- 不切换到 FastAPI。
- 不切换到 MySQL/PostgreSQL。
- 不引入 Vue/React。
- 不改变前端交互。
- 不改变现有公开 API 路径。
