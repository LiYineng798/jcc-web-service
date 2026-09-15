# 阵容封禁、重审与作者通知

路由在 `lineup_moderation.py`，事务/规则在 `lineup_moderation_service.py`。
Web SQLite schema 对应 DB migration 0016；先部署 DB 再部署 Web。

## 状态机

| 当前状态 | 操作 | 结果 |
| --- | --- | --- |
| 正常/隐藏 | 管理员封禁并写原因 | lineups.status=banned，保存原展示状态/内容 |
| 封禁/退回 | 作者提交修改 | pending，提案单独保存，仍封禁 |
| 待审核 | 管理员通过 | approved，采用提案并恢复原展示状态 |
| 待审核 | 管理员退回 | rejected，仍封禁，可再次提交 |
| 封禁/退回 | 管理员解除封禁 | released，按原内容恢复原展示状态 |

封禁前隐藏的阵容恢复后仍隐藏。待审核只能通过或退回，不直接解除。
封禁/待审/退回不能通过通用编辑、删除、隐藏、调分或举报处理绕过限制；
互动拒绝受限记录，作者也不能用原封禁码重新发布或写入另一条自己的阵容。

所有审核/提案提交带整数 version，通过条件更新防止旧页面覆盖决定；冲突返回 409。
内容、状态、处理事件、通知和审计在同一事务内落库。
重审至少改一项，通过时重新核对赛季可用性。软删除仍保留处理历史。

## 通知

通知已读状态使用独立 revision，只标记实际加载/渲染的版本。
用户端仅 all/unread/read，没有归档，也没有邮件发送。

主页铃铛打开作者专属 `/me/lineup-notifications/<id>` 详情页；
个人中心在页内浮窗查看、返回、编辑，`/me#lineup-notifications` 在账号页处理。
详情与 API 保持作者/管理员权限、private/no-store；页面 noindex，包含删除后的历史。

## 接口约束

| 接口 | 关键字段 |
| --- | --- |
| POST `/api/admin/lineups/<id>/moderation/<action>` | ban/approve/reject/release；version，除 approve 外原因必填 |
| POST `/api/lineups/<id>/revision` | name/code/season_id/version；作者提交 |
| GET `/api/lineups/<id>/moderation` | 原内容、提案、状态与历史 |
| GET `/api/me/lineup-notifications` | status 与分页 |
| PUT `/api/me/lineup-notifications/<id>` | status=unread/read，revision |
| GET `/api/admin/lineup-moderation-summary` | 待审数 |

后台查询/调分仍在 admin 服务。前端文件映射见 [架构](architecture.md)，
本地演练和浏览器命令见 [开发与验证](development.md)。

回滚不能单独退到无封禁保护的旧 Web，避免旧编辑路径重新修改受限阵容；
应核对真实审核数据，使用兼容代码或匹配恢复点。见 [运维](operations.md)。
